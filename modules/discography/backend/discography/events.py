"""discography's events (SPEC.md section 11, decision 0036).

`discography.release.published` goes out once a release, the first time it
goes live, whether at once or on its release day: discography hears the
kernel's `kernel.content.published` for its type, and `announced_at` keeps it
to once. `discography.release.changed` says a live release or one of its
tracks was saved, for a homepage's cache. The deleted events let `featured`
drop its placements; `discography.track.processed` says a stream file is ready.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from discography.models import Release
from kernel import clock, events, jobs, lifecycle

CONTENT_TYPE = "discography.release"


@events.payload("discography.release.published", v=1)
class ReleasePublished(events.Payload):
    """A release went live for the first time."""

    release_id: uuid.UUID
    slug: str
    title: str
    kind: str
    #: Its page: /music/<slug>.
    path: str


@events.payload("discography.release.changed", v=1)
class ReleaseChanged(events.Payload):
    """A live release, or one of its tracks, changed on the site."""

    release_id: uuid.UUID


@events.payload("discography.release.deleted", v=1)
class ReleaseDeleted(events.Payload):
    release_id: uuid.UUID
    #: Its tracks, gone with it.
    track_ids: list[uuid.UUID]


@events.payload("discography.track.processed", v=1)
class TrackProcessed(events.Payload):
    """A track's stream file, duration and peaks are ready."""

    track_id: uuid.UUID
    release_id: uuid.UUID
    duration_ms: int


@events.payload("discography.track.deleted", v=1)
class TrackDeleted(events.Payload):
    track_id: uuid.UUID
    release_id: uuid.UUID


async def _announce(ctx: jobs.Context, event: events.Event) -> None:
    heard = event.parse(events.ContentPublished)
    if heard.type != CONTENT_TYPE:
        return
    async with ctx.sessions() as db:
        release = await db.scalar(select(Release).where(Release.id == heard.id).with_for_update())
        if (
            release is None
            or release.announced_at is not None
            or release.status != lifecycle.PUBLISHED
        ):
            return
        release.announced_at = clock.now()
        await events.emit(
            db,
            "discography.release.published",
            ReleasePublished(
                release_id=release.id,
                slug=release.slug,
                title=release.title,
                kind=release.kind,
                path=f"/music/{release.slug}",
            ),
        )
        await db.commit()


ANNOUNCE = events.on("kernel.content.published", "discography.announce_published")(_announce)
