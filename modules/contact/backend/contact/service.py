"""The contact module's work (`dev plans/contracts/contact.md` §2), shared by
its routes, its jobs and its hooks.

**A message arrives** through `receive`: the bot check first (hook 5), then
the site's word and link filters (`kernel.moderation.screen`). Either holding
it stores it as `spam`, with the reason, and tells nobody: the sender gets the
same thanks either way. One that passes is `new`, and `count_it` tells every
holder of `contact.message.manage` (decision 0059) and, when the sender asked
for news, emits `contact.news.requested` for `campaigns`. A message let out of
spam later counts then, never twice (`notified_at`).

**The Inbox** lists a tab newest first, a new message on one of Settings'
first topics before the rest, 50 at a time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from contact.events import NEWS_REQUESTED, NewsRequested
from contact.models import Message
from contact.schemas import NewContactMessage, Settings, Status, Tab
from kernel import Problem, attention, audit, bot, clock, events, moderation, notifications
from kernel import settings as module_settings

MODULE = "contact"
TYPE = "contact.message"
FORM = "contact.message"
PERMISSION = "contact.message.manage"
NOTICE = "contact.message_received"
PAGE = 50
#: Most messages an export holds: years of a busy site's form.
MAX_EXPORT = 10_000
#: How long a message is kept after its status last changed (§8, 3).
KEEP_SPAM = timedelta(days=30)
KEEP_OTHERS = timedelta(days=730)
#: The waiting item turns from info to a warning once the oldest has waited this long.
WAITING_WARNS = timedelta(days=2)
FIRST_LINE = 120


async def current(db: AsyncSession) -> Settings:
    return cast(Settings, await module_settings.for_module(db, MODULE))


def _invalid(field: str, message: str) -> Problem:
    return Problem(
        "kernel.invalid_request",
        422,
        "Some of what was sent isn't valid.",
        errors={field: [message]},
    )


def normal(address: str) -> str:
    """An address as export and erase compare it (as `auth_user.email_normal`)."""
    return address.strip().lower()


# --- a message arrives -----------------------------------------------------------------


async def receive(
    db: AsyncSession, request: Request, body: NewContactMessage, *, user_id: uuid.UUID | None
) -> Message:
    """Stores the message, held as spam or not, and counts one that passes."""
    cfg = await current(db)
    topic = next((each for each in cfg.topics if each.key == body.topic), None)
    if topic is None:
        raise _invalid("body.topic", "Choose what your message is about.")
    held: str | None = None
    found = await bot.verify(request, body.bot, form=FORM, db=db)
    if isinstance(found, bot.Held):
        held = found.reason[:40]
    else:
        screen = await moderation.screen(db, f"{body.name}\n{body.message}")
        if screen.hold:
            held = screen.reasons[0]
    now = clock.now()
    message = Message(
        id=uuid.uuid4(),
        received_at=now,
        name=body.name,
        email=body.email,
        email_normal=normal(body.email),
        topic=topic.key,
        topic_label=topic.label,
        message=body.message,
        wants_news=body.wants_news,
        status="spam" if held else "new",
        held_reason=held,
        status_at=now,
        user_id=user_id,
    )
    db.add(message)
    await db.flush()
    if held is None:
        await count_it(db, message)
    return message


async def count_it(db: AsyncSession, message: Message) -> None:
    """Tells the Inbox's readers, and passes on a sign-up for news, once."""
    if message.notified_at is not None:
        return
    message.notified_at = clock.now()
    await notifications.notify_holders(
        db,
        PERMISSION,
        NOTICE,
        {"topic": message.topic_label, "name": message.name},
        link=f"/admin/contact/{message.id}",
    )
    if message.wants_news:
        await events.emit(
            db,
            NEWS_REQUESTED,
            NewsRequested(message_id=message.id, email=message.email, name=message.name),
        )


# --- the Inbox -------------------------------------------------------------------------


def _rank(first: list[str]) -> sa.ColumnElement[int]:
    """0 for a new message on a first topic, else 1: the list's first key."""
    return sa.case((sa.and_(Message.status == "new", Message.topic.in_(first)), 0), else_=1)


def _in_tab(tab: Tab) -> sa.ColumnElement[bool]:
    if tab == "all":
        return Message.status != "spam"
    return Message.status == tab


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _cursor_of(rank: int, message: Message) -> str:
    micros = (message.received_at - _EPOCH) // timedelta(microseconds=1)
    return f"{rank}.{micros}.{message.id.hex}"


def _after(cursor: str) -> tuple[int, datetime, uuid.UUID]:
    parts = cursor.split(".")
    try:
        if len(parts) != 3 or parts[0] not in ("0", "1") or not parts[1].isdigit():
            raise ValueError
        return int(parts[0]), _EPOCH + timedelta(microseconds=int(parts[1])), uuid.UUID(parts[2])
    except ValueError:
        raise _invalid("cursor", "Not a page of the Inbox.") from None


def first_line(text: str) -> str:
    """The message's opening words, on one line, cut at a word."""
    words = " ".join(text.split())
    if len(words) <= FIRST_LINE:
        return words
    cut = words[:FIRST_LINE].rsplit(" ", 1)[0] or words[:FIRST_LINE]
    return cut + "…"


