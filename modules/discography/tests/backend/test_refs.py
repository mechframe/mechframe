"""discography 0.1.2 (`dev plans/contracts/featured.md` §2, "discography
0.1.2"): its two sources for kernel.refs (hook 11), their lines and `live`,
drafts found and picked too, a page at a time newest edit first; and the reads
by id a homepage draws its players from, live ones only, in the order given."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from discography import refs as discography_refs
from discography import service
from discography.models import Release, Track
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import load_module, refs

from ..conftest import make_image, slug

pytestmark = pytest.mark.db
MODULE = Path(__file__).resolve().parents[2]
LINK = "https://soundcloud.com/petrodestroys/catalyst"
RELEASES, TRACKS = discography_refs.REFS


async def _release(db: AsyncSession, title: str = "Catalyst", **fields: Any) -> Release:
    release = await service.create_release(
        db,
        {"title": title, "slug": slug(), "artist_line": "petro and J Tone", "year": 2026, **fields},
        by=None,
    )
    await db.commit()
    return release


async def _track(db: AsyncSession, release: Release, title: str, *, link: bool = True) -> Track:
    track = await service.create_track(db, release.id, title, LINK if link else None, by=None)
    await db.commit()
    return track


async def _publish(db: AsyncSession, release: Release) -> None:
    await service.publish(db, release.id, None, by=None)
    await db.commit()


def test_the_module_gives_its_two_types() -> None:
    found = load_module(MODULE / "module.json")
    assert [(each.type, each.label) for each in found.referable] == [
        ("discography.release", "Albums"),
        ("discography.track", "Tracks"),
    ]
    assert refs.build([found]).keys() == {"discography.release", "discography.track"}


async def test_a_releases_line_and_when_its_live(db: AsyncSession) -> None:
    cover = await make_image(db)
    release = await _release(db, cover_id=str(cover))
    one = await _track(db, release, "Catalyst (full album)")
    await _track(db, release, "No audio yet", link=False)
    draft = (await RELEASES.find(db, [release.id]))[release.id]
    assert (draft.title, draft.line, draft.live, draft.path) == (
        "Catalyst",
        "2026, petro and J Tone, 1 track",
        False,
        None,
    )
    assert draft.image is not None
    assert draft.image.startswith("https://files.music.test/")
    await _publish(db, release)
    live = (await RELEASES.find(db, [release.id]))[release.id]
    assert (live.live, live.path) == (True, f"/music/{release.slug}")
    # Live with no track that plays isn't live for a player.
    await service.remove_track(db, one.id, by=None)
    await db.commit()
    silent = (await RELEASES.find(db, [release.id]))[release.id]
    assert (silent.live, silent.line) == (False, "2026, petro and J Tone, 0 tracks")
    gone = uuid.uuid4()
    assert gone not in await RELEASES.find(db, [release.id, gone])


async def test_a_release_with_no_year_or_artist_says_less(db: AsyncSession) -> None:
    release = await _release(db, "Untitled", artist_line="", year=None)
    await _track(db, release, "One")
    await _track(db, release, "Two")
    found = (await RELEASES.find(db, [release.id]))[release.id]
    assert found.line == "2 tracks"


async def test_a_tracks_line_and_when_its_live(db: AsyncSession) -> None:
    release = await _release(db)
    plays = await _track(db, release, "Gather Around")
    silent = await _track(db, release, "Pray For You", link=False)
    found = await TRACKS.find(db, [plays.id, silent.id])
    assert {each.line for each in found.values()} == {"Catalyst, petro and J Tone"}
    assert (found[plays.id].live, found[silent.id].live) == (False, False)
    await _publish(db, release)
    found = await TRACKS.find(db, [plays.id, silent.id])
    assert (found[plays.id].live, found[plays.id].path) == (
        True,
        f"/music/{release.slug}/{plays.slug}",
    )
    assert (found[silent.id].live, found[silent.id].path) == (False, None)


async def test_the_picker_finds_by_title_drafts_too_newest_edit_first(db: AsyncSession) -> None:
    word = uuid.uuid4().hex[:8]
    older = await _release(db, f"Older {word}")
    newer = await _release(db, f"Newer {word} 100%")
    page = await RELEASES.pick(db, word, cursor=None, limit=1)
    assert [each.id for each in page["items"]] == [newer.id]
    rest = await RELEASES.pick(db, word, cursor=page["next_cursor"], limit=1)
    assert [each.id for each in rest["items"]] == [older.id]
    assert rest["next_cursor"] is None
    # `%` and `_` mean themselves.
    assert [
        each.id for each in (await RELEASES.pick(db, "100%", cursor=None, limit=50))["items"]
    ] == [newer.id]
    track_one = await _track(db, older, f"Hook It Up {word}")
    track_two = await _track(db, newer, f"Hook It Up {word} again")
    picked = await TRACKS.pick(db, f"hook it up {word}", cursor=None, limit=1)
    assert [each.id for each in picked["items"]] == [track_two.id]
    after = await TRACKS.pick(db, f"hook it up {word}", cursor=picked["next_cursor"], limit=1)
    assert [each.id for each in after["items"]] == [track_one.id]
    for wrong in (
        "nope",
        "2026-11-25T00:00:00~" + str(uuid.uuid4()),
        "2026-11-25T00:00:00+00:00~nope",
    ):
        with pytest.raises(ValueError, match=r"isn't a page|badly formed|hexadecimal"):
            await RELEASES.pick(db, None, cursor=wrong, limit=1)


async def test_the_reads_by_id_answer_live_ones_in_the_order_given(db: AsyncSession) -> None:
    catalyst = await _release(db, "Catalyst")
    unified = await _release(db, "Unified Vibration", artist_line="Vibrant Mindz", year=2024)
    draft = await _release(db, "A draft")
    gather = await _track(db, unified, "Gather Around")
    silent = await _track(db, unified, "Pray For You", link=False)
    hook = await _track(db, unified, "Hook It Up")
    full = await _track(db, catalyst, "Catalyst (full album)")
    hidden = await _track(db, draft, "Not yet")
    await _publish(db, catalyst)
    await _publish(db, unified)
    found = await service.releases_by_id(db, [unified.id, draft.id, catalyst.id, unified.id])
    assert [each["title"] for each in found] == ["Unified Vibration", "Catalyst"]
    assert await service.releases_by_id(db, [unified.id, catalyst.id], kind="ep") == []
    tracks = await service.tracks_by_id(
        db, [hook.id, hidden.id, silent.id, full.id, gather.id, uuid.uuid4()]
    )
    assert [(each["title"], each["number"]) for each in tracks] == [
        ("Hook It Up", 2),
        ("Catalyst (full album)", 1),
        ("Gather Around", 1),
    ]
    assert tracks[0]["release"] == {
        "title": "Unified Vibration",
        "slug": unified.slug,
        "artist_line": "Vibrant Mindz",
        "cover": None,
        "path": f"/music/{unified.slug}",
    }
    assert await service.tracks_by_id(db, []) == []
