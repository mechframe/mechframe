"""Export and erase (hook 7, decision 0052): social keeps who shared each
post, by their account and their name as it was then, which is their address
when they had no name. Export lists the shares a person sent, found by either;
erase clears who sent them and keeps the shares, which are the site's posts,
not the person's."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import privacy
from social.models import Share


def _theirs(subject: privacy.Subject) -> sa.ColumnElement[bool]:
    # The address matches only a share that names no account: a name is any
    # words someone chose, an address among them (CodeRabbit on #152).
    return sa.or_(
        Share.sent_by_id == subject.user_id,
        sa.and_(
            Share.sent_by_id.is_(None),
            func.lower(Share.sent_by_name) == subject.email.strip().lower(),
        ),
    )


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(select(Share).where(_theirs(subject)).order_by(Share.created_at))
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
    await db.execute(update(Share).where(_theirs(subject)).values(sent_by_id=None, sent_by_name=""))
