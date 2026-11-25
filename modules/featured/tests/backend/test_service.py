"""featured's rules on the database (`dev plans/contracts/featured.md` §2, §3,
§7): what's live at the edges of its dates, each placement's state, items
hidden and gone and their module off, every refusal of a save, two saves at
once, the slots' own rules, the picker, pasted links, the public read and the
Dashboard."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from featured import dashboard, public, service
from featured.models import Placement, Slot
from featured.schemas import KindIn, PlacementIn
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, Problem, clock
from kernel.models import AuditEvent

from ..conftest import key
from .conftest import Sources

pytestmark = pytest.mark.db
NOW = datetime(2026, 11, 15, 18, 0, tzinfo=UTC)
VIDEO = "dQw4w9WgXcQ"
KINDS = [KindIn(key="music-video", label="Music video"), KindIn(key="poetry", label="Poetry")]


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "now", lambda: NOW)


def at(hours: float) -> str:
    return (NOW + timedelta(hours=hours)).isoformat()


def item(ident: uuid.UUID, kind: str = "music.track", **more: Any) -> PlacementIn:
    return PlacementIn.model_validate({"ref": {"type": kind, "id": str(ident)}, **more})


def link(
    url: str = f"https://youtu.be/{VIDEO}", title: str = "Hook It Up", **more: Any
) -> PlacementIn:
    kind = more.pop("kind", None)
    return PlacementIn.model_validate({"link": {"url": url, "title": title, "kind": kind}, **more})


async def _slot(db: AsyncSession, accepts: tuple[str, ...] = ("music.track",), **more: Any) -> Slot:
    return await service.create_slot(
        db,
        more.pop("slot_key", None) or key(),
        more.pop("label", "Spotlight"),
        list(accepts),
        more.pop("kinds", []),
        more.pop("on_dashboard", None),
        by=None,
    )


async def _save(db: AsyncSession, slot: Slot, *items: PlacementIn) -> dict[str, Any]:
    await service.save_placements(db, slot.key, slot.version, list(items), by=None)
    return await service.full_slot(db, slot)


async def _refused(code: str, act: Any) -> Problem:
    with pytest.raises(Problem) as raised:
        await act
    assert raised.value.code == code, raised.value.detail
    return raised.value


def _states(full: dict[str, Any]) -> list[str]:
    return [each["state"] for each in full["items"]]


# --- what's live -----------------------------------------------------------------------------


async def test_whats_live_at_the_edges_of_its_dates(db: AsyncSession, sources: Sources) -> None:
    slot = await _slot(db)
    ids = [sources.tracks.add(f"Track {n}") for n in range(6)]
    full = await _save(
        db,
        slot,
        item(ids[0], starts_at=at(0)),  # starts this minute: live
        item(ids[1], ends_at=at(0)),  # ended this minute
        item(ids[2], starts_at=at(-24), ends_at=at(0.01)),  # live until just after now
        item(ids[3], starts_at=at(48)),  # later
        item(ids[4], starts_at=at(24), ends_at=at(30)),  # the soonest to start
        item(ids[5]),  # no dates: always
    )
    assert _states(full) == ["live", "ended", "live", "scheduled", "next", "live"]
    assert full["counts"] == {"live": 3, "scheduled": 2}
    assert full["now"] == {"title": "Track 0", "starts_at": NOW.isoformat(), "ends_at": None}
    shown = await service.live_slot(db, slot.key)
    assert shown is not None
    assert [each["ref"]["title"] for each in shown["items"]] == ["Track 0", "Track 2", "Track 5"]
    assert shown["items"][0]["ref"] == {
        "type": "music.track",
        "id": str(ids[0]),
        "title": "Track 0",
        "line": "Catalyst, petro and J Tone",
        "image": "https://files.test/cover.jpg",
        "path": f"/music/{ids[0].hex[:8]}",
    }


async def test_a_draft_is_hidden_and_a_gone_item_removed(
    db: AsyncSession, sources: Sources
) -> None:
    slot = await _slot(db)
    draft, gone, shown_id = (
        sources.tracks.add("A draft"),
        sources.tracks.add("Gone"),
        sources.tracks.add(),
    )
    await _save(db, slot, item(draft), item(gone), item(shown_id))
    sources.tracks.draft(draft)
    sources.tracks.drop(gone)
    full = await service.full_slot(db, slot)
    assert _states(full) == ["hidden", "removed", "live"]
    assert full["items"][0]["ref"]["live"] is False
    assert full["items"][1]["ref"] is None
    assert full["items"][1]["removed"] is True
    assert full["items"][1]["item"] == {"type": "music.track", "id": str(gone)}
    shown = await service.live_slot(db, slot.key)
    assert shown is not None
    assert [each["ref"]["id"] for each in shown["items"]] == [str(shown_id)]


async def test_an_ended_item_shows_ended_even_as_a_draft(
    db: AsyncSession, sources: Sources
) -> None:
    slot = await _slot(db)
    ident = sources.tracks.add(live=False)
    full = await _save(db, slot, item(ident, ends_at=at(-1)))
    assert _states(full) == ["ended"]


async def test_a_placement_whose_module_is_off_is_hidden_and_kept(
    db: AsyncSession, sources: Sources
) -> None:
    slot = await _slot(db)
    off, other = sources.tracks.add("Off"), sources.tracks.add("Gone while off")
    await _save(db, slot, item(off, starts_at=at(-1)), item(other))
    sources.switches.off.add("music")
    full = await service.full_slot(db, slot)
    assert _states(full) == ["hidden", "hidden"]
    assert full["items"][0]["ref"] is None
    assert full["items"][0]["removed"] is False
    assert full["items"][0]["item"] == {"type": "music.track", "id": str(off)}
    shown = await service.live_slot(db, slot.key)
    assert shown is not None
    assert shown["items"] == []
    # A save keeps them as they are, dates changed included, and can't add another.
    kept = [
        PlacementIn.model_validate({"id": each["id"], "ref": each["item"], "starts_at": at(-2)})
        for each in full["items"]
    ]
    await service.save_placements(db, slot.key, slot.version, kept, by=None)
    rows = list(await db.scalars(select(Placement).where(Placement.slot_key == slot.key)))
    assert {row.ref_id for row in rows} == {off, other}
    await _refused(
        "featured.not_accepted",
        service.save_placements(
            db, slot.key, slot.version, [*kept, item(sources.tracks.add())], by=None
        ),
    )
    sources.switches.off.clear()
    assert _states(await service.full_slot(db, slot)) == ["live", "live"]


async def test_a_save_leaves_out_a_kept_item_thats_gone(db: AsyncSession, sources: Sources) -> None:
    slot = await _slot(db)
    gone, kept = sources.tracks.add("Gone"), sources.tracks.add("Kept")
    full = await _save(db, slot, item(gone), item(kept))
    sources.tracks.drop(gone)
    again = [
        PlacementIn.model_validate({"id": each["id"], "ref": each["item"]})
        for each in full["items"]
    ]
    await service.save_placements(db, slot.key, slot.version, again, by=None)
    after = await service.full_slot(db, slot)
    assert [each["ref"]["title"] for each in after["items"]] == ["Kept"]
    assert after["items"][0]["id"] == full["items"][1]["id"]


# --- a save ----------------------------------------------------------------------------------


async def test_a_save_keeps_ids_moves_rows_and_bumps_the_version(
    db: AsyncSession, sources: Sources, said: list[tuple[str, Any]]
) -> None:
    slot = await _slot(db, ("music.track", "youtube"), kinds=KINDS)
    one, two = sources.tracks.add("One"), sources.tracks.add("Two")
    first = await _save(db, slot, item(one), item(two), link(kind="poetry"))
    assert first["version"] == 2
    ids = [each["id"] for each in first["items"]]
    # The rows swap places: the unique place is checked at the commit.
    swapped = [
        PlacementIn.model_validate(
            {
                "id": ids[2],
                "link": {
                    "url": f"https://www.youtube.com/watch?v={VIDEO}&t=42",
                    "title": "  Hook   It Up  ",
                    "kind": "music-video",
                },
            }
        ),
        PlacementIn.model_validate({"id": ids[1], "ref": {"type": "music.track", "id": str(two)}}),
        PlacementIn.model_validate({"id": ids[0], "ref": {"type": "music.track", "id": str(one)}}),
    ]
    await service.save_placements(db, slot.key, 2, swapped, by=None)
    await db.flush()  # an immediate unique place would refuse the swap here
    after = await service.full_slot(db, slot)
    assert [each["id"] for each in after["items"]] == [ids[2], ids[1], ids[0]]
    assert after["items"][0]["link"] == {
        "url": f"https://www.youtube.com/watch?v={VIDEO}",
        "video_id": VIDEO,
        "title": "Hook It Up",
        "kind": "music-video",
    }
    assert after["version"] == 3
    assert [name for name, _ in said] == ["featured.placement.changed"] * 2
    assert said[-1][1].slot_key == slot.key
    entry = await db.scalar(
        select(AuditEvent)
        .where(AuditEvent.action == "featured.slot.saved", AuditEvent.target_id == slot.key)
        .order_by(AuditEvent.id.desc())
    )
    assert entry is not None
    assert entry.details == {
        "count": 3,
        "items": [{"video": VIDEO}, {"ref": f"music.track:{two}"}, {"ref": f"music.track:{one}"}],
    }


async def test_the_audit_keeps_a_long_list_under_its_limit(
    db: AsyncSession, sources: Sources
) -> None:
    slot = await _slot(db)
    many = [item(sources.tracks.add(), starts_at=at(1), ends_at=at(2)) for _ in range(100)]
    await _save(db, slot, *many)
    entry = await db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "featured.slot.saved", AuditEvent.target_id == slot.key
        )
    )
    assert entry is not None
    assert entry.details["count"] == 100
    assert entry.details["more"] == 100 - len(entry.details["items"]) > 0
    assert len(json.dumps(entry.details)) <= 4096


async def test_the_refusals_of_a_save(db: AsyncSession, sources: Sources) -> None:
    tracks = await _slot(db, kinds=KINDS)
    videos = await _slot(db, ("youtube",), kinds=KINDS)
    ident = sources.tracks.add()

    async def refused(code: str, slot: Slot, *items: PlacementIn) -> Problem:
        return await _refused(
            code, service.save_placements(db, slot.key, slot.version, list(items), by=None)
        )

    await refused("featured.not_accepted", tracks, item(sources.albums.add(), "music.album"))
    await refused("featured.not_accepted", tracks, link())
    await refused("featured.not_accepted", videos, item(ident))
    await refused("featured.not_found", tracks, item(uuid.uuid4()))
    for url in (
        "https://vimeo.com/76979871",
        "https://www.youtube.com/playlist?list=PL590L5WQmH8fJ54F369BLDSqIwcs-TCfs",
        "https://www.youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
        "javascript:alert(1)",
    ):
        await refused("featured.not_youtube", videos, link(url))
    await refused("featured.no_title", videos, link(title="   "))
    await refused("featured.no_title", videos, link(title="x" * 201))
    await refused("featured.unknown_kind", videos, link(kind="rap-battle"))
    await refused("featured.bad_dates", tracks, item(ident, starts_at=at(1), ends_at=at(1)))
    await refused("featured.bad_dates", tracks, item(ident, starts_at=at(2), ends_at=at(1)))
    await refused("kernel.invalid_request", tracks, item(ident, starts_at="2026-11-15T12:00:00"))
    await refused("kernel.invalid_request", tracks, PlacementIn.model_validate({}))
    await refused(
        "kernel.invalid_request",
        tracks,
        PlacementIn.model_validate(
            {"id": str(uuid.uuid4()), "ref": {"type": "music.track", "id": str(ident)}}
        ),
    )
    problem = await refused("featured.too_many", tracks, *[item(ident)] * 101)
    assert problem.status == 422
    stale = await _refused(
        "featured.changed", service.save_placements(db, tracks.key, 7, [item(ident)], by=None)
    )
    assert stale.status == 409
    assert stale.extra["slot"]["key"] == tracks.key
    assert stale.extra["slot"]["version"] == 1


async def test_a_placement_listed_twice_is_refused(db: AsyncSession, sources: Sources) -> None:
    slot = await _slot(db)
    ident = sources.tracks.add()
    full = await _save(db, slot, item(ident))
    twice = [
        PlacementIn.model_validate(
            {"id": full["items"][0]["id"], "ref": {"type": "music.track", "id": str(ident)}}
        )
    ] * 2
    await _refused(
        "kernel.invalid_request",
        service.save_placements(db, slot.key, slot.version, twice, by=None),
    )


async def test_two_saves_of_one_slot_at_once_make_one_version(
    database: Database, sources: Sources
) -> None:
    """Both read version 1; the first holds the slot while its items are looked
    up, so the second waits, reads version 2, and answers 409. Without the
    lock both would pass the check and the first's list would be lost."""
    async with database.sessions() as made:
        slot = await _slot(made)
        await made.commit()
    one, two = sources.tracks.add("First"), sources.tracks.add("Second")
    sources.tracks.pause = 0.4

    async def save(ident: uuid.UUID, wait: float) -> str:
        await asyncio.sleep(wait)
        async with database.sessions() as session:
            try:
                await service.save_placements(session, slot.key, 1, [item(ident)], by=None)
            except Problem as problem:
                await session.rollback()
                return problem.code
            await session.commit()
            return "saved"

    try:
        answers = await asyncio.gather(save(one, 0), save(two, 0.1))
        assert sorted(answers) == ["featured.changed", "saved"]
        async with database.sessions() as read:
            found = await read.scalar(select(Slot).where(Slot.key == slot.key))
            assert found is not None
            assert found.version == 2
            rows = list(
                await read.scalars(select(Placement.ref_id).where(Placement.slot_key == slot.key))
            )
            assert rows == [one]
    finally:
        sources.tracks.pause = 0
        async with database.sessions() as tidy:
            await tidy.execute(delete(Slot).where(Slot.key == slot.key))
            await tidy.commit()


