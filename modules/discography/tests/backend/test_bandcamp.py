"""Bandcamp's own player (`dev plans/contracts/bandcamp-player.md` §2, §3, §7;
0.1.5): what a paste keeps, the order a track plays from, and a Bandcamp
track live everywhere a SoundCloud one is."""

from __future__ import annotations

from typing import Any

import pytest
from discography import public, refs, service
from discography.models import Release, Track
from discography.server_copy import PAGES
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem

from ..conftest import slug

TRACK = "https://exampleband.bandcamp.com/track/one-more-time#bandcamp-track=987654321"
ALBUM = "https://exampleband.bandcamp.com/album/weightless#bandcamp-album=1234567"
PLAYER = (
    'src="https://bandcamp.com/EmbeddedPlayer/{kind}={id}/size=large/bgcol=ffffff/'
    'linkcol=0687f5/tracklist=false/artwork=small/transparent=true/" seamless>'
)
TRACK_CODE = (
    '<iframe style="border: 0; width: 100%; height: 120px;" '
    + PLAYER.format(kind="track", id="987654321")
    + '<a href="https://exampleband.bandcamp.com/track/one-more-time">One More Time</a></iframe>'
)
ALBUM_CODE = (
    '<iframe style="border: 0; width: 100%; height: 120px;" '
    + PLAYER.format(kind="album", id="1234567")
    + '<a href="https://exampleband.bandcamp.com/album/weightless">Weightless</a></iframe>'
)
SOUNDCLOUD = "https://soundcloud.com/petrodestroys/catalyst"


# --- what a paste keeps ----------------------------------------------------------------------


def test_a_pasted_code_keeps_only_its_pages_link_with_the_players_id() -> None:
    assert service.bandcamp_player(TRACK_CODE, "track") == TRACK
    assert service.bandcamp_player(f"  {ALBUM_CODE}\n", "album") == ALBUM


def test_the_link_its_field_shows_back_is_taken_as_it_is_kept() -> None:
    assert service.bandcamp_player(TRACK, "track") == TRACK
    # One plain form: https, the host in lower case, no trailing slash.
    loose = "http://ExampleBand.bandcamp.com/track/one-more-time/#bandcamp-track=987654321"
    assert service.bandcamp_player(loose, "track") == TRACK


@pytest.mark.parametrize(
    ("pasted", "kind"),
    [
        (ALBUM_CODE, "track"),
        (TRACK_CODE, "album"),
        (ALBUM, "track"),
        ("https://exampleband.bandcamp.com/track/one-more-time", "track"),
        ("<p>Not a code</p>", "track"),
        (SOUNDCLOUD, "track"),
        ("https://open.spotify.com/album/1", "album"),
        ("<iframe>" + " " * 5000 + "</iframe>", "album"),
    ],
)
def test_anything_else_is_a_field_error_in_its_kinds_words(pasted: str, kind: str) -> None:
    with pytest.raises(Problem) as refused:
        service.bandcamp_player(pasted, kind)
    assert (refused.value.code, refused.value.status) == ("discography.not_bandcamp", 422)
    assert refused.value.errors == {"bandcamp_url": [service.NOT_BANDCAMP[kind]]}
    assert f"a Bandcamp {kind}'s embed code" in service.NOT_BANDCAMP[kind]


# --- the order a track plays from ------------------------------------------------------------


@pytest.mark.parametrize(
    ("track", "release", "plays", "player"),
    [
        (
            {"stream_key": "s", "soundcloud_url": SOUNDCLOUD, "bandcamp_url": TRACK},
            ALBUM,
            "upload",
            None,
        ),
        ({"soundcloud_url": SOUNDCLOUD, "bandcamp_url": TRACK}, ALBUM, "soundcloud", None),
        ({"bandcamp_url": TRACK}, ALBUM, "bandcamp", TRACK),
        ({}, ALBUM, "bandcamp", ALBUM),
        ({}, None, None, None),
    ],
)
def test_an_upload_then_soundcloud_then_its_own_bandcamp_player_then_its_albums(
    track: dict[str, Any], release: str | None, plays: str | None, player: str | None
) -> None:
    row, album = Track(**track), Release(bandcamp_url=release)
    assert service.plays_from(row, album) == plays
    assert service.bandcamp_of(row, album) == player


# --- live everywhere -------------------------------------------------------------------------


async def _live(db: AsyncSession, **fields: Any) -> Release:
    release = await service.create_release(
        db, {"title": "Weightless", "slug": slug(), "artist_line": "The band", **fields}, by=None
    )
    await service.publish(db, release.id, None, by=None)
    await db.commit()
    return release


async def _track(db: AsyncSession, release: Release, title: str, **fields: Any) -> Track:
    track = await service.create_track(db, release.id, title, None, by=None)
    if fields:
        track = await service.change_track(db, track.id, track.version, fields, by=None)
    await db.commit()
    return track


