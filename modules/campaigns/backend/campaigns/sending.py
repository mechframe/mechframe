"""The send job's work (`dev plans/contracts/campaigns.md` §2, "Sending"),
from VybeSite's `campaign_service.py`: the audience fixed once, batches at a
pace, and each recipient asked again before their turn.

Each run of `campaigns.send`:

1. **Starts what's due:** a scheduled email whose time has come gets its
   deliveries (`service.start`), the audience as it stands now.
2. **Queues at the pace:** a sixtieth of `send_per_hour`, at least one, less
   what went out in the last minute, so an extra run (Send now queues one)
   never doubles the pace. On a host with a limit, that leaves room for the
   site's own mail, which goes out through the same mailbox.
3. **Asks again for each recipient:** still subscribed and not set aside, or
   their row goes unsent. An address that left mid-send is skipped.
4. **Queues each copy** through the kernel's mail queue (decision 0062), with
   the person's own unsubscribe link and RFC 8058's headers, in the same
   transaction as marking the row queued: a run that dies sends nothing, and
   a run twice finds nothing left to send.
5. **Finishes:** an email with every row queued is `sent`.

Nothing sends while the postal address is missing: the rows wait for it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import render, service
from campaigns.models import Delivery, Email, SetAside, Subscriber
from kernel import clock, crypto, email

#: The window the pace is counted over.
MINUTE = timedelta(minutes=1)


def per_minute(send_per_hour: int) -> int:
    """A sixtieth of the hourly pace, at least one."""
    return max(1, send_per_hour // 60)


async def run(db: AsyncSession) -> int:
    """One run of the send job, in the caller's transaction. Answers how many
    copies it queued."""
    now = clock.now()
    cfg = await service.current(db)
    ready = bool(cfg.postal_address.strip())
    if ready:
        due = list(
            await db.scalars(
                select(Email)
                .where(Email.status == "scheduled", Email.send_at <= now)
                .order_by(Email.send_at, Email.id)
                .with_for_update(skip_locked=True)
            )
        )
        for row in due:
            await service.start(db, row, now)
        await db.flush()
    queued = await _queue(db, cfg.send_per_hour, now) if ready else 0
    await _finish(db, now)
    return queued


async def _queue(db: AsyncSession, send_per_hour: int, now: datetime) -> int:
    recent = await db.scalar(
        select(func.count()).select_from(Delivery).where(Delivery.queued_at > now - MINUTE)
    )
    allowance = per_minute(send_per_hour) - int(recent or 0)
    if allowance <= 0:
        return 0
    rows: list[tuple[Delivery, Email]] = [
        (delivery, row)
        for delivery, row in (
            await db.execute(
                select(Delivery, Email)
                .join(Email, Delivery.email_id == Email.id)
                .where(Email.status == "sending", Delivery.queued_at.is_(None))
                .order_by(Email.started_at, Email.id, Delivery.id)
                .limit(allowance)
                .with_for_update(of=Delivery, skip_locked=True)
            )
        ).all()
    ]
    if not rows:
        return 0
    people = {
        row.id: row
        for row in await db.scalars(
            select(Subscriber).where(
                Subscriber.id.in_(
                    [delivery.subscriber_id for delivery, _ in rows if delivery.subscriber_id]
                )
            )
        )
    }
    aside = set(
        await db.scalars(
            select(SetAside.email_normal).where(
                SetAside.email_normal.in_([delivery.email_normal for delivery, _ in rows])
            )
        )
    )
    footer = await service.footer(db)
    site_url = email.site_url()
    made: dict[uuid.UUID, render.Parts] = {}
    skipped: list[uuid.UUID] = []
    queued = 0
    for delivery, row in rows:
        person = people.get(delivery.subscriber_id) if delivery.subscriber_id else None
        if (
            person is None
            or person.status != "subscribed"
            or person.email_normal != delivery.email_normal
            or delivery.email_normal in aside
        ):
            skipped.append(delivery.id)
            continue
        if row.id not in made:
            made[row.id] = render.parts(row.subject, row.preview, row.body, footer, site_url)
        parts = made[row.id]
        token = crypto.open(person.token_sealed)
        link = render.unsubscribe_page(site_url, token)
        await email.queue_message(
            db,
            person.email,
            parts.subject,
            render.text(parts, link),
            render.html(parts, link),
            render.headers(site_url, token),
        )
        delivery.queued_at = now
        row.sent_to += 1
        queued += 1
    if skipped:
        await db.execute(delete(Delivery).where(Delivery.id.in_(skipped)))
    return queued


async def _finish(db: AsyncSession, now: datetime) -> None:
    waiting = (
        select(Delivery.id)
        .where(Delivery.email_id == Email.id, Delivery.queued_at.is_(None))
        .exists()
    )
    for row in await db.scalars(
        select(Email).where(Email.status == "sending", ~waiting).with_for_update(skip_locked=True)
    ):
        row.status = "sent"
        row.sent_at = now
