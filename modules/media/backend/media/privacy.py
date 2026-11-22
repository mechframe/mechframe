"""Export and erase (hook 7, decision 0052): what the library keeps about a
person is which images they uploaded. Export lists them; erase keeps them as
the site's and forgets who uploaded them."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, privacy
from media import service
from media.models import MediaImage


def _address(row: MediaImage) -> str | None:
    """The image's address, or None while the public bucket is off: the copy
    of a person's data never waits on it (CodeRabbit on #116)."""
    try:
        return service.url(row)
    except Problem:
        return None


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(MediaImage)
        .where(MediaImage.uploaded_by == subject.user_id)
        .order_by(MediaImage.created_at)
    )
    return {
        "images": [
            {
                "id": str(row.id),
                "url": _address(row),
                "filename": row.filename,
                "alt": row.alt,
                "uploaded_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    await db.execute(
        update(MediaImage).where(MediaImage.uploaded_by == subject.user_id).values(uploaded_by=None)
    )