@pytest.mark.db
async def test_a_track_with_its_own_bandcamp_player_is_live_everywhere(db: AsyncSession) -> None:
    release = await _live(db)
    track = await _track(db, release, "One More Time", bandcamp_url=TRACK_CODE, duration_ms=229_000)
    assert track.bandcamp_url == TRACK

    shown = await service.shown(db, release)
    [line] = shown["tracks"]
    assert (
        line["plays_from"],
        line["bandcamp_url"],
        line["stream_url"],
        line["soundcloud_url"],
    ) == (
        "bandcamp",
        TRACK,
        None,
        None,
    )
    assert (shown["track_count"], line["duration_ms"]) == (1, 229_000)
    found = await service.live_track(db, release.slug, track.slug)
    assert isinstance(found, tuple)
    page = await service.track_shown(db, *found)
    assert (page["bandcamp_url"], page["peaks"]) == (TRACK, None)
    [card] = await service.tracks_by_id(db, [track.id])
    assert card["bandcamp_url"] == TRACK
    cards = await public.track_cards(db, [track.id])
    assert (cards[track.id].bandcamp_url, cards[track.id].stream_url) == (TRACK, None)
    assert (await public.release_cards(db, [release.id]))[release.id].bandcamp_url == TRACK
    ref = (await refs.Tracks().find(db, [track.id]))[track.id]
    assert ref.live
    assert ref.path == service.track_path(release, track)
    assert PAGES is not None
    entries = await PAGES.sitemap(db)
    assert service.track_path(release, track) in [entry.path for entry in entries]
    [row] = [each for each in await service.every_release(db) if each["id"] == str(release.id)]
    assert (row["track_count"], row["unplayable"]) == (1, 0)
    full = await service.full_track(db, track)
    assert (full["audio"]["plays_from"], full["audio"]["bandcamp_url"]) == ("bandcamp", TRACK)


@pytest.mark.db
async def test_a_track_with_no_player_of_its_own_plays_in_its_albums_while_it_has_one(
    db: AsyncSession,
) -> None:
    release = await _live(db)
    track = await _track(db, release, "Weightless")
    assert await service.live_track(db, release.slug, track.slug) is None

    release = await service.change_release(
        db, release.id, release.version, {"bandcamp_url": ALBUM_CODE}, by=None
    )
    await db.commit()
    assert (await service.full_release(db, release))["bandcamp_url"] == ALBUM
    [line] = (await service.shown(db, release))["tracks"]
    assert (line["plays_from"], line["bandcamp_url"]) == ("bandcamp", ALBUM)
    full = await service.full_track(db, track)
    # Its own field stays empty: the album's player is the album's.
    assert (full["audio"]["plays_from"], full["audio"]["bandcamp_url"]) == ("bandcamp", None)

    release = await service.change_release(
        db, release.id, release.version, {"bandcamp_url": "  "}, by=None
    )
    await db.commit()
    assert release.bandcamp_url is None
    assert (await service.shown(db, release))["tracks"] == []
    assert await service.live_track(db, release.slug, track.slug) is None
    assert await public.track_cards(db, [track.id]) == {}
    assert not (await refs.Tracks().find(db, [track.id]))[track.id].live


@pytest.mark.db
async def test_an_uploaded_or_soundcloud_track_never_names_a_bandcamp_player(
    db: AsyncSession,
) -> None:
    release = await _live(db)
    release = await service.change_release(
        db, release.id, release.version, {"bandcamp_url": ALBUM}, by=None
    )
    track = await _track(db, release, "Catalyst", soundcloud_url=SOUNDCLOUD, bandcamp_url=TRACK)
    [line] = (await service.shown(db, release))["tracks"]
    assert (line["plays_from"], line["bandcamp_url"]) == ("soundcloud", None)
    # Its own player is kept for when the link goes.
    track = await service.change_track(
        db, track.id, track.version, {"soundcloud_url": None}, by=None
    )
    await db.commit()
    [line] = (await service.shown(db, release))["tracks"]
    assert (line["plays_from"], line["bandcamp_url"]) == ("bandcamp", TRACK)


@pytest.mark.db
async def test_a_blank_paste_clears_a_tracks_player(db: AsyncSession) -> None:
    release = await _live(db)
    track = await _track(db, release, "One More Time", bandcamp_url=TRACK)
    track = await service.change_track(db, track.id, track.version, {"bandcamp_url": ""}, by=None)
    await db.commit()
    assert track.bandcamp_url is None
    with pytest.raises(Problem) as refused:
        await service.change_track(db, track.id, track.version, {"bandcamp_url": ALBUM}, by=None)
    assert refused.value.code == "discography.not_bandcamp"


@pytest.mark.db
@pytest.mark.parametrize(
    ("table", "value"),
    [
        ("discography_track", ALBUM),
        ("discography_release", TRACK),
        ("discography_track", "https://exampleband.bandcamp.com/track/one-more-time"),
    ],
)
async def test_the_table_holds_only_a_player_of_its_kind(
    db: AsyncSession, table: str, value: str
) -> None:
    release = await _live(db)
    track = await _track(db, release, "Held")
    row = track.id if table == "discography_track" else release.id
    with pytest.raises(IntegrityError):
        await db.execute(
            text(f"UPDATE {table} SET bandcamp_url = :value WHERE id = :id"),  # noqa: S608
            {"value": value, "id": row},
        )
    await db.rollback()
