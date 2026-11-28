"""Export and erase (hook 7, decision 0052): what portfolio keeps about a
person is the pieces credited to them. Export lists them; erase keeps the
pieces as the site's and forgets who made them (blog's)."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle, privacy, search
from portfolio import service
from portfolio.models import Piece


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(Piece).where(Piece.artist_id == subject.user_id).order_by(Piece.created_at, Piece.id)
    )
    return {
        "pieces": [
            {
                "id": str(row.id),
                "title": row.title,
                "address": service.path(row),
                "year": row.year,
                "about": row.about,
                "video": row.video_url,
                "status": row.status,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "added_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    """The credit removed, and each live piece's search document written
    again, since it held the artist's name."""
    credited = list(await db.scalars(select(Piece).where(Piece.artist_id == subject.user_id)))
    await db.execute(update(Piece).where(Piece.artist_id == subject.user_id).values(artist_id=None))
    for piece in credited:
        await db.refresh(piece)
        if piece.status == lifecycle.PUBLISHED:
            await search.index(db, await service.document(db, piece))
