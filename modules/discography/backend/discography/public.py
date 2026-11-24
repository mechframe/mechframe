"""What other modules and a site's own code may call (SPEC 7), and only those
that list `discography` under requires.modules.

`track_cards` and `release_cards` are for players and site composers
(`audio-player`, `featured`): only live, playable items are ever answered,
so a placement pointing at a draft, a deleted track or one that can't play
simply has no card. `releases`, `release`, `track` and `path` give a site's
own Music and Release pages, and its server copy, the API's own answers.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from media import public as media
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from discography.models import Release, Track
from discography.schemas import LiveRelease, LiveTrack, MusicMoved, ReleaseCards
from kernel import lifecycle

PER_PAGE = service.PER_PAGE


@dataclass(frozen=True)
class Card:
    """A live track, or a live release's first playable track, as a player plays it."""

    id: uuid.UUID
    title: str
    artist_line: str
    cover: media.Picture | None
    #: The stream file, when it plays from an upload; else the SoundCloud link.
    stream_url: str | None
    soundcloud_url: str | None
    duration_ms: int | None
    #: 1,000 integers from 0 to 255 for a stream file; None for a link.
    peaks: list[int] | None
    explicit: bool
    #: Its page: /music/<release>/<track>, or /music/<release> for a release.
    path: str
    #: A release's tracks that play, in order, as cards of their own; empty for a track.
    tracks: tuple[Card, ...] = ()


def path(release_slug: str, track_slug: str | None = None) -> str:
    """A release's page, such as /music/unified-vibration, or one of its tracks'."""
    return f"{service.PREFIX}{release_slug}" + (f"/{track_slug}" if track_slug else "")


def _card(release: Release, track: Track, picture: media.Picture | None, explicit: bool) -> Card:
    upload = service.plays_from(track) == "upload"
    return Card(
        id=track.id,
        title=track.title,
        artist_line=release.artist_line,
        cover=picture,
        stream_url=service.stream_url(track) if upload else None,
        soundcloud_url=None if upload else track.soundcloud_url,
        duration_ms=track.duration_ms,
        peaks=track.peaks if upload else None,
        explicit=explicit and track.explicit,
        path=service.track_path(release, track),
    )


async def track_cards(db: AsyncSession, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Card]:
    """The live, playable tracks among `ids`, by id."""
    wanted = list(set(ids))
    if not wanted:
        return {}
    rows = list(
        await db.execute(
            select(Track, Release)
            .join(Release, Release.id == Track.release_id)
            .where(Track.id.in_(wanted), lifecycle.visible(Release), service.playable_clause())
        )
    )
    releases = [release for _, release in rows]
    pictures = await service.pictures_of(db, releases)
    badge = (await service.settings_of(db)).show_explicit_badge
    return {
        track.id: _card(
            release, track, pictures.get(release.cover_id) if release.cover_id else None, badge
        )
        for track, release in rows
    }


async def release_cards(db: AsyncSession, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Card]:
    """The live releases among `ids` that have a track to play, by id: each
    with its playable tracks in order."""
    wanted = list(set(ids))
    if not wanted:
        return {}
    releases = list(
        await db.scalars(select(Release).where(Release.id.in_(wanted), lifecycle.visible(Release)))
    )
    pictures = await service.pictures_of(db, releases)
    tracks = await service.tracks_of(db, [release.id for release in releases])
    badge = (await service.settings_of(db)).show_explicit_badge
    found: dict[uuid.UUID, Card] = {}
    for release in releases:
        picture = pictures.get(release.cover_id) if release.cover_id else None
        playable = [
            _card(release, track, picture, badge)
            for track in tracks[release.id]
            if service.plays_from(track)
        ]
        if not playable:
            continue
        first = playable[0]
        found[release.id] = Card(
            id=release.id,
            title=release.title,
            artist_line=release.artist_line,
            cover=picture,
            stream_url=first.stream_url,
            soundcloud_url=first.soundcloud_url,
            duration_ms=sum(each.duration_ms or 0 for each in playable) or None,
            peaks=None,
            explicit=any(each.explicit for each in playable),
            path=service.release_path(release),
            tracks=tuple(playable),
        )
    return found


async def releases(
    db: AsyncSession, *, kind: str | None = None, cursor: str | None = None, limit: int = PER_PAGE
) -> ReleaseCards:
    """A page of live releases, newest first, as `GET /api/discography/releases` answers."""
    return ReleaseCards.model_validate(
        await service.page_of(db, kind=kind, cursor=cursor, limit=limit)
    )


async def release(db: AsyncSession, slug: str) -> LiveRelease | MusicMoved | None:
    """The live release at `slug`; where it is now for an address it left; else None."""
    found = await service.live(db, slug)
    if found is None:
        return None
    if isinstance(found, str):
        return MusicMoved(moved=found)
    return LiveRelease.model_validate(await service.shown(db, found))


async def track(db: AsyncSession, slug: str, track_slug: str) -> LiveTrack | MusicMoved | None:
    found = await service.live_track(db, slug, track_slug)
    if found is None:
        return None
    if isinstance(found, str):
        return MusicMoved(moved=found)
    return LiveTrack.model_validate(await service.track_shown(db, *found))
