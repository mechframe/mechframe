"""discography's rules on the database (`dev plans/contracts/discography.md`
§2, §3, §7): releases and their moves, saves that cross, what plays and what's
hidden, credits and the people they name, links, the job, the public reads,
the server copy, search, the announcement, the seed and the dashboard."""

from __future__ import annotations

import asyncio
import io
import os
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, BinaryIO

import pytest
from discography import audio, dashboard, jobs, public, service
from discography import events as discography_events
from discography import seed as discography_seed
from discography.models import Credit, Person, Release, Track
from discography.schemas import Settings
from discography.seed import _NAMESPACE, RELEASES
from discography.server_copy import PAGES, iso_duration
from sqlalchemy import event as sa_event
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
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


async def _process(database: Database, track: Track, try_number: int = 1) -> None:
    ctx = SimpleNamespace(sessions=database.sessions, try_number=try_number)
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


async def test_a_replaced_upload_plays_its_old_stream_until_the_new_one_is_ready(
    db: AsyncSession, database: Database, store: Store
) -> None:
    """Codex on #145: a replace or a failed one never takes a stream off the site."""
    release = await _live(db)
    track = await _uploaded(db, release, master(2.0))
    await _process(database, track)
    await db.refresh(track)
    first = track.stream_key
    assert first is not None
    body = master(3.0)
    await service.replace_audio(db, track.id, io.BytesIO(body), len(body), "v2.wav", by=None)
    await db.commit()
    assert track.audio_state == "processing"

    def heard() -> list[str | None]:
        return [line["stream_url"] for line in shown["tracks"]]

    shown = await service.shown(db, release)
    assert [url and url.endswith(first) for url in heard()] == [True]
    assert list(await public.track_cards(db, [track.id])) == [track.id]
    assert isinstance(await service.live_track(db, release.slug, track.slug), tuple)

    assert track.master_key is not None
    store.files[(track.master_key, False)] = b"not audio any more"
    await _process(database, track)
    await db.refresh(track)
    assert track.audio_state == "failed"
    shown = await service.shown(db, release)
    assert [url and url.endswith(first) for url in heard()] == [True]


async def test_a_track_renamed_then_its_release_moved_goes_straight_to_where_it_is(
    db: AsyncSession,
) -> None:
    """Codex on #145: /music/a/x, renamed to y and then moved to b, answers b/y."""
    release = await _live(db)
    track = await _linked(db, release, "Night Drive")
    a, x = release.slug, track.slug
    await service.change_track(db, track.id, track.version, {"slug": "night-ride"}, by=None)
    await db.commit()
    await service.change_release(db, release.id, release.version, {"slug": slug()}, by=None)
    await db.commit()
    await db.refresh(release)
    await db.refresh(track)
    now = service.track_path(release, track)
    assert await service.live_track(db, a, x) == now
    assert await service.live_track(db, a, "night-ride") == now
    added = await _linked(db, release, "Added Later")
    assert await service.live_track(db, a, added.slug) == service.track_path(release, added)


