"""discography's rules on the database (`dev plans/contracts/discography.md`
§2, §3, §7): releases and their moves, saves that cross, what plays and what's
hidden, credits and the people they name, links, the job, the public reads,
the server copy, search, the announcement, the seed and the dashboard."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from discography import dashboard, jobs, public, service
from discography import events as discography_events
from discography.models import Person, Release, Track
from discography.seed import _NAMESPACE, RELEASES
from discography.server_copy import PAGES, iso_duration
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, Problem, clock, lifecycle, load_module, server_copy
from kernel import events as kernel_events
from kernel import seed as seeding
from kernel import storage as kernel_storage
from kernel.config import reset_config
from kernel.models import SearchDocument

from ..conftest import make_image, master, slug
from .conftest import Store

pytestmark = pytest.mark.db
MODULE = Path(__file__).resolve().parents[2]
LINK = "https://soundcloud.com/petrodestroys/catalyst"
#: Taken as the module is read, before any fixture puts a stand-in in its place.
_REAL_PUBLIC_URL = kernel_storage.public_url


async def _release(db: AsyncSession, **fields: Any) -> Release:
    release = await service.create_release(
        db, {"title": "An album", "slug": slug(), "artist_line": "The band", **fields}, by=None
    )
    await db.commit()
    return release


async def _live(db: AsyncSession, **fields: Any) -> Release:
    release = await _release(db, **fields)
    await service.publish(db, release.id, None, by=None)
    await db.commit()
    return release


async def _linked(db: AsyncSession, release: Release, title: str = "A track") -> Track:
    track = await service.create_track(db, release.id, title, LINK, by=None)
    await db.commit()
    return track


async def _uploaded(db: AsyncSession, release: Release, data: bytes | None = None) -> Track:
    body = data or master()
    track = await service.upload_track(
        db, release.id, io.BytesIO(body), len(body), "Night Drive.wav", by=None
    )
    await db.commit()
    return track


async def _process(database: Database, track: Track) -> None:
    ctx = SimpleNamespace(sessions=database.sessions)
    await jobs.process_track.run(  # type: ignore[arg-type]
        ctx, {"track_id": str(track.id), "master_key": track.master_key}
    )


# --- releases and their addresses ------------------------------------------------------------


async def test_a_release_without_a_slug_takes_one_from_its_title_numbered_when_taken(
    db: AsyncSession,
) -> None:
    title = f"Unified Vibration {uuid.uuid4().hex[:6]}"
    first = await service.create_release(db, {"title": title}, by=None)
    second = await service.create_release(db, {"title": title}, by=None)
    await db.commit()
    assert second.slug == f"{first.slug}-2"
    assert first.status == lifecycle.DRAFT


async def test_a_stale_save_is_refused_with_the_release_as_it_is_now(db: AsyncSession) -> None:
    release = await _release(db)
    await service.change_release(db, release.id, 1, {"title": "Renamed"}, by=None)
    await db.commit()
    with pytest.raises(Problem) as refused:
        await service.change_release(db, release.id, 1, {"title": "Again"}, by=None)
    await db.rollback()
    assert refused.value.status == 409
    assert refused.value.code == "discography.changed"


async def test_a_live_release_that_moves_leaves_its_old_addresses_its_tracks_too(
    db: AsyncSession,
) -> None:
    release = await _live(db)
    track = await _linked(db, release, "Night Drive")
    old = release.slug
    await service.change_release(db, release.id, release.version, {"slug": slug()}, by=None)
    await db.commit()
    assert await service.live(db, old) == service.release_path(release)
    assert await service.live_track(db, old, track.slug) == service.track_path(release, track)
    assert await service.live(db, f"nothing-{uuid.uuid4().hex[:6]}") is None


async def test_a_draft_answers_nothing(db: AsyncSession) -> None:
    release = await _release(db)
    await _linked(db, release)
    assert await service.live(db, release.slug) is None
    assert await public.release(db, release.slug) is None


# --- what plays ------------------------------------------------------------------------------


async def test_a_track_that_cant_play_is_hidden_from_every_public_answer(
    db: AsyncSession,
) -> None:
    release = await _live(db)
    playing = await _linked(db, release, "Plays")
    silent = await service.create_track(db, release.id, "Pray For You", None, by=None)
    await db.commit()
    shown = await service.shown(db, release)
    assert [line["title"] for line in shown["tracks"]] == ["Plays"]
    assert shown["track_count"] == 1
    assert await service.live_track(db, release.slug, silent.slug) is None
    cards = await public.track_cards(db, [playing.id, silent.id])
    assert list(cards) == [playing.id]
    [row] = [each for each in await service.every_release(db) if each["id"] == str(release.id)]
    assert (row["track_count"], row["unplayable"]) == (2, 1)


async def test_a_soundcloud_track_or_playlist_is_taken_and_anything_else_refused() -> None:
    assert service.soundcloud_link("https://m.soundcloud.com/petrodestroys/catalyst/") == (
        LINK,
        "track",
    )
    assert service.soundcloud_link("https://soundcloud.com/petrodestroys/sets/catalyst")[1] == "set"
    for wrong in ("https://soundcloud.com/petrodestroys", "https://open.spotify.com/track/1"):
        with pytest.raises(Problem) as refused:
            service.soundcloud_link(wrong)
        assert refused.value.code == "discography.not_soundcloud"


async def test_an_upload_is_processed_into_a_stream_that_plays_first(
    db: AsyncSession, database: Database, store: Store, said: list[tuple[str, Any]]
) -> None:
    release = await _live(db)
    track = await _uploaded(db, release, master(3.0))
    assert track.title == "Night Drive"
    assert track.audio_state == "processing"
    assert store.keys(public=False) == [track.master_key]
    await service.change_track(db, track.id, track.version, {"soundcloud_url": LINK}, by=None)
    await db.commit()

    await _process(database, track)

    await db.refresh(track)
    assert (track.audio_state, track.processing_percent, track.audio_error) == ("ready", 100, None)
    assert abs((track.duration_ms or 0) - 3000) <= 50
    assert len(track.peaks or []) == 1000
    [stream] = store.keys(public=True)
    assert stream == track.stream_key
    assert stream.endswith(".mp3")
    assert stream.startswith("discography/stream/")
    assert str(track.id) not in stream
    assert service.plays_from(track) == "upload"  # the upload first, the link behind it
    assert ("discography.track.processed", track.id) in [
        (name, getattr(payload, "track_id", None)) for name, payload in said
    ]


async def test_a_master_replaced_while_its_job_runs_throws_the_result_away(
    db: AsyncSession, database: Database, store: Store
) -> None:
    release = await _release(db)
    track = await _uploaded(db, release)
    first = track.master_key
    body = master(2.0)
    await service.replace_audio(db, track.id, io.BytesIO(body), len(body), "v2.wav", by=None)
    await db.commit()
    ctx = SimpleNamespace(sessions=database.sessions)
    await jobs.process_track.run(ctx, {"track_id": str(track.id), "master_key": first})  # type: ignore[arg-type]
    await db.refresh(track)
    assert track.audio_state == "processing"
    assert track.stream_key is None


async def test_a_master_that_wont_read_to_its_end_fails_with_words_for_the_board(
    db: AsyncSession, database: Database, store: Store
) -> None:
    release = await _release(db)
    track = await _uploaded(db, release)
    assert track.master_key is not None
    store.files[(track.master_key, False)] = b"not audio any more"
    await _process(database, track)
    await db.refresh(track)
    assert (track.audio_state, track.audio_error) == ("failed", "discography.not_audio")
    shown = await service.full_track(db, track)
    assert "Export it again" in shown["audio"]["error_words"]
    retried = await service.retry(db, track.id, by=None)
    assert retried.audio_state == "processing"
    await db.rollback()


@pytest.mark.parametrize(
    ("data", "size", "code"),
    [
        (b"x" * 100, service.MAX_MASTER_BYTES + 1, "discography.too_large"),
        (b"<html>no</html>" * 100, 1500, "discography.not_audio"),
    ],
)
async def test_an_upload_that_cant_be_taken_is_refused(
    db: AsyncSession, store: Store, data: bytes, size: int, code: str
) -> None:
    release = await _release(db)
    with pytest.raises(Problem) as refused:
        await service.upload_track(db, release.id, io.BytesIO(data), size, "x.wav", by=None)
    await db.rollback()
    assert refused.value.code == code


async def test_an_upload_with_storage_off_says_what_to_do(db: AsyncSession, store: Store) -> None:
    store.on = False
    release = await _release(db)
    body = master()
    with pytest.raises(Problem) as refused:
        await service.upload_track(db, release.id, io.BytesIO(body), len(body), "a.wav", by=None)
    await db.rollback()
    assert (refused.value.status, refused.value.code) == (503, "discography.storage_off")


async def test_removing_a_track_renumbers_the_rest_and_lets_its_files_go(
    db: AsyncSession, store: Store
) -> None:
    release = await _release(db)
    first = await _uploaded(db, release)
    second = await _linked(db, release, "Second")
    await service.remove_track(db, first.id, by=None)
    await db.commit()
    await db.refresh(second)
    assert second.position == 0
    queued = await db.scalar(
        text(
            "SELECT count(*) FROM kernel_job WHERE name = 'discography.delete_files' "
            "AND payload::text LIKE :key"
        ),
        {"key": f"%{first.master_key}%"},
    )
    assert queued == 1


async def test_tracks_take_the_order_a_save_sends(db: AsyncSession) -> None:
    release = await _release(db)
    one, two, three = [await _linked(db, release, name) for name in ("One", "Two", "Three")]
    await service.change_release(
        db,
        release.id,
        release.version,
        {"track_ids": [str(three.id), str(one.id), str(two.id)]},
        by=None,
    )
    await db.commit()
    tracks = (await service.tracks_of(db, [release.id]))[release.id]
    assert [track.title for track in tracks] == ["Three", "One", "Two"]
    with pytest.raises(Problem) as refused:
        await service.change_release(
            db, release.id, release.version, {"track_ids": [str(one.id)]}, by=None
        )
    await db.rollback()
    assert refused.value.code == "discography.tracks_changed"


# --- credits, people and links ---------------------------------------------------------------


async def _role(db: AsyncSession, name: str) -> str:
    found = await db.scalar(
        text("SELECT id FROM discography_role WHERE name = :name"), {"name": name}
    )
    return str(found)


async def test_a_name_is_one_person_however_often_its_credited_and_goes_with_its_last_credit(
    db: AsyncSession,
) -> None:
    name = f"Rob Beaton {uuid.uuid4().hex[:6]}"
    mastered = await _role(db, "Mastered by")
    first, second = await _release(db), await _release(db)
    for release in (first, second):
        await service.change_release(
            db,
            release.id,
            release.version,
            {"credits": [{"role_id": mastered, "name": name}]},
            by=None,
        )
    await service.change_release(
        db,
        first.id,
        first.version,
        {"credits": [{"role_id": mastered, "name": name.upper()}]},
        by=None,
    )
    await db.commit()
    count = await db.scalar(select(func.count()).where(func.lower(Person.name) == name.lower()))
    assert count == 1
    for release in (first, second):
        await service.change_release(db, release.id, release.version, {"credits": []}, by=None)
    await db.commit()
    assert await db.scalar(select(func.count()).where(func.lower(Person.name) == name.lower())) == 0


async def test_a_role_a_credit_names_cant_go(db: AsyncSession) -> None:
    roles = await service.every_role(db)
    artist = next(each for each in roles if each["name"] == "Artist")
    release = await _release(db)
    await service.change_release(
        db,
        release.id,
        release.version,
        {"credits": [{"role_id": artist["id"], "name": "J Tone"}]},
        by=None,
    )
    await db.commit()
    kept = [
        {"id": each["id"], "name": each["name"]} for each in roles if each["id"] != artist["id"]
    ]
    with pytest.raises(Problem) as refused:
        await service.put_roles(db, kept, by=None)
    await db.rollback()
    assert refused.value.code == "discography.role_in_use"


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://open.spotify.com/album/abc", "spotify"),
        ("https://music.apple.com/us/album/x/1", "apple-music"),
        ("https://music.youtube.com/playlist?list=1", "youtube-music"),
        ("https://vibrantmindz.bandcamp.com/album/x", "bandcamp"),
    ],
)
def test_a_links_platform_is_read_from_its_host(url: str, platform: str) -> None:
    assert service.platform_of(url) == (platform, url)


@pytest.mark.parametrize("url", ["http://open.spotify.com/x", "https://example.com/album"])
def test_a_link_off_the_list_is_refused(url: str) -> None:
    with pytest.raises(Problem):
        service.platform_of(url)


# --- the public reads and the server copy ----------------------------------------------------


async def test_a_live_release_answers_its_page_and_json_ld(
    db: AsyncSession, database: Database, store: Store
) -> None:
    cover = await make_image(db)
    release = await _live(db, cover_id=str(cover), year=2024, credit_line="Produced by us.")
    track = await _uploaded(db, release, master(2.0))
    await _process(database, track)
    await db.refresh(track)  # the job wrote in its own session
    await service.change_track(
        db,
        track.id,
        (await service.get_track(db, track.id)).version,
        {"explicit": True, "lyrics": "Line one"},
        by=None,
    )
    await service.change_release(
        db, release.id, release.version, {"links": ["https://open.spotify.com/album/abc"]}, by=None
    )
    await db.commit()

    shown = await public.release(db, release.slug)
    assert shown is not None
    assert not isinstance(shown, type(None))
    assert shown.model_dump()["explicit"] is True
    page = await PAGES.page(db, service.release_path(release), {"release": release.slug})  # type: ignore[union-attr]
    assert isinstance(page, server_copy.Page)
    [album] = page.data
    assert album["@type"] == "MusicAlbum"
    assert album["datePublished"] == "2024"
    assert album["albumReleaseType"] == "https://schema.org/AlbumRelease"
    [item] = album["track"]["itemListElement"]
    assert item["item"]["@type"] == "MusicRecording"
    assert item["item"]["duration"] == "PT2S"
    assert "discography/stream" not in str(page.data)  # no stream address for crawlers

    found = await PAGES.page(  # type: ignore[union-attr]
        db, service.track_path(release, track), {"release": release.slug, "track": track.slug}
    )
    assert isinstance(found, server_copy.Page)
    assert found.data[0]["@type"] == "MusicRecording"
    assert found.data[0]["inAlbum"]["name"] == release.title


def test_a_duration_in_iso_8601() -> None:
    assert iso_duration(221_400) == "PT3M41S"
    assert iso_duration(3_700_000) == "PT1H1M40S"
    assert iso_duration(None) is None


async def test_search_finds_a_release_by_a_tracks_credit(db: AsyncSession) -> None:
    release = await _live(db)
    track = await _linked(db, release)
    name = f"Moya {uuid.uuid4().hex[:8]}"
    await service.change_track(
        db,
        track.id,
        track.version,
        {"credits": [{"role_id": await _role(db, "Featuring"), "name": name}]},
        by=None,
    )
    await db.commit()
    document = await db.scalar(
        select(SearchDocument).where(SearchDocument.content_id == release.id)
    )
    assert document is not None
    assert name in document.body


async def test_a_release_is_announced_once(
    db: AsyncSession, database: Database, said: list[tuple[str, Any]]
) -> None:
    release = await _live(db)
    ctx = SimpleNamespace(sessions=database.sessions)
    heard = kernel_events.Event(
        uuid.uuid4(),
        "kernel.content.published",
        1,
        clock.now(),
        {"type": "discography.release", "id": str(release.id)},
    )
    await discography_events._announce(ctx, heard)  # type: ignore[arg-type]
    await discography_events._announce(ctx, heard)  # type: ignore[arg-type]
    assert [name for name, _ in said if name == "discography.release.published"] == [
        "discography.release.published"
    ]


# --- the hooks -------------------------------------------------------------------------------


async def test_the_dashboard_says_a_live_track_cant_play(db: AsyncSession) -> None:
    release = await _live(db)
    await service.create_track(db, release.id, "Pray For You", None, by=None)
    await db.commit()
    items = await dashboard.ATTENTION(db, None)
    assert any(item.key == "discography.cant_play" for item in items)


_STORAGE = {
    "STORAGE_ENDPOINT_URL": "https://r2.mechframe.test",
    "STORAGE_ACCESS_KEY_ID": "music-key-id-AKIA0000",
    "STORAGE_SECRET_ACCESS_KEY": "music-secret-do-not-print",
    "STORAGE_BUCKET": "music-private",
    "STORAGE_PUBLIC_BUCKET": "music-public",
    "STORAGE_PUBLIC_URL": "https://files.mechframe.test",
}


async def test_the_setup_step_is_done_once_both_buckets_can_be_used(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The real address, not the one the autouse fixture gives every other test.
    monkeypatch.setattr(kernel_storage, "public_url", _REAL_PUBLIC_URL)
    before = {name: os.environ.get(name) for name in _STORAGE}
    [step] = dashboard.SETUP

    async def done(values: dict[str, str]) -> bool:
        for name in _STORAGE:
            monkeypatch.delenv(name, raising=False)
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        reset_config()
        kernel_storage._client.cache_clear()
        return bool(await step.done(db))

    try:
        assert await done({}) is False
        assert await done({k: v for k, v in _STORAGE.items() if "PUBLIC" not in k}) is False
        assert await done({k: v for k, v in _STORAGE.items() if k != "STORAGE_BUCKET"}) is False
        assert await done(_STORAGE) is True
    finally:
        for name, value in before.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        reset_config()
        kernel_storage._client.cache_clear()


async def test_the_seed_twice_gives_the_same(db: AsyncSession, store: Store) -> None:
    discography = load_module(MODULE / "module.json")
    allowed = {"MECHFRAME_ALLOW_SEED": "1"}
    ids = [uuid.uuid5(_NAMESPACE, each[0]) for each in RELEASES]
    await seeding.run(db, [discography], environ=allowed)
    first = {
        row.id: (row.slug, row.status, row.version)
        for row in await db.scalars(select(Release).where(Release.id.in_(ids)))
    }
    tracks = await db.scalar(
        select(func.count()).select_from(Track).where(Track.release_id.in_(ids))
    )
    await seeding.run(db, [discography], environ=allowed)
    again = {
        row.id: (row.slug, row.status, row.version)
        for row in await db.scalars(select(Release).where(Release.id.in_(ids)))
    }
    assert first == again
    assert len(first) == 3
    assert tracks == 4
    album = await db.get(Release, ids[0])
    assert album is not None
    assert album.status == lifecycle.PUBLISHED