async def test_a_new_slot_waits_for_one_being_made(database: Database, sources: Sources) -> None:
    """Two made at once would read the same last place, and both be the first
    (cubic on #157): with the lock held elsewhere, a new slot waits for it."""
    async with database.sessions() as holder:
        await holder.execute(
            text("SELECT pg_advisory_xact_lock(:class, :id)"), service.NEW_SLOT_LOCK
        )
        async with database.sessions() as actor:
            pid = await actor.scalar(text("SELECT pg_backend_pid()"))
            task = asyncio.ensure_future(_slot(actor))
            async with database.sessions() as probe:
                for _ in range(100):
                    waiting = await probe.scalar(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"),
                        {"pid": pid},
                    )
                    await probe.rollback()
                    if waiting == "Lock":
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise AssertionError("A new slot never waited for the one being made.")
            assert not task.done()
            await holder.rollback()
            await task
            await actor.rollback()


# --- slots -----------------------------------------------------------------------------------


async def test_a_new_slot_and_its_refusals(db: AsyncSession, sources: Sources) -> None:
    await db.execute(delete(Slot))  # rolled back at the end: only this test's slots
    first = await _slot(db, ("music.track", "music.track"), label="  Spot   light ")
    assert (first.accepts, first.label, first.on_dashboard, first.position) == (
        ["music.track"],
        "Spot light",
        True,
        0,
    )
    second = await _slot(db, ("youtube",), kinds=KINDS)
    assert (second.on_dashboard, second.position, second.kinds[0]) == (
        False,
        1,
        {"key": "music-video", "label": "Music video"},
    )
    third = await _slot(db, on_dashboard=True)
    assert third.on_dashboard is True
    await _refused("featured.key_taken", _slot(db, slot_key=first.key))
    await _refused("featured.unknown_type", _slot(db, ("music.single",)))
    sources.switches.off.add("music")
    await _refused("featured.unknown_type", _slot(db, ("music.track",)))
    await _refused(
        "kernel.invalid_request",
        _slot(db, ("youtube",), kinds=[KINDS[0], KindIn(key="music-video", label="Again")]),
    )
    listed = await service.every_slot(db)
    assert [each["key"] for each in listed["items"]] == [first.key, second.key, third.key]
    assert listed["types"] == []  # music is off
    sources.switches.off.clear()
    assert (await service.every_slot(db))["types"] == [
        {"type": "music.album", "label": "Albums"},
        {"type": "music.track", "label": "Tracks"},
    ]


