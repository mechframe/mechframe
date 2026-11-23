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

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import render, service
from campaigns.models import Delivery, Email, SetAside, Subscriber
from kernel import clock, crypto, email

log = logging.getLogger(__name__)

#: The windows the pace is counted over: a sixtieth a minute, and the hour's whole.
MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)
#: The advisory lock a run holds for its transaction: Send now's run and the
#: minute's can overlap in the worker, and each would spend the same allowance
#: (Codex on #134). A run that finds it held leaves the work to the one holding it.
LOCK = 6_377_016_421_517_436_516


def per_minute(send_per_hour: int) -> int:
    """A sixtieth of the hourly pace, at least one."""
    return max(1, send_per_hour // 60)


async def run(db: AsyncSession) -> list[uuid.UUID]:
    """One run of the send job, in the caller's transaction. Answers the rows it
    queued; `run_and_commit` is how the job runs it."""
    if not await db.scalar(select(func.pg_try_advisory_xact_lock(LOCK))):
        return []
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
    sent = await _queue(db, cfg.send_per_hour, now) if ready else []
    await _finish(db, now)
    # Stamped last, just before the job commits: a run slow at any step still counts
    # its copies in the minute they leave in (CodeRabbit on #134).
    finished = clock.now()
    for delivery in sent:
        delivery.queued_at = finished
    return [delivery.id for delivery in sent]


async def run_and_commit(db: AsyncSession) -> int:
    """A run, committed, then its copies stamped again as of the commit, in a
    transaction of its own: one whose commit outlasted a minute still counts them
    in the minute they became mail (CodeRabbit on #134). Answers how many it queued."""
    sent = await run(db)
    await db.commit()
    if sent:
        await db.execute(
            update(Delivery).where(Delivery.id.in_(sent)).values(queued_at=clock.now())
        )
        await db.commit()
    return len(sent)


async def _queue(db: AsyncSession, send_per_hour: int, now: datetime) -> list[Delivery]:
    """Queues the next copies at the pace: answers their rows, which `run` stamps last."""
    minute, hour = (
        await db.execute(
            select(
                func.count().filter(Delivery.queued_at > now - MINUTE),
                func.count().filter(Delivery.queued_at > now - HOUR),
            ).select_from(Delivery)
            # The hour's rows only: the queued_at index narrows the scan (CodeRabbit on #134).
            .where(Delivery.queued_at > now - HOUR)
        )
    ).one()
    # "At least one a minute" never takes an hour past `send_per_hour`: a setting
    # under 60 is held to its hour too (CodeRabbit on #134).
    allowance = min(per_minute(send_per_hour) - int(minute), send_per_hour - int(hour))
    if allowance <= 0:
        return []
    # The emails first, then their rows, the order Cancel takes them in: an email that
    # a cancel holds is left to it, so neither waits on the other (CodeRabbit on #134).
    held = list(
        await db.scalars(
            select(Email.id)
            .where(Email.status == "sending")
            .order_by(Email.started_at, Email.id)
            .with_for_update(skip_locked=True)
        )
    )
    if not held:
        return []
    rows: list[tuple[Delivery, Email]] = [
        (delivery, row)
        for delivery, row in (
            await db.execute(
                select(Delivery, Email)
                .join(Email, Delivery.email_id == Email.id)
                .where(Email.id.in_(held), Delivery.queued_at.is_(None))
                .order_by(Email.started_at, Email.id, Delivery.id)
                .limit(allowance)
                .with_for_update(of=Delivery, skip_locked=True)
            )
        ).all()
    ]
    if not rows:
        return []
    wanted = {delivery.subscriber_id for delivery, _ in rows if delivery.subscriber_id}
    # Each recipient held while their copy is decided: an unsubscribe under way waits
    # for this run, or this run leaves that copy for the next (CodeRabbit on #134).
    people = {
        row.id: row
        for row in await db.scalars(
            select(Subscriber).where(Subscriber.id.in_(wanted)).with_for_update(skip_locked=True)
        )
    }
    busy = set(
        await db.scalars(select(Subscriber.id).where(Subscriber.id.in_(wanted - set(people))))
    )
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
    stopped: set[uuid.UUID] = set()
    sent: list[Delivery] = []
    queued = 0
    for delivery, row in rows:
        if row.id in stopped:
            continue
        if row.id not in made:
            made[row.id] = render.parts(row.subject, row.preview, row.body, footer, site_url)
            if render.too_long(made[row.id]):
                # Past the mailer's limit (send and a scheduled save refuse it, so only a
                # change since, such as the footer's): it stops here rather than holding
                # every send behind it (Codex on #134).
                await _stop(db, row, now)
                stopped.add(row.id)
                continue
        if delivery.subscriber_id in busy:
            continue  # held by another change right now: this copy waits for the next run
        person = people.get(delivery.subscriber_id) if delivery.subscriber_id else None
        if (
            person is None
            or person.status != "subscribed"
            or person.email_normal != delivery.email_normal
            or delivery.email_normal in aside
        ):
            skipped.append(delivery.id)
            continue
        parts = made[row.id]
        try:
            token = crypto.open(person.token_sealed)
        except crypto.SealError:
            # Sealed with a key since removed: this person's copy can't carry their
            # link, so it goes unsent, and nobody else waits on it (CodeRabbit on #134).
            log.error("A subscriber's link couldn't be opened; their copy is skipped.")
            skipped.append(delivery.id)
            continue
        link = render.unsubscribe_page(site_url, token)
        try:
            await email.queue_message(
                db,
                person.email,
                parts.subject,
                render.text(parts, link),
                render.html(parts, link),
                render.headers(site_url, token),
            )
        except ValueError:
            # The kernel's checks refused this email's copy (its subject, say): every
            # copy would be refused alike, so it stops here, and the sends behind it
            # go on (CodeRabbit on #134). Nothing of the copy is logged.
            await _stop(db, row, now)
            stopped.add(row.id)
            continue
        delivery.queued_at = now
        sent.append(delivery)
        row.sent_to += 1
        queued += 1
    if skipped:
        await db.execute(delete(Delivery).where(Delivery.id.in_(skipped)))
    return sent


async def _stop(db: AsyncSession, row: Email, now: datetime) -> None:
    await db.execute(
        delete(Delivery).where(Delivery.email_id == row.id, Delivery.queued_at.is_(None))
    )
    row.status = "sent"
    row.sent_at = now
    log.error(
        "A newsletter was too long to send once rendered; it stopped.",
        extra={"email_id": str(row.id), "count": row.sent_to},
    )


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
