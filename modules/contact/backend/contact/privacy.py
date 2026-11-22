"""Export and erase (hook 7, decision 0052): contact keeps the messages a
person sent, found by their address, whatever its case, or by their account
when they were signed in. Export lists them; erase deletes them."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from contact import service
from contact.models import Message
from kernel import privacy


def _theirs(subject: privacy.Subject) -> sa.ColumnElement[bool]:
    return sa.or_(
        Message.email_normal == service.normal(subject.email),
        Message.user_id == subject.user_id,
    )


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(Message).where(_theirs(subject)).order_by(Message.received_at, Message.id)
    )
    return {
        "messages": [
            {
                "sent_at": row.received_at.isoformat(),
                "name": row.name,
                "email": row.email,
                "topic": row.topic_label,
                "message": row.message,
                "wants_news": row.wants_news,
                "status": row.status,
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    await db.execute(delete(Message).where(_theirs(subject)))
