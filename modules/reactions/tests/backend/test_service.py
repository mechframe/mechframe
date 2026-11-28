"""reactions' rules on the database (`dev plans/contracts/reactions.md` §2, §7):
the counts and the reader's own, only live things, every refusal, one row for
two presses and for two at once, taking back only one's own, the palette, the
sweep, and export and erase."""

from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from reactions import privacy, service
from reactions.models import Reaction
from reactions.schemas import BUILT_IN, Settings
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, Problem
from kernel import privacy as kernel_privacy

from .conftest import Sources, member

pytestmark = pytest.mark.db
ICONS = Path(__file__).parents[2] / "web" / "icons.tsx"


async def _refused(code: str, act: Any) -> Problem:
    with pytest.raises(Problem) as raised:
        await act
    assert raised.value.code == code, raised.value.detail
    return raised.value


async def _rows(db: AsyncSession, thing: uuid.UUID) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Reaction).where(Reaction.target_id == thing)
        )
        or 0
    )


def _palette(monkeypatch: pytest.MonkeyPatch, *keys: str) -> None:
    async def given(db: AsyncSession) -> list[str]:
        return list(keys)

    monkeypatch.setattr(service, "palette", given)


# --- the counts ------------------------------------------------------------------------------


async def test_counts_every_key_in_the_palette_and_the_readers_own(
    db: AsyncSession, sources: Sources
) -> None:
    thing = sources.tracks.add()
    ana, rae = await member(db), await member(db)
    await service.react(db, ana, "music.track", thing, "fire")
    await service.react(db, rae, "music.track", thing, "fire")
    await service.react(db, rae, "music.track", thing, "mind_blown")
    await db.commit()

    found = await service.counted(db, "music.track", [thing], ana)
    assert found["palette"] == [
        {"key": "fire", "label": "Fire"},
        {"key": "love", "label": "Love"},
        {"key": "mind_blown", "label": "Mind blown"},
    ]
    assert found["items"] == [
        {"id": str(thing), "counts": {"fire": 2, "love": 0, "mind_blown": 1}, "mine": ["fire"]}
    ]
    signed_out = await service.counted(db, "music.track", [thing], None)
    assert signed_out["items"][0]["mine"] == []


async def test_answers_only_live_things_in_the_order_asked(
    db: AsyncSession, sources: Sources
) -> None:
    first, hidden, gone, last = (sources.tracks.add() for _ in range(4))
    sources.tracks.draft(hidden)
    sources.tracks.drop(gone)
    found = await service.counted(db, "music.track", [last, hidden, gone, first, last], None)
    assert [each["id"] for each in found["items"]] == [str(last), str(first)]


async def test_a_type_no_module_on_gives_is_unknown(db: AsyncSession, sources: Sources) -> None:
    thing = sources.tracks.add()
    await _refused("reactions.unknown_type", service.counted(db, "shop.product", [thing], None))
    sources.switches.off.add("music")
    await _refused("reactions.unknown_type", service.counted(db, "music.track", [thing], None))
    ana = await member(db)
    await _refused("reactions.unknown_type", service.react(db, ana, "music.track", thing, "fire"))


# --- pressing and taking back ----------------------------------------------------------------


async def test_pressing_twice_adds_one(db: AsyncSession, sources: Sources) -> None:
    thing = sources.tracks.add()
    ana = await member(db)
    await service.react(db, ana, "music.track", thing, "love")
    again = await service.react(db, ana, "music.track", thing, "love")
    await db.commit()
    assert again["counts"]["love"] == 1
    assert again["mine"] == ["love"]
    assert await _rows(db, thing) == 1


async def test_two_presses_at_once_make_one_row(
    database: Database, db: AsyncSession, sources: Sources
) -> None:
    thing = sources.tracks.add()
    ana = await member(db)

    async def press() -> None:
        async with database.sessions() as each:
            await service.react(each, ana, "music.track", thing, "fire")
            await each.commit()

    await asyncio.gather(press(), press())
    assert await _rows(db, thing) == 1


async def test_an_unverified_address_cant_react(db: AsyncSession, sources: Sources) -> None:
    thing = sources.tracks.add()
    unverified = await member(db, verified=False)
    refused = await _refused(
        "reactions.email_unverified", service.react(db, unverified, "music.track", thing, "fire")
    )
    assert (refused.status, refused.detail) == (403, "Verify your email address first.")


async def test_a_hidden_or_gone_thing_takes_no_reaction(db: AsyncSession, sources: Sources) -> None:
    hidden, gone = sources.tracks.add(), sources.tracks.add()
    ana = await member(db)
    await service.react(db, ana, "music.track", hidden, "fire")
    sources.tracks.draft(hidden)
    sources.tracks.drop(gone)
    for thing in (hidden, gone):
        refused = await _refused(
            "reactions.not_found", service.react(db, ana, "music.track", thing, "fire")
        )
        assert refused.status == 404
        await _refused(
            "reactions.not_found", service.unreact(db, ana, "music.track", thing, "fire")
        )


