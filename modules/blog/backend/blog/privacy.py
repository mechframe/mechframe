"""Export and erase (hook 7, decision 0052): what blog keeps about a person is
the posts they wrote. Export lists them; erase keeps the posts as the site's
and forgets who wrote them."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from blog.models import Post
from kernel import privacy


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(Post).where(Post.author_id == subject.user_id).order_by(Post.created_at, Post.id)
    )
    return {
        "posts": [
            {
                "id": str(row.id),
                "title": row.title,
                "address": f"/blog/{row.slug}",
                "status": row.status,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "written_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    await db.execute(update(Post).where(Post.author_id == subject.user_id).values(author_id=None))
