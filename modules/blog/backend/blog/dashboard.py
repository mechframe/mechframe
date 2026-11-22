"""Dashboard cards (hook 8, decision 0052): a scheduled post with no cover
goes up as a plain card on the blog and when it's shared, so "Needs you" says
so while one is waiting, the soonest first. Its Add a cover opens the post."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from blog import service
from kernel import attention


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    found = await service.needs_cover(db)
    if found is None or found.publish_at is None:
        return []
    return [
        attention.Item(
            key="blog.no_cover",
            tone="warning",
            what="A scheduled post has no cover image",
            why=(
                f"{found.title} is scheduled to go up. Without a cover, it shows a plain "
                "card on the blog and when it's shared."
            ),
            label="Add a cover",
            to=f"/admin/blog/{found.id}",
            permission="blog.post.write",
        )
    ]


ATTENTION = _attention
SETUP: tuple[Any, ...] = ()