async def test_the_label_setting_covers_a_releases_tracklist_too(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex on #145: with the label off, no track in a tracklist says explicit."""
    release = await _live(db)
    track = await _linked(db, release)
    await service.change_track(db, track.id, track.version, {"explicit": True}, by=None)
    await db.commit()
    assert [line["explicit"] for line in (await service.shown(db, release))["tracks"]] == [True]

    async def label_off(db: AsyncSession) -> Settings:
        return Settings(show_explicit_badge=False)

    monkeypatch.setattr(service, "settings_of", label_off)
    shown = await service.shown(db, release)
    assert (shown["explicit"], [line["explicit"] for line in shown["tracks"]]) == (False, [False])


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


async def test_a_master_replaced_after_its_job_read_it_never_publishes_the_old_result(
    db: AsyncSession,
    database: Database,
    store: Store,
    said: list[tuple[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CodeRabbit on #145 (0.1.3): the old job has read its master and is encoding
    when the replacement commits; it finishes, and the track never takes its result.
    The test above covers a job that was still queued."""
    release = await _release(db)
    track = await _uploaded(db, release)
    first = track.master_key
    real = audio.make_stream
    reading, resume = threading.Event(), threading.Event()

    def paused(source: BinaryIO, into: BinaryIO, *, kbps: int, progress: Any) -> audio.Made:
        reading.set()  # the master is read in, and the encoder has it
        assert resume.wait(5)
        return real(source, into, kbps=kbps, progress=progress)

    monkeypatch.setattr(audio, "make_stream", paused)
    ctx = SimpleNamespace(sessions=database.sessions, try_number=1)
    old_job = asyncio.create_task(
        jobs.process_track.run(ctx, {"track_id": str(track.id), "master_key": first})  # type: ignore[arg-type]
    )
    assert await asyncio.to_thread(reading.wait, 5)
    body = master(2.0)
    await service.replace_audio(db, track.id, io.BytesIO(body), len(body), "v2.wav", by=None)
    await db.commit()
    resume.set()
    await old_job

    await db.refresh(track)
    assert track.master_key != first
    assert (track.audio_state, track.stream_key) == ("processing", None)
    assert "discography.track.processed" not in [name for name, _ in said]

    monkeypatch.setattr(audio, "make_stream", real)
    await _process(database, track)  # the new master's own job
    await db.refresh(track)
    assert track.audio_state == "ready"
    assert track.stream_key is not None


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


async def _taken_back() -> None:
    """Lets the masters a transaction gave up be taken back out of the bucket."""
    for _ in range(5):
        await asyncio.sleep(0)
    while service._TAKING_BACK:
        await asyncio.gather(*list(service._TAKING_BACK))


async def test_an_upload_that_doesnt_commit_takes_its_master_back(
    db: AsyncSession, store: Store
) -> None:
    """CodeRabbit on #145 (0.1.3): a master the request never committed stays in no bucket."""
    release = await _release(db)
    body = master()
    await service.upload_track(db, release.id, io.BytesIO(body), len(body), "a.wav", by=None)
    assert len(store.keys(public=False)) == 1
    await db.rollback()
    await _taken_back()

    assert store.keys(public=False) == []


async def test_a_replace_that_doesnt_commit_takes_its_new_master_back_and_keeps_the_old(
    db: AsyncSession, store: Store
) -> None:
    release = await _release(db)
    track = await _uploaded(db, release)
    await _taken_back()
    first = track.master_key
    body = master(2.0)
    await service.replace_audio(db, track.id, io.BytesIO(body), len(body), "v2.wav", by=None)
    await db.rollback()
    await _taken_back()

    assert store.keys(public=False) == [first]


async def test_two_uploads_in_one_transaction_go_with_it_whichever_way_it_ends(
    db: AsyncSession, store: Store
) -> None:
    """Each upload's insert is a savepoint, whose release isn't the transaction's commit."""
    release_id = (await _release(db)).id  # the rollback expires the row
    for name in ("a.wav", "b.wav"):
        body = master()
        await service.upload_track(db, release_id, io.BytesIO(body), len(body), name, by=None)
    await db.rollback()
    await _taken_back()
    assert store.keys(public=False) == []

    kept = []
    for name in ("a.wav", "b.wav"):
        body = master()
        track = await service.upload_track(
            db, release_id, io.BytesIO(body), len(body), name, by=None
        )
        kept.append(track.master_key)
    await db.commit()
    await _taken_back()
    assert store.keys(public=False) == sorted(kept)


async def test_a_session_closed_without_a_commit_takes_its_master_back(
    database: Database, db: AsyncSession, store: Store
) -> None:
    """The kernel's get_db closes the session; no rollback is called."""
    release = await _release(db)
    async with database.sessions() as session:
        body = master()
        await service.upload_track(
            session, release.id, io.BytesIO(body), len(body), "a.wav", by=None
        )
    await _taken_back()

    assert store.keys(public=False) == []


async def test_a_master_a_track_names_is_never_taken_back(
    database: Database, db: AsyncSession, store: Store
) -> None:
    """A commit whose reply was lost may have landed: its master stays while a track names it."""
    release = await _release(db)
    track = await _uploaded(db, release)
    assert track.master_key is not None

    await service._take_back(database.engine, track.master_key)

    assert store.keys(public=False) == [track.master_key]


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


async def _credited_release(db: AsyncSession, tag: str) -> Release:
    """A live release with a playable track, a silent one and a credit on each."""
    release = await _live(db)
    track = await _linked(db, release, f"Lit {tag}")
    silent = await service.create_track(db, release.id, f"Hush {tag}", None, by=None)
    await db.commit()
    role = await _role(db, "Featuring")
    for each in (track, silent):
        await service.change_track(
            db,
            each.id,
            each.version,
            {
                "credits": [{"role_id": role, "name": f"{each.title} singer"}],
                "lyrics": f"words {tag}",
            },
            by=None,
        )
        await db.commit()
    return release


async def test_a_reindex_reads_a_pages_tracks_credits_and_settings_once(
    db: AsyncSession, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CodeRabbit on #145 (0.1.3): a page of releases is three reads, not three a release,
    and each document is what one release's own read gives."""
    from discography.search import Releases

    monkeypatch.setattr("discography.search.PAGE", 100_000)  # every release in one page
    said: list[str] = []

    def heard(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        said.append(statement)

    async def reindexed() -> tuple[int, list[Any]]:
        said.clear()
        sa_event.listen(database.engine.sync_engine, "before_cursor_execute", heard)
        try:
            found = [each async for each in Releases().documents(db)]
        finally:
            sa_event.remove(database.engine.sync_engine, "before_cursor_execute", heard)
        return len(said), found

    await _credited_release(db, "one")
    before, _ = await reindexed()
    tag = uuid.uuid4().hex[:8]
    made = [await _credited_release(db, f"{tag}{n}") for n in range(3)]
    after, found = await reindexed()

    assert after == before
    by_id = {each.id: each for each in found}
    for release in made:
        assert by_id[release.id] == await service.document(db, release)
        assert f"Lit {tag}" in by_id[release.id].body
        assert f"Hush {tag}" not in by_id[release.id].body  # nor its credit: it can't play


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
    tracks = set(await db.scalars(select(Track.id).where(Track.release_id.in_(ids))))
    await seeding.run(db, [discography], environ=allowed)
    again = {
        row.id: (row.slug, row.status, row.version)
        for row in await db.scalars(select(Release).where(Release.id.in_(ids)))
    }
    assert first == again
    assert len(first) == 3
    assert len(tracks) == 4
    # Read again after the second run: no track added, none made anew (CodeRabbit on #145).
    assert set(await db.scalars(select(Track.id).where(Track.release_id.in_(ids)))) == tracks
    album = await db.get(Release, ids[0])
    assert album is not None
    assert album.status == lifecycle.PUBLISHED


# --- CodeRabbit on #145 ----------------------------------------------------------------------


async def test_a_release_takes_no_more_tracks_than_a_save_can_order(
    db: AsyncSession, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A save sends every track's id, at most MAX_TRACKS of them: adding one more is refused."""
    monkeypatch.setattr(service, "MAX_TRACKS", 2)
    release = await _release(db)
    release_id = release.id  # a rollback expires the row
    await _linked(db, release, "One")
    await _linked(db, release, "Two")
    with pytest.raises(Problem) as refused:
        await service.create_track(db, release_id, "Three", LINK, by=None)
    await db.rollback()
    assert (refused.value.status, refused.value.code) == (409, "discography.too_many_tracks")
    body = master(1.0)
    with pytest.raises(Problem) as refused:
        await service.upload_track(db, release_id, io.BytesIO(body), len(body), "x.wav", by=None)
    await db.rollback()
    assert refused.value.code == "discography.too_many_tracks"
    assert store.keys(public=False) == []  # refused before the master is kept


async def test_a_role_sent_twice_by_its_id_is_refused(db: AsyncSession) -> None:
    roles = await service.every_role(db)
    first = str(roles[0]["id"])
    items = [
        {"id": first, "name": "One name"},
        {"id": first.upper(), "name": "Another name"},
        *({"id": each["id"], "name": each["name"]} for each in roles[1:]),
    ]
    with pytest.raises(Problem) as refused:
        await service.put_roles(db, items, by=None)
    await db.rollback()
    assert (refused.value.status, refused.value.code) == (422, "discography.role_twice")


async def test_a_link_longer_than_a_row_holds_is_a_field_error(db: AsyncSession) -> None:
    release = await _release(db)
    long = "https://open.spotify.com/album/" + "a" * 500
    with pytest.raises(Problem) as refused:
        await service.change_release(db, release.id, release.version, {"links": [long]}, by=None)
    await db.rollback()
    assert (refused.value.status, refused.value.code) == (422, "discography.not_a_link")
    assert "links" in refused.value.errors


async def test_a_tracks_page_that_isnt_ascii_digits_is_a_field_error(db: AsyncSession) -> None:
    with pytest.raises(Problem) as refused:
        await service.every_track(db, q=None, show="all", cursor="²")
    assert refused.value.status == 422


async def test_a_persons_credits_are_told_apart_by_release_not_title(db: AsyncSession) -> None:
    name = f"Ada {uuid.uuid4().hex[:6]}"
    title = f"Greatest Hits {uuid.uuid4().hex[:6]}"
    one, two = await _release(db, title=title), await _release(db, title=title)
    for release, role in ((one, "Artist"), (two, "Mastered by")):
        await service.change_release(
            db,
            release.id,
            release.version,
            {"credits": [{"role_id": await _role(db, role), "name": name}]},
            by=None,
        )
    await db.commit()
    [person] = [each for each in (await service.every_person(db))["items"] if each["name"] == name]
    assert person["credited_for"] in (
        f"Artist, {title}; Mastered by, {title}",
        f"Mastered by, {title}; Artist, {title}",
    )


async def _until_blocked(probe: AsyncSession, actor: int, holder: int) -> None:
    """Until the holder's backend blocks the actor's, for 5 seconds at most
    (CodeRabbit on #145: a fixed sleep, or any session waiting, can probe before
    the act gets to the release)."""
    for _ in range(100):
        blocked = await probe.scalar(
            text("SELECT CAST(:holder AS integer) = ANY(pg_blocking_pids(:actor))"),
            {"holder": holder, "actor": actor},
        )
        await probe.rollback()
        if blocked:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("The act never waited on the release's lock.")


async def _track_free_while_it_waits(
    database: Database, release_id: uuid.UUID, track_id: uuid.UUID, act: Any
) -> bool:
    """With the release held, `act` runs until it waits on the release: is the track
    still free then? A reorder holds the release, then its tracks, so an act that
    takes them the other way round can deadlock with it."""
    async with database.sessions() as holder:
        await holder.execute(select(Release.id).where(Release.id == release_id).with_for_update())
        holder_pid = int(await holder.scalar(text("SELECT pg_backend_pid()")) or 0)
        async with database.sessions() as actor:
            # Its transaction holds this one connection to the end: the act runs on it.
            actor_pid = int(await actor.scalar(text("SELECT pg_backend_pid()")) or 0)
            task = asyncio.ensure_future(act(actor))
            async with database.sessions() as probe:
                await _until_blocked(probe, actor_pid, holder_pid)
                try:
                    await probe.execute(
                        text("SELECT 1 FROM discography_track WHERE id = :id FOR UPDATE NOWAIT"),
                        {"id": track_id},
                    )
                    free = True
                except DBAPIError:
                    free = False
                await probe.rollback()
            await holder.rollback()
            await task
            await actor.rollback()
    return free


async def test_deleting_a_track_waits_for_its_release_before_it_holds_the_track(
    db: AsyncSession, database: Database
) -> None:
    release = await _release(db)
    track = await _linked(db, release)
    assert await _track_free_while_it_waits(
        database,
        release.id,
        track.id,
        lambda actor: service.remove_track(actor, track.id, by=None),
    )


async def test_a_tracks_save_waits_for_its_release_before_it_holds_the_track(
    db: AsyncSession, database: Database
) -> None:
    """CodeRabbit on #145: a new address on a live release writes a move, which reads the
    release: the save holds it first, as a delete does."""
    release = await _live(db)
    track = await _linked(db, release)
    version = track.version
    assert await _track_free_while_it_waits(
        database,
        release.id,
        track.id,
        lambda actor: service.change_track(actor, track.id, version, {"slug": slug()}, by=None),
    )


async def test_a_tracks_old_address_never_lands_on_another_track(db: AsyncSession) -> None:
    """/music/a/x, renamed to y, moved to b, with a new x on b: once y can't play, a/x is
    gone, not the new x."""
    release = await _live(db)
    track = await _linked(db, release, "Night Drive")
    a, x = release.slug, track.slug
    await service.change_track(db, track.id, track.version, {"slug": "night-ride"}, by=None)
    await db.commit()
    await service.change_release(db, release.id, release.version, {"slug": slug()}, by=None)
    await db.commit()
    await db.refresh(release)
    await db.refresh(track)
    newer = await _linked(db, release, "Night Drive")
    assert newer.slug == x
    await service.change_track(db, track.id, track.version, {"soundcloud_url": None}, by=None)
    await db.commit()
    assert await service.live_track(db, a, x) is None


async def test_a_null_explicit_leaves_the_track_as_it_was(db: AsyncSession) -> None:
    release = await _release(db)
    track = await _linked(db, release)
    track = await service.change_track(db, track.id, track.version, {"explicit": True}, by=None)
    await db.commit()
    saved = await service.change_track(
        db, track.id, track.version, {"explicit": None, "title": "Renamed"}, by=None
    )
    await db.commit()
    assert (saved.explicit, saved.title) == (True, "Renamed")  # not reset to False


async def test_the_seed_credits_a_name_thats_there_under_another_id(db: AsyncSession) -> None:
    name = f"Ada {uuid.uuid4().hex[:6]}"
    there_id = uuid.uuid4()  # a rollback expires the row
    there = Person(
        id=there_id,
        version=1,
        name=name.upper(),
        profile="unlinked",
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    db.add(there)
    release = await _release(db)
    ctx = SimpleNamespace(now=clock.now())
    await discography_seed._credit(db, ctx, name, "Artist", release_id=release.id)  # type: ignore[arg-type]
    await db.flush()
    credited = await db.scalar(select(Credit.person_id).where(Credit.release_id == release.id))
    await db.rollback()
    assert credited == there_id


async def test_a_stream_that_cant_be_stored_on_the_last_try_fails_the_track(
    db: AsyncSession, database: Database, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = await _release(db)
    track = await _uploaded(db, release, master(1.0))

    async def down(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("storage is down")

    monkeypatch.setattr(kernel_storage, "put", down)
    with pytest.raises(RuntimeError):
        await _process(database, track, try_number=1)
    await db.refresh(track)
    assert track.audio_state == "processing"  # a try is left: it runs again
    with pytest.raises(RuntimeError):
        await _process(database, track, try_number=jobs.TRIES)
    await db.refresh(track)
    assert (track.audio_state, track.audio_error) == ("failed", "discography.process_failed")
    words = (await service.full_track(db, track))["audio"]["error_words"]
    assert words
    assert "Try again" in words


async def test_a_stream_whose_track_cant_be_saved_is_taken_back_out(
    db: AsyncSession, database: Database, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = await _release(db)
    track = await _uploaded(db, release, master(1.0))

    async def refused(db: AsyncSession, release: Release) -> None:
        raise RuntimeError("the save failed")

    monkeypatch.setattr(service, "_touched", refused)
    with pytest.raises(RuntimeError):
        await _process(database, track)
    assert store.keys(public=True) == []


async def test_the_job_waits_for_its_encoder_before_it_lets_the_files_go(
    db: AsyncSession, database: Database, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = await _release(db)
    track = await _uploaded(db, release, master(1.0))
    closed: list[bool] = []
    # The encoder holds until the percent's write has failed (CodeRabbit on #145:
    # timing alone can let it finish first), then works on a while.
    failed = threading.Event()

    def slow(source: BinaryIO, into: BinaryIO, *, kbps: int, progress: Any) -> audio.Made:
        progress(10)
        assert failed.wait(5)
        time.sleep(0.3)
        closed.append(into.closed)
        return audio.Made(duration_ms=1000, peaks=[0] * 1000, samplerate=44100, channels=2)

    async def unwritten(*args: Any) -> None:
        failed.set()
        raise RuntimeError("the percent couldn't be written")

    monkeypatch.setattr(audio, "make_stream", slow)
    monkeypatch.setattr(jobs, "_percent", unwritten)
    monkeypatch.setattr(jobs, "PROGRESS_EVERY", 0.05)
    with pytest.raises(RuntimeError, match="percent"):
        await _process(database, track)
    assert closed == [False]


async def test_a_last_try_that_runs_out_of_time_fails_the_track(
    db: AsyncSession, database: Database, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CodeRabbit on #145: the worker's own timeout cancels the handler, which no
    `except Exception` hears; the job's deadline comes first and says so."""
    release = await _release(db)
    track = await _uploaded(db, release, master(1.0))

    def stuck(source: BinaryIO, into: BinaryIO, *, kbps: int, progress: Any) -> audio.Made:
        time.sleep(1.0)
        return audio.Made(duration_ms=1000, peaks=[0] * 1000, samplerate=44100, channels=2)

    monkeypatch.setattr(audio, "make_stream", stuck)
    monkeypatch.setattr(jobs, "DEADLINE", 0.1, raising=False)
    monkeypatch.setattr(jobs, "ENCODER_GRACE", 0.05, raising=False)
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await asyncio.wait_for(_process(database, track, try_number=jobs.TRIES), timeout=0.5)
    await db.refresh(track)
    assert (track.audio_state, track.audio_error) == ("failed", "discography.process_failed")


async def test_a_percent_never_lands_on_the_master_that_replaced_its_own(
    db: AsyncSession, database: Database, store: Store
) -> None:
    """CodeRabbit on #145: the percent's write holds the row while it checks the master."""
    release = await _release(db)
    track = await _uploaded(db, release, master(1.0))
    old = track.master_key
    assert old is not None
    ctx = SimpleNamespace(sessions=database.sessions, try_number=1)
    async with database.sessions() as replacing:
        row = await replacing.scalar(select(Track).where(Track.id == track.id).with_for_update())
        assert row is not None
        row.master_key, row.processing_percent = "discography/masters/new.wav", 0
        await replacing.flush()
        task = asyncio.ensure_future(jobs._percent(ctx, track.id, old, 55))  # type: ignore[arg-type]
        await asyncio.sleep(0.3)
        await replacing.commit()
    await task
    await db.refresh(track)
    assert (track.master_key, track.processing_percent) == ("discography/masters/new.wav", 0)


async def test_a_stream_whose_commit_reply_was_lost_is_kept_when_its_track_names_it(
    db: AsyncSession, database: Database, store: Store
) -> None:
    """CodeRabbit on #145: a commit can land and its reply be lost; the file goes only
    if no track names it."""
    release = await _release(db)
    track = await _uploaded(db, release, master(1.0))

    def sessions() -> AsyncSession:
        session = database.sessions()
        real = session.commit

        async def commit() -> None:
            await real()
            raise ConnectionError("the commit's reply was lost")

        session.commit = commit  # type: ignore[method-assign]
        return session

    ctx = SimpleNamespace(sessions=sessions, try_number=1)
    with pytest.raises(ConnectionError):
        await jobs.process_track.run(  # type: ignore[arg-type]
            ctx, {"track_id": str(track.id), "master_key": track.master_key}
        )
    await db.refresh(track)
    assert track.stream_key is not None
    assert store.keys(public=True) == [track.stream_key]


async def test_search_drops_lyrics_once_the_site_stops_showing_them(
    db: AsyncSession, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = await _live(db)
    track = await _linked(db, release)
    words = f"moonlit{uuid.uuid4().hex[:8]}"
    await service.change_track(db, track.id, track.version, {"lyrics": words}, by=None)
    await db.commit()
    body = select(SearchDocument.body).where(SearchDocument.content_id == release.id)
    assert words in (await db.scalar(body) or "")

    async def hidden(db: AsyncSession) -> Settings:
        return Settings(show_lyrics=False)

    monkeypatch.setattr(service, "settings_of", hidden)
    ctx = SimpleNamespace(sessions=database.sessions)
    heard = kernel_events.Event(
        uuid.uuid4(),
        "kernel.settings.changed",
        1,
        clock.now(),
        {"module": "discography", "version": 2},
    )
    await discography_events._settings_changed(ctx, heard)  # type: ignore[arg-type]
    await db.commit()
    assert words not in (await db.scalar(body) or "")
