"""Dashboard cards (hook 8, decision 0052): images a screen reader would say
nothing of need the staff who describe them, and uploads need the public bucket."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kernel import attention, setup
from media import service


async def _bucket_on(db: AsyncSession) -> bool:
    return service.storage_on()


SETUP = (
    setup.Step(
        key="media.public_bucket",
        title="Turn on the public bucket for images",
        why="The media library stores every image there, so nothing can be uploaded until it's set.",
        link="/admin/settings/system",
        permission="media.image.manage",
        done=_bucket_on,
    ),
)


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    missing = await service.count_missing_alt(db)
    if not missing:
        return []
    images = "image has" if missing == 1 else "images have"
    return [
        attention.Item(
            key="media.missing_alt",
            tone="warning",
            what=f"{missing} {images} no alt text",
            why="People using screen readers hear nothing for them, and search engines can't tell what they show.",
            label="Fix the first",
            to="/admin/media?missing_alt=1",
            permission="media.image.manage",
        )
    ]


ATTENTION = _attention
