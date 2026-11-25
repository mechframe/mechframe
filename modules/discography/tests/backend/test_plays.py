"""discography 0.1.1's plays (`dev plans/contracts/audio-player.md` §2, "discography
0.1.1", and §7): a play counts only for a live track that plays, through
audio-player; deleting a track or a release forgets its plays in the same
transaction; the Dashboard card's figures; and the seed's two weeks of plays."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from audio_player import public as audio_player
from discography import service
from discography.models import Release, Track
from discography.seed import _NAMESPACE, RELEASES
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, clock, load_module
from kernel import seed as seeding

from ..conftest import slug
from .conftest import Store

pytestmark = pytest.mark.db
MODULE = Path(__file__).resolve().parents[2]
LINK = "https://soundcloud.com/petrodestroys/catalyst"
SOURCE = "discography.track"
#: Days far from any other test's, as audio-player's own tests take them.
_FAR = date(2600, 1, 1)


def visit(address: str = "203.0.113.9", agent: str = "Mozilla/5.0 (Plays)") -> Request:
    """A request from `address` in a browser that calls itself `agent`."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"user-agent", agent.encode())],
            "client": (address, 51000),
            "app": SimpleNamespace(state=SimpleNamespace()),
        }
    )


def far_day() -> date:
    """A day no other test has had."""
    return _FAR + timedelta(days=uuid.uuid4().int % 300_000)


async def _release(db: AsyncSession, *, live: bool = True, **fields: Any) -> Release:
    release = await service.create_release(
        db, {"title": "An album", "slug": slug(), "artist_line": "The band", **fields}, by=None
    )
    await db.commit()
    if live:
        await service.publish(db, release.id, None, by=None)
        await db.commit()
    return release


async def _track(db: AsyncSession, release: Release, title: str = "A track", **kw: Any) -> Track:
    track = await service.create_track(db, release.id, title, kw.get("link", LINK), by=None)
    await db.commit()
    return track


async def _today(db: AsyncSession, *ids: uuid.UUID) -> dict[uuid.UUID, int]:
    today = clock.now().date()
    found = await audio_player.plays(db, SOURCE, since=today, until=today)
    await db.commit()  # not a rollback, which would expire the test's rows
    return {each: found[each] for each in ids if each in found}


# --- counting --------------------------------------------------------------------------------


async def test_a_live_track_that_plays_counts_once_a_listener_a_day(db: AsyncSession) -> None:
    track = await _track(db, await _release(db))
    assert await service.count_play(db, visit(), track.id) is True
    await db.commit()
    assert await service.count_play(db, visit(), track.id) is False
    await db.commit()
    assert await service.count_play(db, visit(address="198.51.100.4"), track.id) is True
    await db.commit()
    assert await _today(db, track.id) == {track.id: 2}