async def test_a_slots_change_and_whats_still_in_use(
    db: AsyncSession, sources: Sources, said: list[tuple[str, Any]]
) -> None:
    slot = await _slot(db, ("music.track", "music.album", "youtube"), kinds=KINDS)
    await _save(db, slot, item(sources.tracks.add()), link(kind="poetry"))

    async def change(**fields: Any) -> Slot:
        return await service.change_slot(db, slot.key, slot.version, fields, by=None)

    await _refused("featured.in_use", change(accepts=["music.album", "youtube"]))
    await _refused("featured.in_use", change(accepts=["music.track", "music.album"]))
    await _refused(
        "featured.in_use", change(kinds=[{"key": "music-video", "label": "Music video"}])
    )
    await _refused("featured.unknown_type", change(accepts=["music.track", "youtube", "blog.post"]))
    await _refused(
        "featured.changed", service.change_slot(db, slot.key, 99, {"label": "X"}, by=None)
    )
    changed = await change(
        label="Videos and tracks",
        accepts=["music.track", "youtube"],
        kinds=[{"key": "poetry", "label": "Spoken word"}],
        on_dashboard=False,
    )
    assert (
        changed.label,
        changed.accepts,
        changed.kinds,
        changed.on_dashboard,
        changed.version,
    ) == (
        "Videos and tracks",
        ["music.track", "youtube"],
        [{"key": "poetry", "label": "Spoken word"}],
        False,
        3,
    )
    # A type whose module is off may stay, though it couldn't be added now.
    sources.switches.off.add("music")
    kept = await change(accepts=["youtube", "music.track"])
    assert kept.accepts == ["youtube", "music.track"]
    assert said[-1][0] == "featured.placement.changed"


