"""discography's jobs (kernel.jobs, decision 0035).

`discography.process_track` makes a track's stream file, duration and peaks
from its master. It reads the track in a short session, works on the files
outside any (a session held through a long job holds a connection), writes
its percent as it goes, and commits its result only if the track still has
the master it started from: a master replaced meanwhile throws the result
away, and the new master's own job makes the stream. At least once: run
twice, it makes the same file again under a new name and lets the first go.

`discography.delete_files` removes masters and stream files after the commit
that dropped them; a file already gone counts as done.
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from typing import Any, BinaryIO, cast

from sqlalchemy import select

from discography import audio, service
from discography.events import TrackProcessed
from discography.models import Track
from kernel import events, jobs, storage

#: How often a running job writes its percent, in seconds.
PROGRESS_EVERY = 2.0


async def _fail(ctx: jobs.Context, track_id: uuid.UUID, master_key: str, code: str) -> None:
    async with ctx.sessions() as db:
        track = await db.scalar(select(Track).where(Track.id == track_id).with_for_update())
        if track is not None and track.master_key == master_key:
            track.audio_state, track.audio_error, track.processing_percent = "failed", code, None
            await db.commit()


async def _percent(ctx: jobs.Context, track_id: uuid.UUID, master_key: str, percent: int) -> None:
    async with ctx.sessions() as db:
        track = await db.scalar(select(Track).where(Track.id == track_id))
        if track is not None and track.master_key == master_key:
            track.processing_percent = percent
            await db.commit()


@jobs.handler(service.PROCESS, tries=3, timeout=1800)
async def process_track(ctx: jobs.Context, payload: dict[str, Any]) -> None:
    track_id, master_key = uuid.UUID(payload["track_id"]), str(payload["master_key"])
    async with ctx.sessions() as db:
        track = await db.scalar(select(Track).where(Track.id == track_id))
        if track is None or track.master_key != master_key:
            return  # gone, or another master's job has it
        kbps = (await service.settings_of(db)).stream_bitrate_kbps
    with tempfile.TemporaryFile() as master_file, tempfile.TemporaryFile() as stream_file:
        master, stream = cast(BinaryIO, master_file), cast(BinaryIO, stream_file)
        if not await storage.download(master_key, master):
            await _fail(ctx, track_id, master_key, "discography.master_missing")
            return
        heard: list[int] = [0]
        work = asyncio.ensure_future(
            asyncio.to_thread(audio.make_stream, master, stream, kbps=kbps, progress=heard.append)
        )
        told = 0
        while not work.done():
            await asyncio.wait([work], timeout=PROGRESS_EVERY)
            if not work.done() and heard[-1] != told:
                told = heard[-1]
                await _percent(ctx, track_id, master_key, told)
        try:
            made = work.result()
        except audio.TooLong:
            await _fail(ctx, track_id, master_key, "discography.too_long")
            return
        except audio.Unsupported:
            await _fail(ctx, track_id, master_key, "discography.unsupported_rate")
            return
        except audio.NotAudio:
            await _fail(ctx, track_id, master_key, "discography.not_audio")
            return
        stream.seek(0)
        key = storage.unguessable_key("discography/stream", ".mp3")
        await storage.put(key, stream, content_type="audio/mpeg", public=True)
    async with ctx.sessions() as db:
        track = await db.scalar(select(Track).where(Track.id == track_id).with_for_update())
        if track is None or track.master_key != master_key:
            await service._delete_later(db, [{"key": key, "public": True}])
            await db.commit()
            return
        old = [{"key": track.stream_key, "public": True}] if track.stream_key else []
        track.stream_key, track.duration_ms, track.peaks = key, made.duration_ms, made.peaks
        track.audio_state, track.processing_percent, track.audio_error = "ready", 100, None
        await service._delete_later(db, old)
        await events.emit(
            db,
            "discography.track.processed",
            TrackProcessed(
                track_id=track.id, release_id=track.release_id, duration_ms=made.duration_ms
            ),
        )
        release = await service.get_release(db, track.release_id)
        await service._touched(db, release)
        await db.commit()


@jobs.handler(service.DELETE_FILES, tries=5, timeout=300)
async def delete_files(ctx: jobs.Context, payload: dict[str, Any]) -> None:
    for each in payload.get("files") or []:
        await storage.delete(str(each["key"]), public=bool(each.get("public")))
