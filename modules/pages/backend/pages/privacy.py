"""Export and erase (hook 7, decision 0052): what pages keeps about a person
is which pages they changed last. Export lists them; erase keeps the pages as
the site's and forgets who changed them."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import privacy
from pages.models import Page


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(Page).where(Page.updated_by == subject.user_id).order_by(Page.address)
    )
    return {
        "pages": [
            {
                "id": str(row.id),
                "title": row.title,
                "address": row.address,
                "status": row.status,
                "last_changed_at": row.updated_at.isoformat(),
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    await db.execute(update(Page).where(Page.updated_by == subject.user_id).values(updated_by=None))