async def test_a_name_with_an_at_sign_is_saved_and_never_audited(
    db: AsyncSession, sources: Sources
) -> None:
    """The audit refuses an `@` as an address (Codex on #157): the label stays out of it."""
    slot = await _slot(db, label="Live @ Home")
    renamed = await service.change_slot(
        db, slot.key, slot.version, {"label": "Live @ Work"}, by=None
    )
    assert renamed.label == "Live @ Work"
    entries = list(
        await db.scalars(
            select(AuditEvent).where(AuditEvent.target_id == slot.key).order_by(AuditEvent.id)
        )
    )
    assert [entry.action for entry in entries] == ["featured.slot.created", "featured.slot.changed"]
    assert entries[0].details == {
        "accepts": ["music.track"],
        "kinds": [],
        "on_dashboard": slot.on_dashboard,
    }
    assert entries[1].details == {"label": True}


async def test_a_slot_goes_with_its_placements(
    db: AsyncSession, sources: Sources, said: list[tuple[str, Any]]
) -> None:
    slot = await _slot(db)
    await _save(db, slot, item(sources.tracks.add()))
    await service.remove_slot(db, slot.key, by=None)
    assert (
        await db.scalar(
            select(func.count()).select_from(Placement).where(Placement.slot_key == slot.key)
        )
        == 0
    )
    assert await service.live_slot(db, slot.key) is None
    await _refused("featured.slot_not_found", service.remove_slot(db, slot.key, by=None))
    assert said[-1][1].slot_key == slot.key


