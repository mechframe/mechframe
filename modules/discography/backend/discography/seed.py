"""discography: its seed data (kernel.seed, hook 4, decision 0052).

A live album of three tracks, each a few seconds of a generated tone: with
storage on, each is stored as its master and processed by the real job, so
the waveform and the stream are real; with storage off, each is "No audio
yet" (and the dashboard says so). A live single that plays from a SoundCloud
link, a draft EP with no tracks, credits on the album and its first track,
and the artist's own links. Each has a fixed id, so a second run finds them
and changes nothing; a slug another release already has is left to it. The
roles are the migration's. Each track it makes has two weeks of daily plays,
rising, through audio-player's `add_daily` (0.1.1), so the Dashboard's card
has figures.
"""

from __future__ import annotations

import io
import math
import struct
import uuid
import wave
from datetime import timedelta

from audio_player import public as audio_player
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from discography.models import Credit, Link, Person, Release, Role, Track
from kernel import clock, jobs, lifecycle, storage
from kernel import seed as seeding

_NAMESPACE = uuid.UUID("5c6f1e2a-9b3d-4c8e-a7f0-3d2b6e9a1c55")
ARTIST = "The Night Shift Collective"
#: Slug, title, kind, year, state, summary, then the tracks: title, a tone in Hz.
RELEASES = (
    (
        "first-light",
        "First Light",
        "album",
        2025,
        "live",
        "Three tracks recorded live in one night.",
        (("Morning Call", 220.0), ("Long Road", 277.18), ("Home Again", 329.63)),
    ),
    ("overtime", "Overtime", "single", 2026, "live", "The new single.", (("Overtime", 0.0),)),
    ("night-sessions", "Night Sessions", "ep", 2026, "draft", "Four tracks, coming soon.", ()),
)
SINGLE_LINK = "https://soundcloud.com/night-shift-collective/overtime"
#: Each track's plays on the first of the two weeks; a day later, half a play more.
DAILY_PLAYS = {"Morning Call": 48, "Long Road": 31, "Home Again": 22, "Overtime": 37}
PLAYED_DAYS = 14
ARTIST_LINKS = (
    "https://open.spotify.com/artist/0000000000000000000000",
    "https://soundcloud.com/night-shift-collective",
)


def tone(hz: float, seconds: float = 4.0, rate: int = 44100) -> bytes:
    """A WAV of a sine at `hz`, fading in and out."""
    frames = int(seconds * rate)
    out = io.BytesIO()
    with wave.open(out, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(rate)
        file.writeframes(
            b"".join(
                struct.pack(
                    "<h",
                    int(
                        12000
                        * math.sin(2 * math.pi * hz * n / rate)
                        * min(1.0, n / rate, (frames - n) / rate)
                    ),
                )
                for n in range(frames)
            )
        )
    return out.getvalue()


async def _master(db: AsyncSession, track: Track, hz: float) -> None:
    data = tone(hz)
    key = f"discography/masters/{track.id}/seed.wav"
    try:
        await storage.put(key, data, content_type="audio/wav", filename=f"{track.slug}.wav")
    except storage.StorageNotConfigured:
        return
    track.master_key, track.master_name, track.master_bytes = key, f"{track.slug}.wav", len(data)
    track.audio_state, track.processing_percent = "processing", 0
    await jobs.enqueue(db, service.PROCESS, {"track_id": str(track.id), "master_key": key})


async def _plays(db: AsyncSession, track: Track) -> None:
    """Two weeks of plays ending today, more each week than the one before.
    Today is the real one, not the seed's fixed `ctx.now`: the card reads the
    last two weeks, and plays dated then would never show. A second run makes
    no track, so it writes none again."""
    base = DAILY_PLAYS.get(track.title, 20)
    today = clock.now().date()
    for back in range(PLAYED_DAYS):
        plays = base + (PLAYED_DAYS - 1 - back) // 2
        await audio_player.add_daily(
            db, service.PLAYS, track.id, today - timedelta(days=back), plays
        )


async def _credit(
    db: AsyncSession, ctx: seeding.Context, name: str, role: str, **on: uuid.UUID
) -> None:
    # A name credited already is that person, whatever their id (CodeRabbit on #145).
    there = await db.scalar(select(Person.id).where(func.lower(Person.name) == name.lower()))
    person_id = there or uuid.uuid5(_NAMESPACE, f"person:{name}")
    if there is None:
        profile = "collective" if name == ARTIST else "unlinked"
        db.add(
            Person(
                id=person_id,
                version=1,
                name=name,
                profile=profile,
                created_at=ctx.now,
                updated_at=ctx.now,
            )
        )
        await db.flush()
    role_id = await db.scalar(select(Role.id).where(Role.name == role))
    if role_id is None:
        return
    db.add(Credit(id=uuid.uuid4(), person_id=person_id, role_id=role_id, position=0, **on))


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    for slug, title, kind, year, state, summary, tracks in RELEASES:
        release_id = uuid.uuid5(_NAMESPACE, slug)
        taken = await db.scalar(
            select(Release.id).where(or_(Release.id == release_id, Release.slug == slug))
        )
        if taken is not None:
            continue
        release = Release(
            id=release_id,
            version=1,
            kind=kind,
            title=title,
            slug=slug,
            year=year,
            artist_line=ARTIST,
            credit_line="Produced by The Night Shift Collective." if kind == "album" else "",
            summary=summary,
            tracklist_to_come=kind == "ep",
            created_at=ctx.now,
            updated_at=ctx.now,
        )
        db.add(release)
        await db.flush()
        for position, (track_title, hz) in enumerate(tracks):
            track = Track(
                id=uuid.uuid5(_NAMESPACE, f"{slug}/{position}"),
                version=1,
                release_id=release.id,
                position=position,
                title=track_title,
                slug=service.slug_for(track_title),
                audio_state="none",
                created_at=ctx.now,
                updated_at=ctx.now,
            )
            if hz:
                db.add(track)
                await db.flush()
                await _master(db, track, hz)
            else:
                track.soundcloud_url, track.soundcloud_kind = SINGLE_LINK, "track"
                track.duration_ms = 201_000
                db.add(track)
            await db.flush()
            await _plays(db, track)
            if position == 0 and kind == "album":
                await _credit(db, ctx, "Ada Moreno", "Written by", track_id=track.id)
        if kind == "album":
            await _credit(db, ctx, ARTIST, "Artist", release_id=release.id)
            await _credit(db, ctx, "Sam Okafor", "Mastered by", release_id=release.id)
        if state == "live":
            release.published_at = ctx.now
            await lifecycle.publish(db, release)
    if not await db.scalar(select(Link.id).where(Link.release_id.is_(None)).limit(1)):
        for position, url in enumerate(ARTIST_LINKS):
            platform, _ = service.platform_of(url)
            db.add(
                Link(
                    id=uuid.uuid5(_NAMESPACE, url),
                    release_id=None,
                    platform=platform,
                    url=url,
                    position=position,
                )
            )
    await db.flush()
