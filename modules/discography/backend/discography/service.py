"""discography's logic (`dev plans/contracts/discography.md` §2).

**A release** is drafted, scheduled and published through the kernel's
lifecycle; its tracks go live with it. A save of a live release, or of one of
its tracks, changes the site at once, writes its search document again and
says `discography.release.changed`.

**A track plays from** its stream file once the job has made it, else from
its SoundCloud link, else not at all; a track that can't play is in no public
answer. An upload is judged by its bytes (`audio.probe`), stored privately,
and queued for `discography.process_track`; files a change leaves behind go
after its commit (`discography.delete_files`).

**A move** follows the release or track, not an address: an old address
names what left it, so none chains. Only a live release leaves one.

**Credits** name a person in a role. A name is one person however often it's
credited (matched without case); one whose last credit goes is removed in the
same save. Covers are media's images, recorded as the release's uses.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any, BinaryIO, cast
from urllib.parse import urlsplit

import sqlalchemy as sa
from embeds import public as embeds
from media import public as media
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from discography import audio
from discography.models import (
    MAX_SLUG,
    PLATFORMS,
    SLUG_PATTERN,
    Credit,
    Link,
    Move,
    Person,
    Release,
    Role,
    Track,
)
from discography.schemas import Settings
from kernel import Problem, audit, clock, events, jobs, lifecycle, search, storage
from kernel import settings as module_settings

MODULE = "discography"
CONTENT_TYPE = "discography.release"
PREFIX = "/music/"
PER_PAGE = 12
ADMIN_PER_PAGE = 50
#: An upload's largest master: under the route's 64 MB, which the form's own bytes share.
MAX_MASTER_BYTES = 60 * 1024 * 1024
PROCESS = "discography.process_track"
DELETE_FILES = "discography.delete_files"
_SLUG = re.compile(SLUG_PATTERN)

#: Each platform's hosts, and its name on a page.
PLATFORM_HOSTS: dict[str, tuple[str, ...]] = {
    "spotify": ("open.spotify.com", "spotify.link"),
    "apple-music": ("music.apple.com",),
    "youtube": ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"),
    "youtube-music": ("music.youtube.com",),
    "amazon-music": ("music.amazon.com", "music.amazon.co.uk", "amazon.com", "www.amazon.com"),
    "soundcloud": ("soundcloud.com", "www.soundcloud.com", "m.soundcloud.com", "on.soundcloud.com"),
    "bandcamp": ("bandcamp.com",),
    "tidal": ("tidal.com", "listen.tidal.com"),
    "deezer": ("www.deezer.com", "deezer.com", "deezer.page.link"),
}
PLATFORM_LABELS = {
    "spotify": "Spotify",
    "apple-music": "Apple Music",
    "youtube": "YouTube",
    "youtube-music": "YouTube Music",
    "amazon-music": "Amazon Music",
    "soundcloud": "SoundCloud",
    "bandcamp": "Bandcamp",
    "tidal": "Tidal",
    "deezer": "Deezer",
}
#: A failed upload's code, in words for the board.
ERROR_WORDS = {
    "discography.not_audio": "The file couldn't be read as audio. Export it again as WAV or FLAC.",
    "discography.too_long": "The file runs over 60 minutes.",
    "discography.unsupported_rate": (
        "Its sample rate can't be streamed: export it at 44.1 or 48 kHz."
    ),
    "discography.master_missing": "The uploaded file is gone from storage. Upload it again.",
}
#: The roles a new site starts with, in order (the Credits board's).
STARTER_ROLES = ("Artist", "Featuring", "Produced by", "Written by", "Mastered by")


def _not_found(what: str = "release") -> Problem:
    return Problem(f"discography.{what}_not_found", 404, f"There's no such {what}.")


def _invalid(field: str, code: str, message: str) -> Problem:
    return Problem(code, 422, message, errors={field: [message]})


def _uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise _invalid(field, "kernel.invalid_request", "That isn't an id.") from None


async def settings_of(db: AsyncSession) -> Settings:
    return cast(Settings, await module_settings.for_module(db, MODULE))


def owner(release_id: uuid.UUID) -> str:
    """The release as the media library names a place an image is used."""
    return f"{CONTENT_TYPE}:{release_id}"


def release_path(release: Release) -> str:
    return f"{PREFIX}{release.slug}"


def track_path(release: Release, track: Track) -> str:
    return f"{PREFIX}{release.slug}/{track.slug}"


def _when(at: datetime | None) -> str | None:
    return at.isoformat() if at else None


# --- slugs -----------------------------------------------------------------------------------


def slug_for(text: str) -> str:
    """The slug a title spells: "Don't stop" is `dont-stop` (blog's rule)."""
    folded = unicodedata.normalize("NFKD", text.replace("'", "").replace(chr(0x2019), ""))
    words: list[str] = []
    word = ""
    for each in folded.lower():
        if unicodedata.combining(each):
            continue
        if each.isascii() and each.isalnum():
            word += each
        elif word:
            words.append(word)
            word = ""
    if word:
        words.append(word)
    return "-".join(words)[:MAX_SLUG].strip("-")


def _numbered(base: str, number: int) -> str:
    suffix = f"-{number}"
    return f"{base[: MAX_SLUG - len(suffix)].rstrip('-')}{suffix}"


async def _unique(db: AsyncSession, taken: Any, base: str, fallback: str) -> str:
    base = base or fallback
    slug, number = base, 2
    while await db.scalar(taken(slug)) is not None:
        slug = _numbered(base, number)
        number += 1
    return slug


async def unique_release_slug(db: AsyncSession, base: str, exclude: uuid.UUID | None) -> str:
    def taken(slug: str) -> Any:
        found = select(Release.id).where(Release.slug == slug)
        return found if exclude is None else found.where(Release.id != exclude)

    return await _unique(db, taken, base, "release")


async def unique_track_slug(
    db: AsyncSession, release_id: uuid.UUID, base: str, exclude: uuid.UUID | None
) -> str:
    def taken(slug: str) -> Any:
        found = select(Track.id).where(Track.release_id == release_id, Track.slug == slug)
        return found if exclude is None else found.where(Track.id != exclude)

    return await _unique(db, taken, base, "track")


def _taken(slug: str, title: str | None, what: str = "release") -> Problem:
    said = (
        f"Another {what}, {title}, is at {slug}."
        if title
        else f"Another {what} took {slug} just now."
    )
    return Problem(
        "discography.slug_taken", 409, f"{said} Choose another address.", errors={"slug": [said]}
    )


async def _flushed(db: AsyncSession, slug: str, what: str = "release") -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise _taken(slug, None, what) from None


# --- reading rows ----------------------------------------------------------------------------


async def get_release(db: AsyncSession, release_id: uuid.UUID, *, lock: bool = False) -> Release:
    statement = select(Release).where(Release.id == release_id)
    found = await db.scalar(statement.with_for_update() if lock else statement)
    if found is None:
        raise _not_found()
    return found


async def get_track(db: AsyncSession, track_id: uuid.UUID, *, lock: bool = False) -> Track:
    statement = select(Track).where(Track.id == track_id)
    found = await db.scalar(statement.with_for_update() if lock else statement)
    if found is None:
        raise _not_found("track")
    return found


async def tracks_of(
    db: AsyncSession, release_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[Track]]:
    wanted = list(set(release_ids))
    found: dict[uuid.UUID, list[Track]] = {each: [] for each in wanted}
    if wanted:
        rows = await db.scalars(
            select(Track).where(Track.release_id.in_(wanted)).order_by(Track.position)
        )
        for track in rows:
            found[track.release_id].append(track)
    return found


# --- what plays ------------------------------------------------------------------------------


def plays_from(track: Track) -> str | None:
    """The stream file once it's made, else the link, else nothing."""
    if track.audio_state == "ready" and track.stream_key:
        return "upload"
    if track.soundcloud_url:
        return "soundcloud"
    return None


def playable_clause() -> Any:
    return or_(
        sa.and_(Track.audio_state == "ready", Track.stream_key.is_not(None)),
        Track.soundcloud_url.is_not(None),
    )


def stream_url(track: Track) -> str | None:
    if not track.stream_key:
        return None
    try:
        return storage.public_url(track.stream_key)
    except storage.StorageNotConfigured:
        return None


def soundcloud_link(url: str) -> tuple[str, str]:
    """The link in its plain form and its kind, a track or a playlist, as
    `embeds` reads it; 422 for anything else."""
    found = embeds.recognise(url.strip())
    if found is None or found.provider != "soundcloud" or found.kind not in ("track", "set"):
        raise _invalid(
            "soundcloud_url",
            "discography.not_soundcloud",
            "That isn't a SoundCloud track or playlist. Copy the link from the track's page.",
        )
    parts = urlsplit(url.strip())
    return f"https://soundcloud.com{parts.path.rstrip('/')}", found.kind


# --- covers ----------------------------------------------------------------------------------


def _cover(picture: media.Picture | None) -> dict[str, Any] | None:
    if picture is None:
        return None
    return {
        "id": str(picture.id),
        "url": picture.url,
        "srcset": picture.srcset,
        "width": picture.width,
        "height": picture.height,
        "alt": picture.alt,
        "decorative": picture.decorative,
    }


async def pictures_of(
    db: AsyncSession, releases: Sequence[Release]
) -> dict[uuid.UUID, media.Picture]:
    ids = [
        each for release in releases for each in (release.cover_id, release.back_cover_id) if each
    ]
    return await media.pictures(db, ids)


async def _check_cover(db: AsyncSession, field: str, image_id: uuid.UUID) -> None:
    if await media.picture(db, image_id) is None:
        raise _invalid(field, "discography.cover_not_found", "The media library has no such image.")


async def _place_covers(db: AsyncSession, release: Release) -> None:
    """The release's covers recorded as its uses, and any other image it placed let go."""
    kept = [each for each in (release.cover_id, release.back_cover_id) if each]
    for image_id in kept:
        await media.use(
            db,
            image_id,
            owner=owner(release.id),
            label=release.title,
            link=f"/admin/music/{release.id}",
        )
    await media.release(db, owner=owner(release.id), keep=kept)


# --- credits ---------------------------------------------------------------------------------


async def credits_of(
    db: AsyncSession,
    *,
    release_ids: Iterable[uuid.UUID] = (),
    track_ids: Iterable[uuid.UUID] = (),
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    """Each release's and track's credits, in order, by its id."""
    releases, tracks = list(set(release_ids)), list(set(track_ids))
    found: dict[uuid.UUID, list[dict[str, Any]]] = {each: [] for each in [*releases, *tracks]}
    if not found:
        return found
    rows = await db.execute(
        select(Credit, Person, Role)
        .join(Person, Person.id == Credit.person_id)
        .join(Role, Role.id == Credit.role_id)
        .where(or_(Credit.release_id.in_(releases), Credit.track_id.in_(tracks)))
        .order_by(Credit.position)
    )
    for credit, person, role in rows:
        holder = cast(uuid.UUID, credit.release_id or credit.track_id)  # a CHECK holds one
        found[holder].append(
            {
                "role_id": str(role.id),
                "role": role.name,
                "person_id": str(person.id),
                "name": person.name,
                "profile": person.profile,
            }
        )
    return found


def public_credits(credits: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"role": each["role"], "name": each["name"]} for each in credits]


async def _person(db: AsyncSession, name: str) -> uuid.UUID:
    now = clock.now()
    await db.execute(
        insert(Person)
        .values(
            id=uuid.uuid4(),
            version=1,
            name=name,
            profile="unlinked",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing()
    )
    found = await db.scalar(select(Person.id).where(func.lower(Person.name) == name.lower()))
    if found is None:  # only a name deleted between the two statements
        raise Problem("discography.changed", 409, "A credit's name changed just now. Save again.")
    return found


async def _prune_people(db: AsyncSession) -> None:
    """Every person no credit names any more."""
    await db.execute(delete(Person).where(~sa.exists().where(Credit.person_id == Person.id)))


async def _replace_credits(
    db: AsyncSession,
    items: list[dict[str, Any]],
    *,
    release_id: uuid.UUID | None = None,
    track_id: uuid.UUID | None = None,
) -> None:
    role_ids = [_uuid(each["role_id"], "credits") for each in items]
    known = set(await db.scalars(select(Role.id).where(Role.id.in_(role_ids))))
    if any(each not in known for each in role_ids):
        raise _invalid(
            "credits", "discography.role_not_found", "One of those roles isn't on the list."
        )
    await db.execute(
        delete(Credit).where(
            Credit.release_id == release_id if release_id else Credit.track_id == track_id
        )
    )
    for position, (item, role_id) in enumerate(zip(items, role_ids, strict=True)):
        db.add(
            Credit(
                id=uuid.uuid4(),
                person_id=await _person(db, item["name"]),
                role_id=role_id,
                release_id=release_id,
                track_id=track_id,
                position=position,
            )
        )
    await db.flush()
    await _prune_people(db)


# --- links -----------------------------------------------------------------------------------


def platform_of(url: str) -> tuple[str, str]:
    """The platform a streaming link is on, from its host, and the link; 422 otherwise."""
    text = url.strip()
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").lower()
    except ValueError:
        host, parts = "", None
    if parts is None or parts.scheme.lower() != "https" or not host:
        raise _invalid("links", "discography.not_a_link", "A link starts with https://.")
    for platform in PLATFORMS:
        hosts = PLATFORM_HOSTS[platform]
        if host in hosts or (platform == "bandcamp" and host.endswith(".bandcamp.com")):
            return platform, text
    names = ", ".join(PLATFORM_LABELS[each] for each in PLATFORMS)
    raise _invalid(
        "links",
        "discography.not_a_platform",
        f"{host} isn't one of the platforms a release links to: {names}.",
    )


async def _replace_links(db: AsyncSession, release_id: uuid.UUID | None, urls: list[str]) -> None:
    read = [platform_of(each) for each in urls]
    platforms = [platform for platform, _ in read]
    if len(set(platforms)) != len(platforms):
        raise _invalid("links", "discography.platform_twice", "One link a platform.")
    await db.execute(
        delete(Link).where(
            Link.release_id == release_id if release_id else Link.release_id.is_(None)
        )
    )
    for position, (platform, url) in enumerate(read):
        db.add(
            Link(
                id=uuid.uuid4(),
                release_id=release_id,
                platform=platform,
                url=url,
                position=position,
            )
        )
    await db.flush()


async def links_of(
    db: AsyncSession, release_ids: Iterable[uuid.UUID | None]
) -> dict[uuid.UUID | None, list[dict[str, str]]]:
    wanted = list(set(release_ids))
    found: dict[uuid.UUID | None, list[dict[str, str]]] = {each: [] for each in wanted}
    ids = [each for each in wanted if each is not None]
    clauses = [Link.release_id.in_(ids)] if ids else []
    if None in wanted:
        clauses.append(Link.release_id.is_(None))
    if not clauses:
        return found
    for link in await db.scalars(select(Link).where(or_(*clauses)).order_by(Link.position)):
        found[link.release_id].append(
            {"platform": link.platform, "label": PLATFORM_LABELS[link.platform], "url": link.url}
        )
    return found


# --- search ----------------------------------------------------------------------------------


async def document(db: AsyncSession, release: Release) -> search.Document:
    """A release's words: its lines, its tracks' titles, every credit and,
    while the site shows them, its lyrics."""
    tracks = (await tracks_of(db, [release.id]))[release.id]
    shown = [track for track in tracks if plays_from(track)]
    credited = await credits_of(db, release_ids=[release.id], track_ids=[t.id for t in shown])
    names = {each["name"] for found in credited.values() for each in found}
    lyrics = (await settings_of(db)).show_lyrics
    words = " ".join(
        part
        for part in (
            release.artist_line,
            release.credit_line,
            release.summary,
            *(track.title for track in shown),
            *sorted(names),
            *((track.lyrics or "") for track in shown if lyrics),
        )
        if part
    )
    return search.Document(CONTENT_TYPE, release.id, release.title, words, release_path(release))


async def _touched(db: AsyncSession, release: Release) -> None:
    """A live release changed: its search document again, and the word for the homepage."""
    if release.status != lifecycle.PUBLISHED:
        return
    await search.index(db, await document(db, release))
    from discography.events import ReleaseChanged

    await events.emit(db, "discography.release.changed", ReleaseChanged(release_id=release.id))


# --- public reads ----------------------------------------------------------------------------


def _explicit(tracks: Iterable[Track], settings: Settings) -> bool:
    return settings.show_explicit_badge and any(t.explicit for t in tracks if plays_from(t))


async def cards(db: AsyncSession, releases: Sequence[Release]) -> list[dict[str, Any]]:
    """Live releases as a list shows them, in the order given."""
    settings = await settings_of(db)
    pictures = await pictures_of(db, releases)
    tracks = await tracks_of(db, [release.id for release in releases])
    return [
        {
            "title": release.title,
            "slug": release.slug,
            "kind": release.kind,
            "year": release.year,
            "artist_line": release.artist_line,
            "credit_line": release.credit_line,
            "summary": release.summary,
            "cover": _cover(pictures.get(release.cover_id) if release.cover_id else None),
            "explicit": _explicit(tracks[release.id], settings),
            "track_count": sum(1 for track in tracks[release.id] if plays_from(track)),
            "tracklist_to_come": release.tracklist_to_come,
            "path": release_path(release),
            "published_at": _when(release.published_at),
        }
        for release in releases
    ]


def _cursor_of(at: datetime, ident: uuid.UUID) -> str:
    return f"{at.isoformat()}~{ident}"


def _after(cursor: str) -> tuple[datetime, uuid.UUID]:
    at, mark, ident = cursor.partition("~")
    try:
        when, found = datetime.fromisoformat(at), uuid.UUID(ident)
    except ValueError:
        when = None
    if not mark or when is None or when.utcoffset() is None:
        raise _invalid("cursor", "kernel.invalid_request", "Not a page of these releases.")
    return when, found


async def page_of(
    db: AsyncSession, *, kind: str | None, cursor: str | None, limit: int = PER_PAGE
) -> dict[str, Any]:
    """A page of live releases, newest first."""
    statement = select(Release).where(lifecycle.visible(Release))
    if kind is not None:
        statement = statement.where(Release.kind == kind)
    if cursor is not None:
        at, ident = _after(cursor)
        statement = statement.where(
            sa.tuple_(Release.published_at, Release.id)
            < sa.tuple_(
                sa.literal(at, Release.published_at.type), sa.literal(ident, Release.id.type)
            )
        )
    rows = list(
        await db.scalars(
            statement.order_by(Release.published_at.desc(), Release.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if rows else None
    return {
        "items": await cards(db, rows),
        "next_cursor": (
            _cursor_of(last.published_at, last.id)
            if more and last is not None and last.published_at
            else None
        ),
    }


async def newest(db: AsyncSession, limit: int = PER_PAGE) -> list[Release]:
    return list(
        await db.scalars(
            select(Release)
            .where(lifecycle.visible(Release))
            .order_by(Release.published_at.desc(), Release.id.desc())
            .limit(limit)
        )
    )


def _valid_slug(slug: str) -> bool:
    return len(slug) <= MAX_SLUG and _SLUG.fullmatch(slug) is not None


async def live(db: AsyncSession, slug: str) -> Release | str | None:
    """The live release at `slug`; where it is now for an address a live
    release left; else None."""
    if not _valid_slug(slug):
        return None
    found = await db.scalar(select(Release).where(Release.slug == slug, lifecycle.visible(Release)))
    if found is not None:
        return found
    return await _moved(db, slug)


async def _moved(db: AsyncSession, old: str) -> str | None:
    row = (
        await db.execute(
            select(Release, Move.track_id)
            .join(Move, Move.release_id == Release.id)
            .where(Move.old_path == old, lifecycle.visible(Release))
        )
    ).first()
    if row is None:
        return None
    release, track_id = row
    if track_id is None:
        return release_path(release) if release_path(release) != f"{PREFIX}{old}" else None
    track = await db.get(Track, track_id)
    if track is None or not plays_from(track):
        return None
    return track_path(release, track)


def _line(release: Release, track: Track, number: int) -> dict[str, Any]:
    return {
        "title": track.title,
        "slug": track.slug,
        "number": number,
        "duration_ms": track.duration_ms,
        "explicit": track.explicit,
        "plays_from": plays_from(track),
        "stream_url": stream_url(track) if plays_from(track) == "upload" else None,
        "soundcloud_url": track.soundcloud_url,
        "soundcloud_kind": track.soundcloud_kind,
        "has_lyrics": bool(track.lyrics),
        "path": track_path(release, track),
    }


def _shown_tracks(tracks: list[Track]) -> list[tuple[int, Track]]:
    """The tracks that play, numbered from 1 in their order."""
    return list(enumerate((track for track in tracks if plays_from(track)), start=1))


async def shown(db: AsyncSession, release: Release) -> dict[str, Any]:
    """A live release as its page draws it."""
    [card] = await cards(db, [release])
    pictures = await pictures_of(db, [release])
    tracks = _shown_tracks((await tracks_of(db, [release.id]))[release.id])
    credited = await credits_of(db, release_ids=[release.id])
    links = await links_of(db, [release.id])
    return {
        **card,
        "back_cover": _cover(
            pictures.get(release.back_cover_id) if release.back_cover_id else None
        ),
        "tracks": [_line(release, track, number) for number, track in tracks],
        "credits": public_credits(credited[release.id]),
        "links": links[release.id],
        "updated_at": release.updated_at.isoformat(),
    }


async def live_track(
    db: AsyncSession, slug: str, track_slug: str
) -> tuple[Release, Track, int] | str | None:
    """The live, playable track at `slug`/`track_slug`, with its number; where
    it is now for an address it left; else None."""
    if not (_valid_slug(slug) and _valid_slug(track_slug)):
        return None
    release = await db.scalar(
        select(Release).where(Release.slug == slug, lifecycle.visible(Release))
    )
    if release is None:
        moved = await _moved(db, slug)
        return f"{moved}/{track_slug}" if moved and moved.count("/") == 2 else None
    tracks = _shown_tracks((await tracks_of(db, [release.id]))[release.id])
    for number, track in tracks:
        if track.slug == track_slug:
            return release, track, number
    moved = await _moved(db, f"{slug}/{track_slug}")
    return moved


async def track_shown(
    db: AsyncSession, release: Release, track: Track, number: int
) -> dict[str, Any]:
    settings = await settings_of(db)
    pictures = await pictures_of(db, [release])
    credited = await credits_of(db, track_ids=[track.id])
    return {
        **_line(release, track, number),
        "explicit": settings.show_explicit_badge and track.explicit,
        "release": {
            "title": release.title,
            "slug": release.slug,
            "kind": release.kind,
            "path": release_path(release),
        },
        "artist_line": release.artist_line,
        "cover": _cover(pictures.get(release.cover_id) if release.cover_id else None),
        "peaks": track.peaks if plays_from(track) == "upload" else None,
        "lyrics": track.lyrics if settings.show_lyrics and track.lyrics else None,
        "credits": public_credits(credited[track.id]),
    }


async def artist_links(db: AsyncSession) -> list[dict[str, str]]:
    return (await links_of(db, [None]))[None]


# --- the admin: releases ---------------------------------------------------------------------


def _audio(track: Track) -> dict[str, Any]:
    return {
        "state": track.audio_state,
        "plays_from": plays_from(track),
        "percent": track.processing_percent,
        "error": track.audio_error,
        "error_words": ERROR_WORDS.get(track.audio_error or ""),
        "master_name": track.master_name,
        "master_bytes": track.master_bytes,
        "soundcloud_url": track.soundcloud_url,
        "soundcloud_kind": track.soundcloud_kind,
        "duration_ms": track.duration_ms,
        "stream_url": stream_url(track),
    }


def _admin_track(release: Release, track: Track, credits: int) -> dict[str, Any]:
    return {
        "id": str(track.id),
        "version": track.version,
        "release_id": str(release.id),
        "release_title": release.title,
        "number": track.position + 1,
        "title": track.title,
        "slug": track.slug,
        "explicit": track.explicit,
        "audio": _audio(track),
        "has_lyrics": bool(track.lyrics),
        "credit_count": credits,
    }


async def _credit_counts(db: AsyncSession, track_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not track_ids:
        return {}
    rows = await db.execute(
        select(Credit.track_id, func.count())
        .where(Credit.track_id.in_(track_ids))
        .group_by(Credit.track_id)
    )
    return {track_id: int(count) for track_id, count in rows if track_id is not None}


async def _rows(db: AsyncSession, releases: Sequence[Release]) -> list[dict[str, Any]]:
    pictures = await pictures_of(db, releases)
    tracks = await tracks_of(db, [release.id for release in releases])
    return [
        {
            "id": str(release.id),
            "version": release.version,
            "title": release.title,
            "slug": release.slug,
            "kind": release.kind,
            "year": release.year,
            "artist_line": release.artist_line,
            "cover": _cover(pictures.get(release.cover_id) if release.cover_id else None),
            "status": release.status,
            "publish_at": _when(release.publish_at),
            "published_at": _when(release.published_at),
            "track_count": len(tracks[release.id]),
            "unplayable": sum(1 for track in tracks[release.id] if not plays_from(track)),
            "tracklist_to_come": release.tracklist_to_come,
            "updated_at": release.updated_at.isoformat(),
        }
        for release in releases
    ]


async def every_release(db: AsyncSession) -> list[dict[str, Any]]:
    """Every release, newest edit first."""
    found = list(await db.scalars(select(Release).order_by(Release.updated_at.desc(), Release.id)))
    return await _rows(db, found)


async def full_release(db: AsyncSession, release: Release) -> dict[str, Any]:
    [row] = await _rows(db, [release])
    pictures = await pictures_of(db, [release])
    tracks = (await tracks_of(db, [release.id]))[release.id]
    counts = await _credit_counts(db, [track.id for track in tracks])
    credited = await credits_of(db, release_ids=[release.id])
    links = await links_of(db, [release.id])
    moves = await db.scalars(
        select(Move.old_path)
        .where(Move.release_id == release.id, Move.track_id.is_(None))
        .order_by(Move.created_at)
    )
    return {
        **row,
        "credit_line": release.credit_line,
        "summary": release.summary,
        "back_cover": _cover(
            pictures.get(release.back_cover_id) if release.back_cover_id else None
        ),
        "tracks": [_admin_track(release, track, counts.get(track.id, 0)) for track in tracks],
        "credits": credited[release.id],
        "links": links[release.id],
        "moves": [f"{PREFIX}{each}" for each in moves],
        "path": release_path(release),
    }


async def _free(db: AsyncSession, slug: str, release_id: uuid.UUID | None) -> None:
    other = await db.scalar(select(Release).where(Release.slug == slug, Release.id != release_id))
    if other is not None:
        raise _taken(slug, other.title)


async def create_release(
    db: AsyncSession, fields: dict[str, Any], *, by: uuid.UUID | None
) -> Release:
    """A new release, a draft. Its slug, left out, is made from its title."""
    title: str = fields["title"]
    if fields.get("slug"):
        slug = fields["slug"]
        await _free(db, slug, None)
    else:
        slug = await unique_release_slug(db, slug_for(title), None)
    covers: dict[str, uuid.UUID | None] = {}
    for field in ("cover_id", "back_cover_id"):
        value = fields.get(field)
        covers[field] = _uuid(value, field) if value else None
        if covers[field] is not None:
            await _check_cover(db, field, cast(uuid.UUID, covers[field]))
    now = clock.now()
    release = Release(
        id=uuid.uuid4(),
        version=1,
        kind=fields.get("kind") or "album",
        title=title,
        slug=slug,
        year=fields.get("year"),
        artist_line=fields.get("artist_line") or "",
        credit_line=fields.get("credit_line") or "",
        summary=fields.get("summary") or "",
        cover_id=covers["cover_id"],
        back_cover_id=covers["back_cover_id"],
        tracklist_to_come=bool(fields.get("tracklist_to_come")),
        created_at=now,
        updated_at=now,
    )
    db.add(release)
    await _flushed(db, slug)
    await db.execute(delete(Move).where(Move.old_path == slug))
    await _place_covers(db, release)
    audit.record(db, "discography.release.created", actor=by, target=(CONTENT_TYPE, release.id))
    return release


def _changed(problem_of: str, extra: dict[str, Any]) -> Problem:
    return Problem(
        "discography.changed",
        409,
        f"Someone saved this {problem_of} since you opened it. Here is how it reads now.",
        extra=extra,
    )


async def _leave(
    db: AsyncSession, old: str, release_id: uuid.UUID, track_id: uuid.UUID | None
) -> None:
    statement = insert(Move).values(
        old_path=old, release_id=release_id, track_id=track_id, created_at=clock.now()
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[Move.old_path],
            set_={
                "release_id": statement.excluded.release_id,
                "track_id": statement.excluded.track_id,
                "created_at": statement.excluded.created_at,
            },
        )
    )


RELEASE_FIELDS = (
    "title",
    "kind",
    "year",
    "artist_line",
    "credit_line",
    "summary",
    "tracklist_to_come",
)
_CLEARABLE = ("year",)


async def _reorder(db: AsyncSession, release: Release, ids: list[str]) -> None:
    tracks = (await tracks_of(db, [release.id]))[release.id]
    wanted = [_uuid(each, "track_ids") for each in ids]
    if sorted(wanted) != sorted(track.id for track in tracks) or len(set(wanted)) != len(wanted):
        raise _invalid(
            "track_ids",
            "discography.tracks_changed",
            "Send every one of the release's tracks, once.",
        )
    order = {track_id: position for position, track_id in enumerate(wanted)}
    await db.execute(sa.text("SET CONSTRAINTS uq_discography_track_position DEFERRED"))
    for track in tracks:
        if track.position != order[track.id]:
            track.position = order[track.id]
    await db.flush()


async def change_release(
    db: AsyncSession,
    release_id: uuid.UUID,
    version: int,
    fields: dict[str, Any],
    *,
    by: uuid.UUID | None,
) -> Release:
    """Saves the fields sent; 409 `discography.changed` on a stale `version`."""
    release = await get_release(db, release_id, lock=True)
    if version != release.version:
        raise _changed("release", {"release": await full_release(db, release)})
    old_slug = release.slug
    slug = fields.get("slug") or old_slug
    if slug != old_slug:
        await _free(db, slug, release.id)
    for field in ("cover_id", "back_cover_id"):
        if field in fields:
            value = _uuid(fields[field], field) if fields[field] else None
            if value is not None and value != getattr(release, field):
                await _check_cover(db, field, value)
            setattr(release, field, value)
    for name in RELEASE_FIELDS:
        if name not in fields:
            continue
        if fields[name] is None and name not in _CLEARABLE:
            continue
        setattr(release, name, fields[name])
    release.slug = slug
    release.version += 1
    release.updated_at = clock.now()
    await _flushed(db, slug)
    if slug != old_slug:
        await db.execute(delete(Move).where(Move.old_path == slug))
        if release.status == lifecycle.PUBLISHED:
            await _leave(db, old_slug, release.id, None)
            for track in (await tracks_of(db, [release.id]))[release.id]:
                await _leave(db, f"{old_slug}/{track.slug}", release.id, track.id)
    if fields.get("credits") is not None:
        await _replace_credits(db, fields["credits"], release_id=release.id)
    if fields.get("links") is not None:
        await _replace_links(db, release.id, fields["links"])
    if fields.get("track_ids") is not None:
        await _reorder(db, release, fields["track_ids"])
    await _place_covers(db, release)
    await _touched(db, release)
    audit.record(
        db,
        "discography.release.changed",
        actor=by,
        target=(CONTENT_TYPE, release.id),
        details={"moved_from": old_slug} if slug != old_slug else None,
    )
    return release


def _at(text: str) -> datetime:
    try:
        at = datetime.fromisoformat(text)
    except ValueError:
        at = None
    if at is None or at.utcoffset() is None:
        raise _invalid(
            "at",
            "kernel.invalid_request",
            "A time with its zone, such as 2026-12-01T00:00:00-05:00.",
        )
    return at


async def publish(
    db: AsyncSession, release_id: uuid.UUID, at: str | None, *, by: uuid.UUID | None
) -> Release:
    """Live now, or on release day at `at` (the kernel shows it within a minute)."""
    release = await get_release(db, release_id, lock=True)
    if at is None:
        await lifecycle.publish(db, release)
        audit.record(
            db, "discography.release.published", actor=by, target=(CONTENT_TYPE, release.id)
        )
    else:
        when = _at(at)
        await lifecycle.schedule(db, release, when)
        audit.record(
            db,
            "discography.release.scheduled",
            actor=by,
            target=(CONTENT_TYPE, release.id),
            details={"at": when.isoformat()},
        )
    return release


async def unpublish(db: AsyncSession, release_id: uuid.UUID, *, by: uuid.UUID | None) -> Release:
    release = await get_release(db, release_id, lock=True)
    await lifecycle.unpublish(db, release)
    audit.record(db, "discography.release.unpublished", actor=by, target=(CONTENT_TYPE, release.id))
    return release


def _files_of(track: Track) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if track.master_key:
        found.append({"key": track.master_key, "public": False})
    if track.stream_key:
        found.append({"key": track.stream_key, "public": True})
    return found


async def _delete_later(db: AsyncSession, files: list[dict[str, Any]]) -> None:
    if files:
        await jobs.enqueue(db, DELETE_FILES, {"files": files})


async def remove_release(db: AsyncSession, release_id: uuid.UUID, *, by: uuid.UUID | None) -> None:
    """The release gone, with its tracks, credits, links and moves; their files after the commit."""
    from discography.events import ReleaseDeleted

    release = await get_release(db, release_id, lock=True)
    tracks = (await tracks_of(db, [release.id]))[release.id]
    files = [each for track in tracks for each in _files_of(track)]
    slug = release.slug
    await db.delete(release)
    await db.flush()
    await _prune_people(db)
    await media.release(db, owner=owner(release_id))
    await search.remove(db, CONTENT_TYPE, release_id)
    await _delete_later(db, files)
    await events.emit(
        db,
        "discography.release.deleted",
        ReleaseDeleted(release_id=release_id, track_ids=[track.id for track in tracks]),
    )
    audit.record(
        db,
        "discography.release.deleted",
        actor=by,
        target=(CONTENT_TYPE, release_id),
        details={"slug": slug},
    )


# --- the admin: tracks -----------------------------------------------------------------------


async def full_track(db: AsyncSession, track: Track) -> dict[str, Any]:
    release = await get_release(db, track.release_id)
    credited = await credits_of(db, track_ids=[track.id])
    return {
        **_admin_track(release, track, len(credited[track.id])),
        "lyrics": track.lyrics,
        "credits": credited[track.id],
        "peaks": track.peaks,
        "path": track_path(release, track),
    }


async def _next_position(db: AsyncSession, release_id: uuid.UUID) -> int:
    top = await db.scalar(select(func.max(Track.position)).where(Track.release_id == release_id))
    return 0 if top is None else top + 1


async def create_track(
    db: AsyncSession,
    release_id: uuid.UUID,
    title: str,
    soundcloud_url: str | None,
    *,
    by: uuid.UUID | None,
) -> Track:
    """A track at the end of the release: with a SoundCloud link, or no audio yet."""
    release = await get_release(db, release_id, lock=True)
    link, kind = soundcloud_link(soundcloud_url) if soundcloud_url else (None, None)
    now = clock.now()
    track = Track(
        id=uuid.uuid4(),
        version=1,
        release_id=release.id,
        position=await _next_position(db, release.id),
        title=title,
        slug=await unique_track_slug(db, release.id, slug_for(title), None),
        soundcloud_url=link,
        soundcloud_kind=kind,
        audio_state="none",
        created_at=now,
        updated_at=now,
    )
    db.add(track)
    await _flushed(db, track.slug, "track")
    await _touched(db, release)
    audit.record(db, "discography.track.created", actor=by, target=("discography.track", track.id))
    return track


def _clean_name(filename: str | None) -> str:
    text = unicodedata.normalize("NFC", (filename or "").replace("\\", "/").rsplit("/", 1)[-1])
    text = "".join(each for each in text if each.isprintable()).strip()
    return text[:150] or "upload"


def _title_from(name: str, probed: audio.Probe) -> str:
    if probed.title:
        return probed.title[:200]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    words = " ".join(stem.replace("_", " ").split())
    return words[:200] or "Untitled"


def probe(source: BinaryIO, size: int) -> audio.Probe:
    """The master, judged by its bytes: 413, 415 or 422 when it can't be taken."""
    if size > MAX_MASTER_BYTES:
        raise Problem(
            "discography.too_large",
            413,
            "The file is over 60 MB. Export it as FLAC: it keeps every bit at about half the size.",
        )
    try:
        return audio.probe(source)
    except audio.TooLong:
        raise Problem("discography.too_long", 422, ERROR_WORDS["discography.too_long"]) from None
    except audio.Unsupported as error:
        raise Problem("discography.unsupported_rate", 422, str(error)) from None
    except audio.NotAudio:
        raise Problem(
            "discography.not_audio",
            415,
            "That isn't audio this site reads: upload WAV, AIFF, FLAC, Ogg or MP3.",
        ) from None


async def _store_master(
    db: AsyncSession, track: Track, source: BinaryIO, size: int, name: str, probed: audio.Probe
) -> None:
    """The master into the private bucket, and the job queued to make its stream."""
    key = f"discography/masters/{track.id}/{secrets.token_hex(6)}{probed.extension}"
    try:
        await storage.put(key, source, content_type=probed.content_type, filename=name)
    except storage.StorageNotConfigured:
        raise Problem(
            "discography.storage_off",
            503,
            "Uploads need the site's storage. Until it's set up, use a SoundCloud link.",
        ) from None
    old = [{"key": track.master_key, "public": False}] if track.master_key else []
    track.master_key, track.master_name, track.master_bytes = key, name, size
    track.audio_state, track.processing_percent, track.audio_error = "processing", 0, None
    track.updated_at = clock.now()
    await _delete_later(db, old)
    await jobs.enqueue(db, PROCESS, {"track_id": str(track.id), "master_key": key})


async def upload_track(
    db: AsyncSession,
    release_id: uuid.UUID,
    source: BinaryIO,
    size: int,
    filename: str | None,
    *,
    by: uuid.UUID | None,
) -> Track:
    """A new track at the end of the release from an uploaded master, titled
    from its tags or its name, queued for processing."""
    probed = probe(source, size)
    name = _clean_name(filename)
    release = await get_release(db, release_id, lock=True)
    title = _title_from(name, probed)
    now = clock.now()
    track = Track(
        id=uuid.uuid4(),
        version=1,
        release_id=release.id,
        position=await _next_position(db, release.id),
        title=title,
        slug=await unique_track_slug(db, release.id, slug_for(title), None),
        audio_state="none",
        created_at=now,
        updated_at=now,
    )
    db.add(track)
    await _flushed(db, track.slug, "track")
    await _store_master(db, track, source, size, name, probed)
    audit.record(db, "discography.track.uploaded", actor=by, target=("discography.track", track.id))
    return track


async def replace_audio(
    db: AsyncSession,
    track_id: uuid.UUID,
    source: BinaryIO,
    size: int,
    filename: str | None,
    *,
    by: uuid.UUID | None,
) -> Track:
    """A new master for the track: its stream is made again. The old stream
    plays until the new one is ready."""
    probed = probe(source, size)
    track = await get_track(db, track_id, lock=True)
    await _store_master(db, track, source, size, _clean_name(filename), probed)
    track.version += 1
    audit.record(db, "discography.track.uploaded", actor=by, target=("discography.track", track.id))
    return track


async def remove_audio(db: AsyncSession, track_id: uuid.UUID, *, by: uuid.UUID | None) -> Track:
    """The upload gone: the track plays from its link, if it has one."""
    track = await get_track(db, track_id, lock=True)
    files = _files_of(track)
    track.master_key = track.master_name = track.stream_key = None
    track.master_bytes = track.processing_percent = None
    track.audio_error = None
    track.peaks = None
    track.audio_state = "none"
    if not track.soundcloud_url:
        track.duration_ms = None
    track.version += 1
    track.updated_at = clock.now()
    await _delete_later(db, files)
    await _touched(db, await get_release(db, track.release_id))
    audit.record(
        db, "discography.track.audio_removed", actor=by, target=("discography.track", track.id)
    )
    return track


async def retry(db: AsyncSession, track_id: uuid.UUID, *, by: uuid.UUID | None) -> Track:
    track = await get_track(db, track_id, lock=True)
    if not track.master_key or track.audio_state != "failed":
        raise Problem("discography.nothing_to_retry", 409, "Only a failed upload is tried again.")
    track.audio_state, track.processing_percent, track.audio_error = "processing", 0, None
    await jobs.enqueue(db, PROCESS, {"track_id": str(track.id), "master_key": track.master_key})
    return track


TRACK_FIELDS = ("title", "explicit", "lyrics", "duration_ms")


async def change_track(
    db: AsyncSession,
    track_id: uuid.UUID,
    version: int,
    fields: dict[str, Any],
    *,
    by: uuid.UUID | None,
) -> Track:
    track = await get_track(db, track_id, lock=True)
    if version != track.version:
        raise _changed("track", {"track": await full_track(db, track)})
    release = await get_release(db, track.release_id)
    old_slug = track.slug
    slug = fields.get("slug") or old_slug
    if "soundcloud_url" in fields:
        link = fields["soundcloud_url"]
        track.soundcloud_url, track.soundcloud_kind = (
            soundcloud_link(link) if link else (None, None)
        )
    for name in TRACK_FIELDS:
        if name not in fields:
            continue
        value = fields[name]
        if name == "title" and value is None:
            continue
        if name == "lyrics":
            value = value if value and value.strip() else None
        if name == "duration_ms" and track.stream_key:
            continue  # the stream file's own length stands
        setattr(track, name, value)
    if slug != old_slug:
        taken = await db.scalar(
            select(Track).where(
                Track.release_id == track.release_id, Track.slug == slug, Track.id != track.id
            )
        )
        if taken is not None:
            raise _taken(slug, taken.title, "track")
    track.slug = slug
    track.version += 1
    track.updated_at = clock.now()
    await _flushed(db, slug, "track")
    if slug != old_slug:
        await db.execute(delete(Move).where(Move.old_path == f"{release.slug}/{slug}"))
        if release.status == lifecycle.PUBLISHED:
            await _leave(db, f"{release.slug}/{old_slug}", release.id, track.id)
    if fields.get("credits") is not None:
        await _replace_credits(db, fields["credits"], track_id=track.id)
    await _touched(db, release)
    audit.record(db, "discography.track.changed", actor=by, target=("discography.track", track.id))
    return track


async def remove_track(db: AsyncSession, track_id: uuid.UUID, *, by: uuid.UUID | None) -> None:
    from discography.events import TrackDeleted

    track = await get_track(db, track_id, lock=True)
    release = await get_release(db, track.release_id, lock=True)
    files = _files_of(track)
    await db.delete(track)
    await db.flush()
    await db.execute(sa.text("SET CONSTRAINTS uq_discography_track_position DEFERRED"))
    for position, each in enumerate((await tracks_of(db, [release.id]))[release.id]):
        each.position = position
    await db.flush()
    await _prune_people(db)
    await _delete_later(db, files)
    await events.emit(
        db, "discography.track.deleted", TrackDeleted(track_id=track_id, release_id=release.id)
    )
    await _touched(db, release)
    audit.record(db, "discography.track.deleted", actor=by, target=("discography.track", track_id))


SHOWS = ("all", "cant_play", "no_lyrics", "no_credits")


async def every_track(
    db: AsyncSession, *, q: str | None, show: str, cursor: str | None, limit: int = ADMIN_PER_PAGE
) -> dict[str, Any]:
    """Every track on every release, by release then place: the Tracks board."""
    statement = select(Track, Release).join(Release, Release.id == Track.release_id)
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        statement = statement.where(or_(Track.title.ilike(like), Release.title.ilike(like)))
    if show == "cant_play":
        statement = statement.where(~playable_clause())
    elif show == "no_lyrics":
        statement = statement.where(Track.lyrics.is_(None))
    elif show == "no_credits":
        statement = statement.where(~sa.exists().where(Credit.track_id == Track.id))
    offset = 0
    if cursor is not None:
        if not cursor.isdigit() or len(cursor) > 6:
            raise _invalid("cursor", "kernel.invalid_request", "Not a page of these tracks.")
        offset = int(cursor)
    rows = list(
        await db.execute(
            statement.order_by(Release.updated_at.desc(), Release.id, Track.position)
            .offset(offset)
            .limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    counts = await _credit_counts(db, [track.id for track, _ in rows])
    total = await db.scalar(select(func.count()).select_from(Track)) or 0
    releases = await db.scalar(select(func.count(sa.distinct(Track.release_id)))) or 0
    return {
        "items": [_admin_track(release, track, counts.get(track.id, 0)) for track, release in rows],
        "next_cursor": str(offset + limit) if more else None,
        "total": total,
        "releases": releases,
    }


# --- people, roles and the artist's links ----------------------------------------------------


async def every_person(db: AsyncSession) -> dict[str, Any]:
    people = list(await db.scalars(select(Person).order_by(func.lower(Person.name))))
    rows = await db.execute(
        select(Credit.person_id, Role.name, Release.title, Credit.track_id)
        .join(Role, Role.id == Credit.role_id)
        .outerjoin(Track, Track.id == Credit.track_id)
        .join(Release, Release.id == sa.func.coalesce(Credit.release_id, Track.release_id))
        .order_by(Release.title, Role.position)
    )
    seen: dict[uuid.UUID, dict[str, list[str]]] = {}
    counts: dict[uuid.UUID, int] = {}
    for person_id, role, title, _ in rows:
        roles = seen.setdefault(person_id, {}).setdefault(title, [])
        if role not in roles:
            roles.append(role)
        counts[person_id] = counts.get(person_id, 0) + 1
    items = []
    for person in people:
        by_release = seen.get(person.id, {})
        credited = "; ".join(
            f"{' and '.join(roles)}, {title}" for title, roles in by_release.items()
        )
        items.append(
            {
                "id": str(person.id),
                "version": person.version,
                "name": person.name,
                "profile": person.profile,
                "roster_profile_id": (
                    str(person.roster_profile_id) if person.roster_profile_id else None
                ),
                "credited_for": credited,
                "credits": counts.get(person.id, 0),
            }
        )
    return {"items": items, "unlinked": sum(1 for p in people if p.profile == "unlinked")}


async def change_person(
    db: AsyncSession,
    person_id: uuid.UUID,
    version: int,
    fields: dict[str, Any],
    *,
    by: uuid.UUID | None,
) -> Person:
    person = await db.scalar(select(Person).where(Person.id == person_id).with_for_update())
    if person is None:
        raise _not_found("person")
    if version != person.version:
        raise Problem("discography.changed", 409, "Someone changed this name since you opened it.")
    if fields.get("name"):
        clash = await db.scalar(
            select(Person).where(
                func.lower(Person.name) == fields["name"].lower(), Person.id != person.id
            )
        )
        if clash is not None:
            raise _invalid("name", "discography.name_taken", f"{clash.name} is credited already.")
        person.name = fields["name"]
    if fields.get("profile"):
        person.profile = fields["profile"]
        person.roster_profile_id = None
    person.version += 1
    person.updated_at = clock.now()
    await db.flush()
    audit.record(
        db, "discography.person.changed", actor=by, target=("discography.person", person.id)
    )
    return person


async def every_role(db: AsyncSession) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(Role, func.count(Credit.id))
        .outerjoin(Credit, Credit.role_id == Role.id)
        .group_by(Role.id)
        .order_by(Role.position)
    )
    return [{"id": str(role.id), "name": role.name, "credits": count} for role, count in rows]


async def put_roles(db: AsyncSession, items: list[dict[str, Any]], *, by: uuid.UUID | None) -> None:
    """The whole list, in order. A role left out goes; 409 if a credit names it."""
    names = [each["name"].lower() for each in items]
    if len(set(names)) != len(names):
        raise _invalid("items", "discography.role_twice", "Each role once.")
    current = {role.id: role for role in await db.scalars(select(Role).with_for_update())}
    kept: set[uuid.UUID] = set()
    for each in items:
        if each.get("id"):
            role_id = _uuid(each["id"], "items")
            if role_id not in current:
                raise _invalid("items", "discography.role_not_found", "That role is gone.")
            kept.add(role_id)
    gone = [role_id for role_id in current if role_id not in kept]
    if gone:
        used = await db.scalar(
            select(Role.name)
            .join(Credit, Credit.role_id == Role.id)
            .where(Role.id.in_(gone))
            .limit(1)
        )
        if used is not None:
            raise Problem(
                "discography.role_in_use", 409, f"Credits name {used}: change them before it goes."
            )
        await db.execute(delete(Role).where(Role.id.in_(gone)))
    for role in current.values():  # out of the way of the new names and places
        role.name, role.position = f"~{role.id}", 1000 + role.position
    await db.flush()
    for position, each in enumerate(items):
        if each.get("id"):
            role = current[_uuid(each["id"], "items")]
            role.name, role.position = each["name"], position
        else:
            db.add(Role(id=uuid.uuid4(), name=each["name"], position=position))
    await db.flush()
    audit.record(db, "discography.roles.changed", actor=by)


async def put_artist_links(db: AsyncSession, urls: list[str], *, by: uuid.UUID | None) -> None:
    await _replace_links(db, None, urls)
    audit.record(db, "discography.links.changed", actor=by)


# --- the dashboard ---------------------------------------------------------------------------


async def unplayable_live(db: AsyncSession) -> tuple[Release, Track] | None:
    """The first track on a live release that can't play."""
    row = (
        await db.execute(
            select(Release, Track)
            .join(Track, Track.release_id == Release.id)
            .where(lifecycle.visible(Release), ~playable_clause())
            .order_by(Release.published_at.desc(), Track.position)
            .limit(1)
        )
    ).first()
    return None if row is None else (row[0], row[1])


async def failed_upload(db: AsyncSession) -> tuple[Release, Track] | None:
    row = (
        await db.execute(
            select(Release, Track)
            .join(Track, Track.release_id == Release.id)
            .where(Track.audio_state == "failed")
            .order_by(Track.updated_at.desc())
            .limit(1)
        )
    ).first()
    return None if row is None else (row[0], row[1])