# --- the picker, links and the public read ----------------------------------------------------


async def test_the_picker_reads_only_what_the_slot_takes(
    db: AsyncSession, sources: Sources
) -> None:
    slot = await _slot(db, ("music.track", "youtube"))
    sources.tracks.add("Gather Around")
    sources.tracks.add("Hook It Up", live=False)
    page = await service.choices(db, slot.key, "music.track", "hook", None)
    assert [(each["title"], each["live"]) for each in page["items"]] == [("Hook It Up", False)]
    assert sources.tracks.asked[-1] == ("pick", "hook", None, 20)
    # A page at a time, newest first, to the last.
    for n in range(23):
        sources.tracks.add(f"Track {n:02d}")
    first = await service.choices(db, slot.key, "music.track", None, None)
    assert len(first["items"]) == 20
    assert first["items"][0]["title"] == "Track 22"
    rest = await service.choices(db, slot.key, "music.track", None, first["next_cursor"])
    assert [each["title"] for each in rest["items"]] == [
        "Track 02",
        "Track 01",
        "Track 00",
        "Hook It Up",
        "Gather Around",
    ]
    assert rest["next_cursor"] is None
    for kind in ("music.album", "youtube"):
        await _refused("featured.not_accepted", service.choices(db, slot.key, kind, None, None))
    sources.switches.off.add("music")
    await _refused(
        "featured.not_accepted", service.choices(db, slot.key, "music.track", None, None)
    )
    await _refused("featured.slot_not_found", service.choices(db, key(), "music.track", None, None))


