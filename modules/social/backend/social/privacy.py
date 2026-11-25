"""Export and erase (hook 7, decision 0052): social keeps who shared each
post, by their account and their name as it was then. Export lists the shares
a person sent; erase clears who sent them and keeps the shares, which are the
site's posts, not the person's."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import privacy
from social.models import Share


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(Share).where(Share.sent_by_id == subject.user_id).order_by(Share.created_at)
    )
    return {
        "social_shares": [
            {
                "shared": f"{row.content_type} {row.content_id}",
                "channel": row.channel_name,
                "text": row.text,
                "link": row.link,
                "state": row.state,
                "shared_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    await db.execute(
        update(Share)
        .where(Share.sent_by_id == subject.user_id)
        .values(sent_by_id=None, sent_by_name="")
    )
