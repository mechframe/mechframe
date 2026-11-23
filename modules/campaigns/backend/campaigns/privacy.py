"""Export and erase (hook 7, decision 0052): campaigns keeps a person's
subscription, found by their address, whatever its case, or by their account
when they signed up signed in. Export lists it and whether the address is set
aside; erase deletes it and keeps a set-aside row, so the address is never
emailed again (the one thing a suppression list must remember)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import service
from campaigns.models import SetAside, Subscriber
from kernel import privacy


def _theirs(subject: privacy.Subject) -> sa.ColumnElement[bool]:
    return sa.or_(
        Subscriber.email_normal == service.normal(subject.email),
        Subscriber.user_id == subject.user_id,
    )


def _iso(value: object) -> str | None:
    return None if value is None else value.isoformat()  # type: ignore[attr-defined]


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = list(
        await db.scalars(select(Subscriber).where(_theirs(subject)).order_by(Subscriber.created_at))
    )
    addresses = {service.normal(subject.email), *(row.email_normal for row in rows)}
    aside = await db.scalars(
        select(SetAside).where(SetAside.email_normal.in_(addresses)).order_by(SetAside.since)
    )
    return {
        "newsletter": [
            {
                "email": row.email,
                "name": row.name,
                "source": row.source,
                "status": row.status,
                "asked_at": row.created_at.isoformat(),
                "confirmed_at": _iso(row.confirmed_at),
                "unsubscribed_at": _iso(row.unsubscribed_at),
            }
            for row in rows
        ],
        "newsletter_set_aside": [
            {"email": row.email_normal, "why": row.why, "since": row.since.isoformat()}
            for row in aside
        ],
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    for row in list(await db.scalars(select(Subscriber).where(_theirs(subject)))):
        await service.forget(db, row, "Erased at their request")
