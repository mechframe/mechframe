"""The newsletter's work (`dev plans/contracts/campaigns.md` §2), shared by its
routes, its jobs, its listeners and its hooks.

**Signing up** (`request_news`): a new or unconfirmed address is `pending` and
gets the confirmation email; nothing is mailed to it until it's confirmed. A
subscribed or set-aside address gets nothing, and the answer is the same
whatever the state, so nobody learns who's subscribed. A pending address asked
again within `RESEND_AFTER` isn't sent a second confirmation, so a form can't
be used to flood someone's inbox.

**The set-aside list** (VybeSite's `suppression_service`) is the one gate every
send passes: an address is compared lowercased, a row is never deleted, and
there's no way to lift one. Setting aside twice is the outcome the caller
wanted, so it's done once and answers the same.

**A send** fixes its audience as it starts (`start`): one `campaigns_delivery`
row per address subscribed and not set aside, unique per email and address.
`sending.run` queues them at the send pace.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import sqlalchemy as sa
from fastapi import Request
from sqlalchemy import delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import bounces, render
from campaigns.models import MAX_SUBJECT, Delivery, Email, SetAside, Subscriber, WebhookSeen
from campaigns.schemas import (
    CampaignEmailChange,
    EmailTab,
    NewCampaignEmail,
    NewSubscription,
    Settings,
    SubscriberTab,
    Why,
)
from kernel import Problem, attention, audit, bot, clock, crypto, email, jobs, server_copy
from kernel import settings as module_settings

MODULE = "campaigns"
EMAIL_PERMISSION = "campaigns.email.manage"
SUBSCRIBER_PERMISSION = "campaigns.subscriber.manage"
EMAIL_TYPE = "campaigns.email"
SUBSCRIBER_TYPE = "campaigns.subscriber"
FORM = "campaigns.subscribe"
CONFIRM = "campaigns.confirm"
SEND_JOB = "campaigns.send"
PAGE = 50
#: An unconfirmed sign-up is deleted after this (the daily prune).
KEEP_PENDING = timedelta(days=30)
#: Resend's delivery ids and the events heard, kept against replays.
KEEP_SEEN = timedelta(days=7)
#: A pending address asked again within this gets no second confirmation.
RESEND_AFTER = timedelta(minutes=10)
#: The attention card counts the addresses that bounced within this.
BOUNCED_RECENTLY = timedelta(days=7)
ADMIN = "/admin/campaigns"


async def current(db: AsyncSession) -> Settings:
    return cast(Settings, await module_settings.for_module(db, MODULE))


def normal(address: str) -> str:
    """An address as the set-aside list and the subscriber rows compare it."""
    return address.strip().lower()


def _invalid(field: str, message: str) -> Problem:
    return Problem(
        "kernel.invalid_request",
        422,
        "Some of what was sent isn't valid.",
        errors={field: [message]},
    )


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def email_hint(address: str) -> str:
    """The address, partly hidden, for a page anyone holding the link can open: r…@example.com."""
    local, at, domain = address.partition("@")
    if not at:
        return "…"
    return f"{local[:1]}…@{domain}"


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _cursor_of(at: datetime, row_id: uuid.UUID | str) -> str:
    micros = (at - _EPOCH) // timedelta(microseconds=1)
    return f"{micros}.{row_id if isinstance(row_id, str) else row_id.hex}"


def _after(cursor: str, what: str) -> tuple[datetime, str]:
    micros, dot, rest = cursor.partition(".")
    try:
        if not dot or not micros.isdigit() or not rest:
            raise ValueError
        return _EPOCH + timedelta(microseconds=int(micros)), rest
    except (ValueError, OverflowError):
        raise _invalid("cursor", f"Not a page of the {what}.") from None


def _uuid_of(text: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(hex=text)
    except ValueError:
        raise _invalid("cursor", f"Not a page of the {what}.") from None


async def first_time(db: AsyncSession, key: str) -> bool:
    """True the first time `key` is seen: a webhook's delivery id or an event's
    id, kept 7 days, so a replay or a second delivery changes nothing."""
    added = await db.scalar(
        insert(WebhookSeen)
        .values(id=key[:100], seen_at=clock.now())
        .on_conflict_do_nothing(index_elements=[WebhookSeen.id])
        .returning(WebhookSeen.id)
    )
    return added is not None


# --- the set-aside list ---------------------------------------------------------------------


async def is_set_aside(db: AsyncSession, address: str) -> bool:
    found = await db.scalar(
        select(SetAside.email_normal).where(SetAside.email_normal == normal(address))
    )
    return found is not None


async def set_aside(db: AsyncSession, address: str, why: Why, detail: str = "") -> bool:
    """Sets the address aside for good; True when it wasn't already."""
    added = await db.scalar(
        insert(SetAside)
        .values(email_normal=normal(address), why=why, detail=detail[:300], since=clock.now())
        .on_conflict_do_nothing(index_elements=[SetAside.email_normal])
        .returning(SetAside.email_normal)
    )
    return added is not None