async def test_pasted_links_are_read_and_titled(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[list[str]] = []

    async def titles(ids: Any) -> dict[str, str | None]:
        wanted = list(ids)
        asked.append(wanted)
        return {each: f"Title of {each}" for each in wanted}

    monkeypatch.setattr(service.youtube, "titles", titles)
    found = await service.pasted(
        db,
        [
            f" https://youtu.be/{VIDEO}?t=3 ",
            "https://vimeo.com/1",
            "https://www.youtube.com/shorts/abcdefghijk",
        ],
    )
    assert found == {
        "items": [
            {
                "url": f"https://www.youtube.com/watch?v={VIDEO}",
                "video_id": VIDEO,
                "title": f"Title of {VIDEO}",
            },
            {
                "url": "https://www.youtube.com/watch?v=abcdefghijk",
                "video_id": "abcdefghijk",
                "title": "Title of abcdefghijk",
            },
        ],
        "refused": [{"url": "https://vimeo.com/1", "reason": "featured.not_youtube"}],
    }
    assert asked == [[VIDEO, "abcdefghijk"]]

    class Off:
        oembed_titles = False

    async def off(db: Any) -> Off:
        return Off()

    monkeypatch.setattr(service, "settings_of", off)
    quiet = await service.pasted(db, [f"https://youtu.be/{VIDEO}"])
    assert quiet["items"][0]["title"] is None
    assert len(asked) == 1


async def test_the_public_read_for_a_sites_code(db: AsyncSession, sources: Sources) -> None:
    slot = await _slot(db, ("youtube",), kinds=KINDS)
    await _save(db, slot, link(kind="music-video"), link(title="Later", starts_at=at(1)))
    found = await public.live(db, slot.key)
    assert found is not None
    assert found.kinds[0].label == "Music video"
    assert [(each.link.title if each.link else None) for each in found.items] == ["Hook It Up"]
    assert await public.live(db, key()) is None


# --- the Dashboard ---------------------------------------------------------------------------


async def _ending(db: AsyncSession, slot: Slot) -> list[service.Ending]:
    return [each for each in await service.ending_soon(db) if each.slot.key == slot.key]


async def test_the_warning_comes_two_days_out_and_not_three(
    db: AsyncSession, sources: Sources
) -> None:
    soon = await _slot(db, on_dashboard=True)
    later = await _slot(db, on_dashboard=True)
    queued = await _slot(db, on_dashboard=True)
    open_ended = await _slot(db, on_dashboard=True)
    hidden = await _slot(db, on_dashboard=False)
    track = sources.tracks.add("Catalyst (full album)")
    await _save(
        db,
        soon,
        item(track, starts_at=at(-120), ends_at=at(48)),
        item(sources.tracks.add("Second"), ends_at=at(30)),
    )
    await _save(db, later, item(track, ends_at=at(72)))
    await _save(
        db, queued, item(track, ends_at=at(24)), item(sources.tracks.add(), starts_at=at(200))
    )
    await _save(db, open_ended, item(track, ends_at=at(24)), item(sources.tracks.add()))
    await _save(db, hidden, item(track, ends_at=at(24)))
    found = await _ending(db, soon)
    assert [(each.title, each.last_end) for each in found] == [
        ("Catalyst (full album)", NOW + timedelta(hours=48))
    ]
    for other in (later, queued, open_ended, hidden):
        assert await _ending(db, other) == []
    items = [each for each in await dashboard.ATTENTION(db, None) if each.to.endswith(soon.key)]
    assert [
        (each.key, each.tone, each.what, each.why, each.label, each.to, each.permission)
        for each in items
    ] == [
        (
            f"featured.ending_{soon.key.replace('-', '_')}",
            "info",
            "Catalyst (full album) leaves the Spotlight in 2 days",
            "After Nov 17 the Spotlight is empty on the site unless something else is scheduled.",
            "Schedule the next one",
            f"/admin/featured?slot={soon.key}",
            "featured.placement.manage",
        )
    ]
    empty = await _slot(db, on_dashboard=True)
    assert await _ending(db, empty) == []


async def test_setup_is_done_once_every_slot_has_something_live(
    db: AsyncSession, sources: Sources
) -> None:
    await db.execute(delete(Slot))  # rolled back at the end: only this test's slots
    (step,) = dashboard.SETUP
    assert step.key == "featured.players"
    assert step.title == "Put something in each homepage player"
    assert await step.done(db) is False
    one = await _slot(db)
    two = await _slot(db, ("youtube",))
    await _save(db, one, item(sources.tracks.add()))
    assert await step.done(db) is False
    await _save(db, two, link(starts_at=at(1)))
    assert await step.done(db) is False
    await service.save_placements(db, two.key, two.version, [link()], by=None)
    assert await step.done(db) is True


def test_days_left_counts_whole_days() -> None:
    assert service.days_left(NOW + timedelta(hours=1)) == 1
    assert service.days_left(NOW + timedelta(hours=25)) == 2
    assert service.days_left(NOW + timedelta(hours=48)) == 2
