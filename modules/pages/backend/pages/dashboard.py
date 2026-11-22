"""Dashboard cards (hook 8, decision 0052): a site that takes people's email
addresses needs a privacy page, so "Needs you" asks for one while no page at
/privacy is live. Its Write it opens the page there if one is drafted, or a new
page at that address with a few headings to fill."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import attention, lifecycle
from pages.models import Page

PRIVACY = "/privacy"


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    found = await db.scalar(select(Page).where(Page.address == PRIVACY))
    if found is not None and found.status == lifecycle.PUBLISHED:
        return []
    return [
        attention.Item(
            key="pages.no_privacy",
            tone="warning",
            what="There's no privacy page yet",
            why=(
                "The site takes people's email addresses when they sign up, "
                "so it should say how they're used."
            ),
            label="Write it",
            to=(
                f"/admin/pages/{found.id}"
                if found is not None
                else "/admin/pages/new?address=privacy"
            ),
            permission="pages.page.write",
        )
    ]


ATTENTION = _attention
SETUP: tuple[Any, ...] = ()