async def set_aside_if_known(db: AsyncSession, address: str, why: Why, detail: str) -> bool:
    """A bounce or a complaint about one of the newsletter's addresses sets it
    aside. One about other mail the site sent (a sign-in link, a notice) is
    left alone: it isn't the newsletter's."""
    known = await db.scalar(select(Subscriber.id).where(Subscriber.email_normal == normal(address)))
    if known is None:
        return False
    return await set_aside(db, address, why, detail)


async def apply(db: AsyncSession, verdicts: list[tuple[str, bounces.Verdict]]) -> int:
    """A report's or a webhook's verdicts applied: answers how many were set aside."""
    count = 0
    for address, verdict in verdicts:
        if verdict.set_aside is not None and await set_aside_if_known(
            db, address, verdict.set_aside, verdict.why
        ):
            count += 1
    return count


# --- signing up -----------------------------------------------------------------------------


def _token() -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    return token, _hash(token), crypto.seal(token)


async def subscribe(
    db: AsyncSession, request: Request, body: NewSubscription, *, user_id: uuid.UUID | None
) -> None:
    """The public form's sign-up. One the bot check holds is kept as pending
    and sent nothing: it's never confirmed, and the prune takes it."""
    cfg = await current(db)
    if not cfg.signups_open:
        raise Problem("campaigns.closed", 409, "The newsletter isn't taking sign-ups just now.")
    found = await bot.verify(request, body.bot, form=FORM, db=db)
    await request_news(
        db,
        address=body.email,
        name=body.name,
        source=body.source,
        user_id=user_id,
        confirm=not isinstance(found, bot.Held),
    )


async def request_news(
    db: AsyncSession,
    *,
    address: str,
    name: str | None,
    source: str,
    user_id: uuid.UUID | None = None,
    confirm: bool = True,
) -> None:
    """A new or pending address asks for the news: pending, with the
    confirmation email. A subscribed, unsubscribed or set-aside one gets nothing."""
    key = normal(address)
    if await is_set_aside(db, key):
        return
    now = clock.now()
    _, hashed, sealed = _token()
    await db.execute(
        insert(Subscriber)
        .values(
            id=uuid.uuid4(),
            email=address.strip(),
            email_normal=key,
            name=name,
            source=source,
            status="pending",
            token_hash=hashed,
            token_sealed=sealed,
            created_at=now,
            user_id=user_id,
        )
        .on_conflict_do_nothing(index_elements=[Subscriber.email_normal])
    )
    row = await db.scalar(
        select(Subscriber).where(Subscriber.email_normal == key).with_for_update()
    )
    if row is None or row.status != "pending":
        return
    if name and not row.name:
        row.name = name
    if user_id is not None and row.user_id is None:
        row.user_id = user_id
    if not confirm:
        return
    if row.confirm_sent_at is not None and now - row.confirm_sent_at < RESEND_AFTER:
        return
    row.confirm_sent_at = now
    link = render.confirm_page(email.site_url(), crypto.open(row.token_sealed))
    await email.queue(db, CONFIRM, row.email, {"link": link})