async def listed(db: AsyncSession, tab: Tab, cursor: str | None) -> dict[str, Any]:
    """One page of a tab, every tab's count and the waiting item."""
    first = [topic.key for topic in (await current(db)).topics if topic.first]
    rank = _rank(first)
    query = select(Message, rank.label("rank")).where(_in_tab(tab))
    if cursor is not None:
        at_rank, at_time, at_id = _after(cursor)
        query = query.where(
            sa.or_(
                rank > at_rank,
                sa.and_(
                    rank == at_rank,
                    sa.or_(
                        Message.received_at < at_time,
                        sa.and_(Message.received_at == at_time, Message.id < at_id),
                    ),
                ),
            )
        )
    rows = (
        await db.execute(
            query.order_by(rank, Message.received_at.desc(), Message.id.desc()).limit(PAGE + 1)
        )
    ).all()
    page = rows[:PAGE]
    items = [
        {
            "id": str(message.id),
            "name": message.name,
            "topic_label": message.topic_label,
            "first_line": first_line(message.message),
            "status": message.status,
            "first": message.topic in first,
            "received_at": message.received_at.isoformat(),
        }
        for message, _ in page
    ]
    next_cursor = _cursor_of(page[-1][1], page[-1][0]) if len(rows) > PAGE else None
    item = await waiting(db)
    return {
        "items": items,
        "next_cursor": next_cursor,
        "counts": await counts(db),
        "waiting": None if item is None else _shown(item),
    }


async def counts(db: AsyncSession) -> dict[str, int]:
    found = dict(
        (await db.execute(select(Message.status, func.count()).group_by(Message.status))).all()
    )
    return {status: int(found.get(status, 0)) for status in ("new", "replied", "archived", "spam")}


async def get(db: AsyncSession, message_id: uuid.UUID, *, lock: bool = False) -> Message:
    query = select(Message).where(Message.id == message_id)
    if lock:
        query = query.with_for_update()
    found = await db.scalar(query)
    if found is None:
        raise Problem("contact.message_not_found", 404, "There's no such message.")
    return found


def full(message: Message) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "name": message.name,
        "email": message.email,
        "topic_label": message.topic_label,
        "message": message.message,
        "wants_news": message.wants_news,
        "status": message.status,
        "held_reason": message.held_reason,
        "received_at": message.received_at.isoformat(),
        "status_at": message.status_at.isoformat(),
    }


async def change_status(
    db: AsyncSession, message_id: uuid.UUID, status: Status, *, by: uuid.UUID
) -> Message:
    """Moves it to another tab. Leaving spam for the first time counts it."""
    message = await get(db, message_id, lock=True)
    if message.status == status:
        return message
    before = message.status
    message.status = status
    message.status_at = clock.now()
    if before == "spam":
        await count_it(db, message)
    audit.record(
        db,
        "contact.message.status",
        actor=by,
        target=(TYPE, message.id),
        details={"from": before, "to": status},
    )
    return message


async def remove(db: AsyncSession, message_id: uuid.UUID, *, by: uuid.UUID) -> None:
    message = await get(db, message_id, lock=True)
    await db.delete(message)
    audit.record(db, "contact.message.deleted", actor=by, target=(TYPE, message_id))


async def exported(db: AsyncSession, tab: Tab, *, by: uuid.UUID) -> list[dict[str, Any]]:
    """Every message in a tab, newest first, for the Inbox's Export."""
    rows = await db.scalars(
        select(Message)
        .where(_in_tab(tab))
        .order_by(Message.received_at.desc(), Message.id.desc())
        .limit(MAX_EXPORT)
    )
    items = [full(message) for message in rows]
    audit.record(
        db,
        "contact.messages.exported",
        actor=by,
        details={"tab": tab, "count": len(items)},
    )
    return items


# --- what's waiting, and what goes -----------------------------------------------------


def _shown(item: attention.Item) -> dict[str, str]:
    return {
        "tone": item.tone,
        "what": item.what,
        "why": item.why,
        "label": item.label,
        "to": item.to,
    }


def _ago(days: int) -> str:
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


def waiting_item(count: int, waited: timedelta, top: uuid.UUID) -> attention.Item:
    """The words of "n new messages are waiting": how many, how long the
    oldest has waited, and the first in the Inbox's order to open."""
    days = waited.days
    one = count == 1
    reply = "hasn't had a reply" if days > 0 else "hasn't had a reply yet"
    return attention.Item(
        key="contact.waiting",
        tone="warning" if waited >= WAITING_WARNS else "info",
        what="1 new message is waiting" if one else f"{count} new messages are waiting",
        why=f"{'It' if one else 'The oldest'} came in {_ago(days)} and {reply}.",
        label="Open it" if one else "Open the first",
        to=f"/admin/contact/{top}",
        permission=PERMISSION,
    )


async def waiting(db: AsyncSession) -> attention.Item | None:
    """The waiting item while any message is new (hook 8), else None."""
    count, oldest = (
        await db.execute(
            select(func.count(), func.min(Message.received_at)).where(Message.status == "new")
        )
    ).one()
    if not count:
        return None
    first = [topic.key for topic in (await current(db)).topics if topic.first]
    top = await db.scalar(
        select(Message.id)
        .where(Message.status == "new")
        .order_by(_rank(first), Message.received_at.desc(), Message.id.desc())
        .limit(1)
    )
    if top is None:  # the last new message went between the two reads
        return None
    return waiting_item(int(count), max(clock.now() - oldest, timedelta(0)), top)


async def prune(db: AsyncSession) -> int:
    """Deletes spam 30 days after it was set apart, and every other message 2
    years after its last change (§8, 3). Answers how many went."""
    now = clock.now()
    spam = cast(
        CursorResult[Any],
        await db.execute(
            delete(Message).where(Message.status == "spam", Message.status_at < now - KEEP_SPAM)
        ),
    )
    others = cast(
        CursorResult[Any],
        await db.execute(
            delete(Message).where(Message.status != "spam", Message.status_at < now - KEEP_OTHERS)
        ),
    )
    return int(spam.rowcount or 0) + int(others.rowcount or 0)