async def test_a_key_outside_the_palette_is_refused_but_can_be_taken_back(
    db: AsyncSession, sources: Sources, monkeypatch: pytest.MonkeyPatch
) -> None:
    thing = sources.tracks.add()
    ana = await member(db)
    await service.react(db, ana, "music.track", thing, "fire")
    _palette(monkeypatch, "love")

    refused = await _refused(
        "reactions.unknown_key", service.react(db, ana, "music.track", thing, "fire")
    )
    assert refused.status == 422
    await _refused("reactions.unknown_key", service.react(db, ana, "music.track", thing, "clap"))
    # Counted against the palette alone: the fire row is kept, not counted.
    assert (await service.counted(db, "music.track", [thing], ana))["items"][0] == {
        "id": str(thing),
        "counts": {"love": 0},
        "mine": [],
    }
    taken = await service.unreact(db, ana, "music.track", thing, "fire")
    assert taken == {"id": str(thing), "counts": {"love": 0}, "mine": []}
    assert await _rows(db, thing) == 0
    await _refused("reactions.unknown_key", service.unreact(db, ana, "music.track", thing, "clap"))


async def test_the_palettes_order_is_the_rows(
    db: AsyncSession, sources: Sources, monkeypatch: pytest.MonkeyPatch
) -> None:
    thing = sources.tracks.add()
    ana = await member(db)
    _palette(monkeypatch, "mind_blown", "fire")
    await service.react(db, ana, "music.track", thing, "fire")
    await service.react(db, ana, "music.track", thing, "mind_blown")
    found = await service.counted(db, "music.track", [thing], ana)
    assert [each["key"] for each in found["palette"]] == ["mind_blown", "fire"]
    assert list(found["items"][0]["counts"]) == ["mind_blown", "fire"]
    assert found["items"][0]["mine"] == ["mind_blown", "fire"]


async def test_taking_back_one_thats_not_there_answers_the_counts(
    db: AsyncSession, sources: Sources
) -> None:
    thing = sources.tracks.add()
    ana = await member(db)
    taken = await service.unreact(db, ana, "music.track", thing, "love")
    assert taken == {
        "id": str(thing),
        "counts": {"fire": 0, "love": 0, "mind_blown": 0},
        "mine": [],
    }


async def test_nobody_takes_back_anothers_reaction(db: AsyncSession, sources: Sources) -> None:
    thing = sources.tracks.add()
    ana, rae = await member(db), await member(db)
    await service.react(db, ana, "music.track", thing, "fire")
    taken = await service.unreact(db, rae, "music.track", thing, "fire")
    await db.commit()
    assert taken["counts"]["fire"] == 1
    assert taken["mine"] == []
    assert await _rows(db, thing) == 1


# --- the palette -----------------------------------------------------------------------------


def test_the_palette_is_built_in_keys_each_once() -> None:
    assert Settings().palette == ["fire", "love", "mind_blown"]
    assert Settings(palette=["love"]).palette == ["love"]
    for wrong in (["fire", "clap"], ["fire", "fire"], [], ["fire", "love", "mind_blown", "love"]):
        with pytest.raises(ValidationError):
            Settings(palette=wrong)


def test_every_built_in_reaction_has_its_icon() -> None:
    drawn = re.findall(r"^  ([a-z_]+): ", ICONS.read_text(encoding="utf-8"), re.MULTILINE)
    assert drawn == list(BUILT_IN)


# --- the sweep -------------------------------------------------------------------------------


async def test_the_sweep_deletes_only_the_reactions_of_things_that_are_gone(
    db: AsyncSession, sources: Sources
) -> None:
    kept, hidden, gone = (sources.tracks.add() for _ in range(3))
    ana = await member(db)
    for thing in (kept, hidden, gone):
        await service.react(db, ana, "music.track", thing, "fire")
    await db.commit()
    sources.tracks.draft(hidden)
    sources.tracks.drop(gone)

    assert await service.sweep(db) >= 1
    await db.commit()
    assert [await _rows(db, each) for each in (kept, hidden, gone)] == [1, 1, 0]
    assert await service.sweep(db) == 0


async def test_the_sweep_skips_a_type_thats_off(db: AsyncSession, sources: Sources) -> None:
    thing = sources.tracks.add()
    ana = await member(db)
    await service.react(db, ana, "music.track", thing, "fire")
    await db.commit()
    sources.tracks.drop(thing)
    sources.switches.off.add("music")
    await service.sweep(db)
    await db.commit()
    assert await _rows(db, thing) == 1
    sources.switches.off.clear()
    await service.sweep(db)
    await db.commit()
    assert await _rows(db, thing) == 0


# --- export and erase ------------------------------------------------------------------------


async def test_export_lists_a_persons_reactions_and_erase_deletes_them(
    db: AsyncSession, sources: Sources
) -> None:
    thing = sources.tracks.add()
    ana, rae = await member(db), await member(db)
    await service.react(db, ana, "music.track", thing, "fire")
    await service.react(db, ana, "music.track", thing, "love")
    await service.react(db, rae, "music.track", thing, "love")
    await db.commit()

    subject = kernel_privacy.Subject(user_id=ana.id, email=ana.email)
    exported = await privacy.export_user_data(db, subject)
    assert [(each["thing"], each["reaction"]) for each in exported["reactions"]] == [
        (f"music.track {thing}", "fire"),
        (f"music.track {thing}", "love"),
    ]
    await privacy.delete_user_data(db, subject)
    await db.commit()
    assert (await privacy.export_user_data(db, subject))["reactions"] == []
    left = await service.counted(db, "music.track", [thing], None)
    assert left["items"][0]["counts"] == {"fire": 0, "love": 1, "mind_blown": 0}