async def by_token(db: AsyncSession, token: str, *, lock: bool = False) -> Subscriber:
    query = select(Subscriber).where(Subscriber.token_hash == _hash(token))
    if lock:
        query = query.with_for_update()
    found = await db.scalar(query)
    if found is None:
        raise Problem("campaigns.unknown_link", 404, "This link isn't one the site knows.")
    return found


async def _link(db: AsyncSession, row: Subscriber) -> dict[str, Any]:
    subscribed = row.status == "subscribed" and not await is_set_aside(db, row.email_normal)
    return {"email_hint": email_hint(row.email), "subscribed": subscribed}


async def confirm(db: AsyncSession, token: str) -> dict[str, Any]:
    """A pending subscription confirmed. A set-aside or unsubscribed one stays as it is."""
    row = await by_token(db, token, lock=True)
    if row.status == "pending" and not await is_set_aside(db, row.email_normal):
        row.status = "subscribed"
        row.confirmed_at = clock.now()
    return await _link(db, row)


async def looked_up(db: AsyncSession, token: str) -> dict[str, Any]:
    """What an unsubscribe link names, changing nothing: link scanners open links."""
    return await _link(db, await by_token(db, token))


async def unsubscribe(db: AsyncSession, token: str) -> dict[str, Any]:
    """Unsubscribed and set aside, once; a second time answers the same."""
    row = await by_token(db, token, lock=True)
    if row.status != "unsubscribed":
        row.status = "unsubscribed"
        row.unsubscribed_at = clock.now()
    await set_aside(db, row.email_normal, "unsubscribed", "The unsubscribe link")
    return {"email_hint": email_hint(row.email), "subscribed": False}


# --- the audience ---------------------------------------------------------------------------


def _not_set_aside() -> sa.ColumnElement[bool]:
    return ~sa.exists().where(SetAside.email_normal == Subscriber.email_normal)


def _audience() -> sa.ColumnElement[bool]:
    return sa.and_(Subscriber.status == "subscribed", _not_set_aside())


async def audience(db: AsyncSession) -> int:
    """The people a send now reaches: subscribed and not set aside."""
    return int(
        await db.scalar(select(func.count()).select_from(Subscriber).where(_audience())) or 0
    )


async def counts(db: AsyncSession) -> dict[str, int]:
    statuses = dict(
        (
            await db.execute(
                select(Subscriber.status, func.count())
                .where(_not_set_aside())
                .group_by(Subscriber.status)
            )
        ).all()
    )
    scheduled = await db.scalar(
        select(func.count()).select_from(Email).where(Email.status == "scheduled")
    )
    emails = await db.scalar(select(func.count()).select_from(Email))
    aside = await db.scalar(select(func.count()).select_from(SetAside))
    return {
        "subscribed": int(statuses.get("subscribed", 0)),
        "pending": int(statuses.get("pending", 0)),
        "unsubscribed": int(statuses.get("unsubscribed", 0)),
        "scheduled": int(scheduled or 0),
        "set_aside": int(aside or 0),
        "emails": int(emails or 0),
    }


# --- emails ---------------------------------------------------------------------------------


async def get(db: AsyncSession, email_id: uuid.UUID, *, lock: bool = False) -> Email:
    query = select(Email).where(Email.id == email_id)
    if lock:
        query = query.with_for_update()
    found = await db.scalar(query)
    if found is None:
        raise Problem("campaigns.email_not_found", 404, "There's no such email.")
    return found


def _iso(at: datetime | None) -> str | None:
    return None if at is None else at.isoformat()


async def full(db: AsyncSession, row: Email) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "version": row.version,
        "kind": row.kind,
        "subject": row.subject,
        "preview": row.preview,
        "body": row.body,
        "status": row.status,
        "send_at": _iso(row.send_at),
        "started_at": _iso(row.started_at),
        "sent_at": _iso(row.sent_at),
        "sent_to": row.sent_to,
        "audience": await audience(db),
        "from_post": row.post_id is not None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _when(row: Email) -> datetime | None:
    if row.status == "sent":
        return row.sent_at
    if row.status == "sending":
        return row.started_at
    if row.status == "scheduled":
        return row.send_at
    return None


