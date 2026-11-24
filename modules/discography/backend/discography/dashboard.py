"""Dashboard cards (hook 8, decision 0052). "Needs you" says so while a live
release has a track that can't play (it's hidden from the site, and the deck
skips it), and while an upload failed. Setup asks for storage's two buckets,
which uploads need."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from kernel import attention, setup
from kernel.config import get_config

MANAGE = "discography.release.manage"


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    items: list[attention.Item] = []
    found = await service.unplayable_live(db)
    if found is not None:
        release, track = found
        items.append(
            attention.Item(
                key="discography.cant_play",
                tone="danger",
                what=f"{track.title} can't play",
                why=(
                    f"It's on {release.title}, which is live, but it has no audio file or link, "
                    "so it's hidden from the tracklist."
                ),
                label="Add audio",
                to=f"/admin/music/{release.id}",
                permission=MANAGE,
            )
        )
    failed = await service.failed_upload(db)
    if failed is not None:
        release, track = failed
        items.append(
            attention.Item(
                key="discography.upload_failed",
                tone="warning",
                what=f"{track.title}'s upload didn't work",
                why=service.ERROR_WORDS.get(
                    track.audio_error or "", "Its stream couldn't be made."
                ),
                label="Open the track",
                to=f"/admin/music/tracks?track={track.id}",
                permission=MANAGE,
            )
        )
    return items


async def _storage_on(db: AsyncSession) -> bool:
    config = get_config()
    return bool(
        config.storage_bucket and config.storage_public_bucket and config.storage_public_url
    )


ATTENTION = _attention
SETUP: tuple[Any, ...] = (
    setup.Step(
        key="discography.storage",
        title="Turn on storage for uploaded tracks",
        why=(
            "Uploads keep the master private and play a stream file from the public bucket. "
            "Until both buckets are set, tracks play from SoundCloud links only."
        ),
        link="/admin/settings/system",
        permission=MANAGE,
        done=_storage_on,
    ),
)