async def test_a_play_holds_its_track_until_it_is_written(
    db: AsyncSession, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A delete that took the track between the check and the count would forget
    # its plays first, and the play would land after (CodeRabbit on #151). While
    # the count runs, another session can't take the row for a delete.
    track_id = (await _track(db, await _release(db))).id
    real = audio_player.count
    probed: list[str] = []

    async def counting(session: AsyncSession, request: Request, **kw: Any) -> bool:
        async with database.sessions() as other:
            try:
                await other.execute(
                    text("SELECT id FROM discography_track WHERE id = :id FOR UPDATE NOWAIT"),
                    {"id": track_id},
                )
                probed.append("free")
            except DBAPIError:
                probed.append("held")
            finally:
                await other.rollback()
        return await real(session, request, **kw)

    monkeypatch.setattr(audio_player, "count", counting)
    assert await service.count_play(db, visit(), track_id) is True
    await db.commit()
    assert probed == ["held"]
    assert await _today(db, track_id) == {track_id: 1}


async def test_a_draft_a_track_that_cant_play_and_no_track_count_nothing(
    db: AsyncSession,
) -> None:
    draft = await _track(db, await _release(db, live=False))
    live = await _release(db)
    silent = await _track(db, live, "No audio yet", link=None)
    nobody = uuid.uuid4()
    for each in (draft.id, silent.id, nobody):
        assert await service.count_play(db, visit(), each) is False
        await db.commit()
    assert await _today(db, draft.id, silent.id, nobody) == {}


async def test_a_track_of_a_release_taken_down_counts_nothing(db: AsyncSession) -> None:
    release = await _release(db)
    track = await _track(db, release)
    await service.unpublish(db, release.id, by=None)
    await db.commit()
    assert await service.count_play(db, visit(), track.id) is False
    await db.commit()
    assert await _today(db, track.id) == {}


# --- deleting forgets ------------------------------------------------------------------------


async def test_deleting_a_track_forgets_its_plays_and_no_other(db: AsyncSession) -> None:
    release = await _release(db)
    gone, kept = await _track(db, release, "Gone"), await _track(db, release, "Kept")
    day = far_day()
    for each in (gone, kept):
        await audio_player.add_daily(db, SOURCE, each.id, day, 5)
    await db.commit()
    await service.remove_track(db, gone.id, by=None)
    await db.commit()
    found = await audio_player.plays(db, SOURCE, since=day, until=day)
    assert found == {kept.id: 5}


async def test_deleting_a_release_forgets_every_track_s_plays(db: AsyncSession) -> None:
    release = await _release(db)
    tracks = [await _track(db, release, f"Track {each}") for each in range(3)]
    day = far_day()
    for each in tracks:
        await audio_player.add_daily(db, SOURCE, each.id, day, 3)
    await db.commit()
    await service.remove_release(db, release.id, by=None)
    await db.commit()
    assert await audio_player.plays(db, SOURCE, since=day, until=day) == {}


# --- the Dashboard card ----------------------------------------------------------------------


async def test_the_card_counts_the_last_seven_days_and_the_seven_before(db: AsyncSession) -> None:
    release = await _release(db)
    gather = await _track(db, release, "Gather Around")
    pray = await _track(db, release, "Pray For You")
    today = far_day()
    # This week: today and six days back. Last week: seven to thirteen back.
    for back, plays in ((0, 10), (6, 5), (7, 4), (13, 6), (14, 100)):
        await audio_player.add_daily(db, SOURCE, gather.id, today - timedelta(days=back), plays)
    await audio_player.add_daily(db, SOURCE, pray.id, today - timedelta(days=2), 3)
    await audio_player.add_daily(db, SOURCE, pray.id, today + timedelta(days=1), 50)
    await db.commit()
    assert await service.plays_week(db, today) == {
        "this_week": 18,
        "last_week": 10,
        "leading": "Gather Around",
    }


async def test_the_card_leaves_out_plays_of_items_that_arent_tracks(db: AsyncSession) -> None:
    track = await _track(db, await _release(db), "Real Talk")
    today = far_day()
    await audio_player.add_daily(db, SOURCE, uuid.uuid4(), today, 500)
    await audio_player.add_daily(db, SOURCE, track.id, today, 2)
    await db.commit()
    assert await service.plays_week(db, today) == {
        "this_week": 2,
        "last_week": 0,
        "leading": "Real Talk",
    }


async def test_a_tie_for_the_lead_goes_to_the_title_first_in_order(db: AsyncSession) -> None:
    release = await _release(db)
    later, first = await _track(db, release, "Pray For You"), await _track(db, release, "boom")
    today = far_day()
    for each in (later, first):
        await audio_player.add_daily(db, SOURCE, each.id, today, 7)
    await db.commit()
    assert (await service.plays_week(db, today))["leading"] == "boom"


async def test_a_week_with_none_has_no_leader(db: AsyncSession) -> None:
    track = await _track(db, await _release(db))
    today = far_day()
    await audio_player.add_daily(db, SOURCE, track.id, today - timedelta(days=8), 9)
    await db.commit()
    assert await service.plays_week(db, today) == {
        "this_week": 0,
        "last_week": 9,
        "leading": None,
    }


# --- the seed --------------------------------------------------------------------------------


async def test_the_seed_gives_its_tracks_two_weeks_of_plays_rising(
    db: AsyncSession, store: Store
) -> None:
    discography = load_module(MODULE / "module.json")
    tracks = [
        uuid.uuid5(_NAMESPACE, f"{each[0]}/{position}")
        for each in RELEASES
        for position in range(len(each[6]))
    ]
    # The seed makes only what isn't there: what an earlier test or run made goes first.
    for each in RELEASES:
        if await db.get(Release, uuid.uuid5(_NAMESPACE, each[0])) is not None:
            await service.remove_release(db, uuid.uuid5(_NAMESPACE, each[0]), by=None)
    await db.commit()
    await seeding.run(db, [discography], environ={"MECHFRAME_ALLOW_SEED": "1"})
    await db.commit()
    today = clock.now().date()
    week = await audio_player.plays(db, SOURCE, since=today - timedelta(days=6), until=today)
    before = await audio_player.plays(
        db, SOURCE, since=today - timedelta(days=13), until=today - timedelta(days=7)
    )
    older = await audio_player.plays(
        db, SOURCE, since=today - timedelta(days=400), until=today - timedelta(days=14)
    )
    assert len(tracks) == 4
    for track in tracks:
        assert week[track] > before[track] > 0
        assert track not in older
