"""discography's things another module may point at (kernel.refs, hook 11,
decision 0072; `dev plans/contracts/featured.md` §2, "discography 0.1.2"):
its releases, `discography.release` ("Albums"), and its tracks,
`discography.track` ("Tracks"), drafts too, so `featured`'s Players can
schedule a single before its release day.

- **A release** is live while the site shows it with a track that plays; its
  line is "2026, petro and J Tone, 15 tracks".
- **A track** is live while its release is on the site and it plays; its line
  is "Catalyst, petro and J Tone".
- **The picker** finds by title, drafts included, newest edit first, a page
  at a time from a cursor of its own (`<updated_at>~<id>`); a cursor that
  isn't one is a ValueError, which `kernel.refs`' callers answer 422.

Each has its release's front cover, its smallest copy, as its picture. Nothing
here imports `featured`: the kernel asks.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from media import public as media
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from discography.models import Release, Track
from kernel import lifecycle, refs


def _thumb(picture: media.Picture | None) -> str | None:
    """A cover's smallest copy: the first of its srcset, smallest first."""
    if picture is None:
        return None
    first = picture.srcset.split(",", 1)[0].strip().rsplit(" ", 1)[0]
    return first or picture.url


def _count(n: int) -> str:
    return "1 track" if n == 1 else f"{n} tracks"


def release_line(release: Release, playable: int) -> str:
    """ "2026, petro and J Tone, 15 tracks": the year when it has one."""
    parts = [str(release.year)] if release.year else []
    if release.artist_line:
        parts.append(release.artist_line)
    parts.append(_count(playable))
    return ", ".join(parts)


def track_line(release: Release) -> str:
    """ "Catalyst, petro and J Tone": its release and the release's artists."""
    return ", ".join(part for part in (release.title, release.artist_line) if part)


def _visible(release: Release) -> bool:
    return release.status == lifecycle.PUBLISHED


def _after(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    """A page's cursor, `<updated_at>~<id>`; ValueError for anything else."""
    if cursor is None:
        return None
    at, mark, ident = cursor.partition("~")
    when = datetime.fromisoformat(at) if mark else None
    if when is None or when.utcoffset() is None:
        raise ValueError(f"{cursor!r} isn't a page of discography's things.")
    return when, uuid.UUID(ident)


def _page_of(rows: list[Any], limit: int, at: Any) -> str | None:
    if len(rows) <= limit:
        return None
    last = rows[limit - 1]
    return f"{at(last).isoformat()}~{last.id}"


def _matching(column: Any, q: str | None) -> Any:
    """`column` holding `q`'s words as typed, `%` and `_` meaning themselves."""
    if not q:
        return sa.true()
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


class Releases(refs.Source):
    type = "discography.release"
    label = "Albums"

    async def _refs(self, db: AsyncSession, releases: Sequence[Release]) -> list[refs.Ref]:
        pictures = await service.pictures_of(db, releases)
        tracks = await service.tracks_of(db, [release.id for release in releases])
        found: list[refs.Ref] = []
        for release in releases:
            playable = sum(1 for track in tracks[release.id] if service.plays_from(track))
            live = _visible(release) and playable > 0
            found.append(
                refs.Ref(
                    id=release.id,
                    title=release.title,
                    line=release_line(release, playable),
                    image=_thumb(pictures.get(release.cover_id) if release.cover_id else None),
                    path=service.release_path(release) if live else None,
                    live=live,
                )
            )
        return found

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        releases = list(await db.scalars(select(Release).where(Release.id.in_(list(ids)))))
        return {ref.id: ref for ref in await self._refs(db, releases)}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        statement = select(Release).where(_matching(Release.title, q))
        after = _after(cursor)
        if after is not None:
            statement = statement.where(
                sa.tuple_(Release.updated_at, Release.id)
                < sa.tuple_(
                    sa.literal(after[0], Release.updated_at.type),
                    sa.literal(after[1], Release.id.type),
                )
            )
        rows = list(
            await db.scalars(
                statement.order_by(Release.updated_at.desc(), Release.id.desc()).limit(limit + 1)
            )
        )
        return {
            "items": await self._refs(db, rows[:limit]),
            "next_cursor": _page_of(rows, limit, lambda release: release.updated_at),
        }


class Tracks(refs.Source):
    type = "discography.track"
    label = "Tracks"

    async def _refs(
        self, db: AsyncSession, rows: Sequence[tuple[Track, Release]]
    ) -> list[refs.Ref]:
        pictures = await service.pictures_of(db, [release for _, release in rows])
        found: list[refs.Ref] = []
        for track, release in rows:
            live = _visible(release) and service.plays_from(track) is not None
            found.append(
                refs.Ref(
                    id=track.id,
                    title=track.title,
                    line=track_line(release),
                    image=_thumb(pictures.get(release.cover_id) if release.cover_id else None),
                    path=service.track_path(release, track) if live else None,
                    live=live,
                )
            )
        return found

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        rows = list(
            await db.execute(
                select(Track, Release)
                .join(Release, Release.id == Track.release_id)
                .where(Track.id.in_(list(ids)))
            )
        )
        return {ref.id: ref for ref in await self._refs(db, [(t, r) for t, r in rows])}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        statement = (
            select(Track, Release)
            .join(Release, Release.id == Track.release_id)
            .where(_matching(Track.title, q))
        )
        after = _after(cursor)
        if after is not None:
            statement = statement.where(
                sa.tuple_(Track.updated_at, Track.id)
                < sa.tuple_(
                    sa.literal(after[0], Track.updated_at.type),
                    sa.literal(after[1], Track.id.type),
                )
            )
        rows = [
            (track, release)
            for track, release in await db.execute(
                statement.order_by(Track.updated_at.desc(), Track.id.desc()).limit(limit + 1)
            )
        ]
        tracks = [track for track, _ in rows]
        return {
            "items": await self._refs(db, rows[:limit]),
            "next_cursor": _page_of(tracks, limit, lambda track: track.updated_at),
        }


REFS = (Releases(), Tracks())