def _in_tab(tab: EmailTab) -> sa.ColumnElement[bool]:
    if tab == "all":
        return sa.true()
    if tab == "sent":
        return Email.status.in_(("sending", "sent"))
    return Email.status == tab


async def emails_page(
    db: AsyncSession, tab: EmailTab, cursor: str | None, limit: int = PAGE
) -> dict[str, Any]:
    """A page of emails, newest first, with the cards, the attention card and what the page warns of."""
    query = select(Email).where(_in_tab(tab))
    if cursor is not None:
        at, rest = _after(cursor, "emails")
        after_id = _uuid_of(rest, "emails")
        query = query.where(
            sa.or_(Email.created_at < at, sa.and_(Email.created_at == at, Email.id < after_id))
        )
    rows = list(
        await db.scalars(query.order_by(Email.created_at.desc(), Email.id.desc()).limit(limit + 1))
    )
    page = rows[:limit]
    reach = await audience(db)
    items = []
    for row in page:
        when = _when(row)
        items.append(
            {
                "id": str(row.id),
                "subject": row.subject,
                "kind": row.kind,
                "status": row.status,
                "sent_to": reach if row.status == "scheduled" else row.sent_to,
                "when": _iso(when),
            }
        )
    upcoming = await db.scalar(
        select(Email).where(Email.status == "scheduled").order_by(Email.send_at, Email.id).limit(1)
    )
    cfg = await current(db)
    item = await bounced_item(db)
    return {
        "items": items,
        "next_cursor": (
            _cursor_of(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        ),
        "counts": await counts(db),
        "scheduled": (
            None
            if upcoming is None or upcoming.send_at is None
            else {
                "id": str(upcoming.id),
                "subject": upcoming.subject,
                "when": upcoming.send_at.isoformat(),
            }
        ),
        "waiting": None if item is None else shown(item),
        "setup": {
            "signups_open": cfg.signups_open,
            "has_address": bool(cfg.postal_address.strip()),
            "reads_bounces": bounces.login_from() is not None,
        },
    }


async def create(
    db: AsyncSession,
    body: NewCampaignEmail,
    *,
    by: uuid.UUID | None,
    post_id: uuid.UUID | None = None,
) -> Email:
    now = clock.now()
    row = Email(
        id=uuid.uuid4(),
        version=1,
        kind=body.kind,
        subject=body.subject,
        preview=body.preview,
        body=body.body,
        status="draft",
        sent_to=0,
        post_id=post_id,
        created_by=by,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    audit.record(db, "campaigns.email.created", actor=by, target=(EMAIL_TYPE, row.id))
    return row


EDITABLE = ("kind", "subject", "preview", "body")


async def change(
    db: AsyncSession, email_id: uuid.UUID, body: CampaignEmailChange, *, by: uuid.UUID
) -> Email:
    """Saves the fields sent; 409 `campaigns.changed` on a stale `version`, with the email now."""
    row = await get(db, email_id, lock=True)
    if row.status in ("sending", "sent"):
        raise Problem("campaigns.sent", 409, "This email is sent: it can't change.")
    if body.version != row.version:
        raise Problem(
            "campaigns.changed",
            409,
            "Someone saved this email since you opened it. Here is how it reads now.",
            extra={"email": await full(db, row)},
        )
    fields = [name for name in EDITABLE if getattr(body, name) is not None]
    for name in fields:
        setattr(row, name, getattr(body, name))
    if fields:
        row.version += 1
        row.updated_at = clock.now()
        audit.record(
            db,
            "campaigns.email.changed",
            actor=by,
            target=(EMAIL_TYPE, row.id),
            details={"fields": fields},
        )
    return row


async def remove(db: AsyncSession, email_id: uuid.UUID, *, by: uuid.UUID) -> None:
    row = await get(db, email_id, lock=True)
    if row.status != "draft":
        raise Problem(
            "campaigns.not_draft", 409, "Only a draft can be deleted: cancel a scheduled one first."
        )
    await db.delete(row)
    audit.record(db, "campaigns.email.deleted", actor=by, target=(EMAIL_TYPE, email_id))


async def footer(db: AsyncSession, cfg: Settings | None = None) -> render.Footer:
    cfg = cfg or await current(db)
    name = (await server_copy.identity(db)).name
    return render.Footer(render.footer_note(cfg.footer_note, name), name, cfg.postal_address)


async def preview(db: AsyncSession, body: str, subject: str = "", preheader: str = "") -> str:
    made = render.parts(subject, preheader, body, await footer(db), email.site_url())
    return render.preview_html(made)


async def send_test(db: AsyncSession, email_id: uuid.UUID, *, to: str) -> None:
    """The email to the person asking, marked [Test], counted nowhere and set
    aside by nothing: its unsubscribe link is the page with no token."""
    row = await get(db, email_id)
    made = render.parts(
        render.TEST_MARK + row.subject,
        row.preview,
        row.body,
        await footer(db),
        email.site_url(),
    )
    link = render.unsubscribe_page(made.site_url, None)
    await email.queue_message(
        db, to, made.subject, render.text(made, link), render.html(made, link)
    )


def _at(text: str) -> datetime:
    try:
        at = datetime.fromisoformat(text)
    except ValueError:
        at = None
    if at is None or at.utcoffset() is None:
        raise _invalid("at", "A time with its zone, such as 2026-12-01T09:00:00+00:00.")
    return at


async def start(db: AsyncSession, row: Email, now: datetime) -> int:
    """Fixes the audience: one delivery per address subscribed and not set
    aside, made once. The email is `sending` from now. Answers the rows made."""
    made = cast(
        CursorResult[Any],
        await db.execute(
            insert(Delivery)
            .from_select(
                ["id", "email_id", "subscriber_id", "email_normal"],
                select(
                    func.gen_random_uuid(),
                    literal(row.id, type_=Delivery.email_id.type),
                    Subscriber.id,
                    Subscriber.email_normal,
                ).where(_audience()),
            )
            .on_conflict_do_nothing(index_elements=[Delivery.email_id, Delivery.email_normal])
        ),
    )
    row.status = "sending"
    row.started_at = now
    if row.send_at is None:
        row.send_at = now
    return int(made.rowcount or 0)


async def send(
    db: AsyncSession, email_id: uuid.UUID, at: str | None, *, by: uuid.UUID | None
) -> Email:
    """Now, or scheduled for `at`. 409 without the postal address or with nobody subscribed."""
    row = await get(db, email_id, lock=True)
    if row.status != "draft":
        raise Problem("campaigns.not_draft", 409, "This email is already scheduled or sent.")
    when = None if at is None else _at(at)
    cfg = await current(db)
    if not cfg.postal_address.strip():
        raise Problem(
            "campaigns.no_address",
            409,
            "Add the newsletter's postal address in Settings first: every newsletter carries one.",
        )
    reach = await audience(db)
    if reach == 0:
        raise Problem("campaigns.nobody", 409, "Nobody is subscribed yet.")
    now = clock.now()
    if when is None or when <= now:
        count = await start(db, row, now)
        await jobs.enqueue(db, SEND_JOB, {}, key="now")
        audit.record(
            db,
            "campaigns.email.sent",
            actor=by,
            target=(EMAIL_TYPE, row.id),
            details={"count": count},
        )
    else:
        row.status = "scheduled"
        row.send_at = when
        await jobs.enqueue(db, SEND_JOB, {}, run_at=when)
        audit.record(
            db,
            "campaigns.email.scheduled",
            actor=by,
            target=(EMAIL_TYPE, row.id),
            details={"count": reach},
        )
    row.version += 1
    row.updated_at = now
    return row


async def cancel(db: AsyncSession, email_id: uuid.UUID, *, by: uuid.UUID) -> Email:
    """A scheduled email back to a draft; a sending one stops queueing the rest
    and is sent to those it reached."""
    row = await get(db, email_id, lock=True)
    now = clock.now()
    if row.status == "scheduled":
        row.status = "draft"
        row.send_at = None
        details: dict[str, Any] = {"was": "scheduled"}
    elif row.status == "sending":
        await db.execute(
            delete(Delivery).where(Delivery.email_id == row.id, Delivery.queued_at.is_(None))
        )
        row.status = "sent"
        row.sent_at = now
        details = {"was": "sending", "count": row.sent_to}
    else:
        raise Problem("campaigns.not_cancellable", 409, "Only a scheduled or sending email stops.")
    row.version += 1
    row.updated_at = now
    audit.record(
        db, "campaigns.email.cancelled", actor=by, target=(EMAIL_TYPE, row.id), details=details
    )
    return row


async def from_post(
    db: AsyncSession, *, post_id: uuid.UUID, title: str, summary: str, path: str
) -> Email | None:
    """Blog's "Email it to subscribers": the post's email, sent at once. It
    stays a draft while the postal address is missing or nobody is subscribed,
    for someone to send later. Once per post."""
    if await db.scalar(select(Email.id).where(Email.post_id == post_id)) is not None:
        return None
    words = [f"## {render.escaped(title)}"]
    if summary.strip():
        words.append(render.escaped(summary))
    words.append(f"[Read the post]({path})")
    row = await create(
        db,
        NewCampaignEmail(
            kind="newsletter",
            subject=" ".join(title.split())[:MAX_SUBJECT] or "A new post",
            preview=" ".join(summary.split())[:150],
            body="\n\n".join(words),
        ),
        by=None,
        post_id=post_id,
    )
    cfg = await current(db)
    if cfg.postal_address.strip() and await audience(db):
        count = await start(db, row, clock.now())
        await jobs.enqueue(db, SEND_JOB, {}, key="now")
        audit.record(
            db,
            "campaigns.email.sent",
            actor=None,
            target=(EMAIL_TYPE, row.id),
            details={"count": count, "from": "blog.post.published"},
        )
    return row


# --- subscribers ----------------------------------------------------------------------------


def _since(row: Subscriber) -> datetime:
    if row.status == "unsubscribed" and row.unsubscribed_at is not None:
        return row.unsubscribed_at
    if row.status == "subscribed" and row.confirmed_at is not None:
        return row.confirmed_at
    return row.created_at


async def subscribers_page(
    db: AsyncSession, tab: SubscriberTab, cursor: str | None, limit: int = PAGE
) -> dict[str, Any]:
    query = select(Subscriber).where(_not_set_aside())
    if tab != "all":
        query = query.where(Subscriber.status == tab)
    if cursor is not None:
        at, rest = _after(cursor, "subscribers")
        after_id = _uuid_of(rest, "subscribers")
        query = query.where(
            sa.or_(
                Subscriber.created_at < at,
                sa.and_(Subscriber.created_at == at, Subscriber.id < after_id),
            )
        )
    rows = list(
        await db.scalars(
            query.order_by(Subscriber.created_at.desc(), Subscriber.id.desc()).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return {
        "items": [
            {
                "id": str(row.id),
                "email": row.email,
                "name": row.name,
                "source": row.source,
                "status": row.status,
                "since": _since(row).isoformat(),
            }
            for row in page
        ],
        "next_cursor": (
            _cursor_of(page[-1].created_at, page[-1].id) if len(rows) > limit else None
        ),
        "counts": await counts(db),
    }


async def subscriber(db: AsyncSession, subscriber_id: uuid.UUID) -> Subscriber:
    found = await db.scalar(
        select(Subscriber).where(Subscriber.id == subscriber_id).with_for_update()
    )
    if found is None:
        raise Problem("campaigns.subscriber_not_found", 404, "There's no such subscriber.")
    return found


async def set_aside_by_hand(
    db: AsyncSession, subscriber_id: uuid.UUID, why: Why, detail: str | None, *, by: uuid.UUID
) -> None:
    row = await subscriber(db, subscriber_id)
    if why == "unsubscribed" and row.status != "unsubscribed":
        row.status = "unsubscribed"
        row.unsubscribed_at = clock.now()
    await set_aside(db, row.email_normal, why, detail or "Set aside by hand")
    audit.record(
        db,
        "campaigns.subscriber.set_aside",
        actor=by,
        target=(SUBSCRIBER_TYPE, row.id),
        details={"why": why},
    )


async def forget(db: AsyncSession, row: Subscriber, detail: str) -> None:
    """The subscriber gone, with a set-aside row kept so they're never emailed again."""
    await set_aside(db, row.email_normal, "unsubscribed", detail)
    await db.delete(row)


async def remove_subscriber(db: AsyncSession, subscriber_id: uuid.UUID, *, by: uuid.UUID) -> None:
    row = await subscriber(db, subscriber_id)
    await forget(db, row, "Removed at their request")
    audit.record(
        db, "campaigns.subscriber.deleted", actor=by, target=(SUBSCRIBER_TYPE, subscriber_id)
    )


async def set_aside_page(db: AsyncSession, cursor: str | None, limit: int = PAGE) -> dict[str, Any]:
    query = select(SetAside)
    if cursor is not None:
        at, after = _after(cursor, "addresses set aside")
        query = query.where(
            sa.or_(
                SetAside.since < at, sa.and_(SetAside.since == at, SetAside.email_normal < after)
            )
        )
    rows = list(
        await db.scalars(
            query.order_by(SetAside.since.desc(), SetAside.email_normal.desc()).limit(limit + 1)
        )
    )
    page = rows[:limit]
    return {
        "items": [
            {
                "email": row.email_normal,
                "why": row.why,
                "detail": row.detail,
                "since": row.since.isoformat(),
            }
            for row in page
        ],
        "next_cursor": (
            _cursor_of(page[-1].since, page[-1].email_normal) if len(rows) > limit else None
        ),
        "reads_bounces": bounces.login_from() is not None,
    }


# --- what's waiting, and what goes ----------------------------------------------------------


def shown(item: attention.Item) -> dict[str, str]:
    return {
        "tone": item.tone,
        "what": item.what,
        "why": item.why,
        "label": item.label,
        "to": item.to,
    }


def bounced_words(count: int) -> attention.Item:
    one = count == 1
    return attention.Item(
        key="campaigns.set_aside",
        tone="warning",
        what=(
            "1 address bounced and was set aside"
            if one
            else f"{count} addresses bounced and were set aside"
        ),
        why=(
            f"{'It' if one else 'They'} won't be emailed again. Sending to dead addresses "
            "gets a site's mail marked as spam."
        ),
        label="See them",
        to=f"{ADMIN}?tab=set-aside",
        permission=SUBSCRIBER_PERMISSION,
    )


async def bounced_item(db: AsyncSession) -> attention.Item | None:
    """While an address bounced in the last 7 days."""
    count = await db.scalar(
        select(func.count())
        .select_from(SetAside)
        .where(SetAside.why == "bounced", SetAside.since > clock.now() - BOUNCED_RECENTLY)
    )
    return bounced_words(int(count)) if count else None


async def no_address_item(db: AsyncSession) -> attention.Item | None:
    """While the postal address is missing and someone is subscribed."""
    cfg = await current(db)
    if cfg.postal_address.strip() or not await audience(db):
        return None
    return attention.Item(
        key="campaigns.no_address",
        tone="warning",
        what="The newsletter has no postal address",
        why="US law puts a postal address in every newsletter, so nothing sends until it's set. A P.O. box will do.",
        label="Add it",
        to="/admin/settings",
        permission=EMAIL_PERMISSION,
    )


async def prune(db: AsyncSession) -> int:
    """Deletes sign-ups not confirmed within 30 days, and replay ids past 7.
    Answers how many sign-ups went."""
    now = clock.now()
    gone = cast(
        CursorResult[Any],
        await db.execute(
            delete(Subscriber).where(
                Subscriber.status == "pending", Subscriber.created_at < now - KEEP_PENDING
            )
        ),
    )
    await db.execute(delete(WebhookSeen).where(WebhookSeen.seen_at < now - KEEP_SEEN))
    return int(gone.rowcount or 0)
