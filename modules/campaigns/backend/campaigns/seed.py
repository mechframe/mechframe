"""campaigns: its seed data (kernel.seed, hook 4, decision 0052): subscribers
in each state, two addresses set aside, and a draft, a scheduled and a sent
email, every address `@example.com`. Each row has a fixed id or key, so a
second run finds them and changes nothing. Seeding mails nobody: the sent
email's count is set, and no copy is queued."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns.models import Email, SetAside, Subscriber
from kernel import crypto
from kernel import seed as seeding

_NAMESPACE = uuid.UUID("5f0b9c2e-7d41-4a8e-9c36-1e2a7b4d8f90")
#: Address, name, source, status, days ago.
SUBSCRIBERS: tuple[tuple[str, str | None, str, str, int], ...] = (
    ("rae@example.com", "Rae Okafor", "form", "subscribed", 40),
    ("sam@example.com", "Sam Ito", "contact", "subscribed", 21),
    ("lee@example.com", None, "form", "subscribed", 9),
    ("noor@example.com", "Noor Haddad", "form", "pending", 1),
    ("ana@example.com", "Ana Duarte", "form", "unsubscribed", 60),
)
#: Address, why, detail, days ago.
SET_ASIDE: tuple[tuple[str, str, str, int], ...] = (
    ("gone@example.com", "bounced", "address: 5.1.1", 2),
    ("ana@example.com", "unsubscribed", "The unsubscribe link", 5),
    ("cross@example.com", "complained", "spam report: abuse", 12),
)
#: Key, kind, subject, preview, status, days from now (sent and scheduled), sent to.
EMAILS: tuple[tuple[str, str, str, str, str, int, int], ...] = (
    (
        "draft",
        "release",
        "The new single is out Friday",
        "Two years in the making, and it's finally here.",
        "draft",
        0,
        0,
    ),
    (
        "scheduled",
        "newsletter",
        "Winter shows, and a new video",
        "Three nights in December, and what we filmed on the road.",
        "scheduled",
        6,
        0,
    ),
    (
        "sent",
        "newsletter",
        "Back in the studio",
        "What we're working on this autumn.",
        "sent",
        -14,
        3,
    ),
)
BODY = (
    "Hello from the studio.\n\n"
    "We've spent the autumn writing, and the first of the new songs is nearly done. "
    "[Hear the demo](/music) before anyone else.\n\n"
    "- Three shows in December\n- A video from the road\n\n"
    "Thanks for listening."
)


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    for address, name, source, status, days in SUBSCRIBERS:
        row_id = uuid.uuid5(_NAMESPACE, address)
        if await db.scalar(select(Subscriber.id).where(Subscriber.id == row_id)) is not None:
            continue
        token = f"seed-{row_id.hex}-{ctx.random.getrandbits(64):016x}"
        at = ctx.now - timedelta(days=days)
        db.add(
            Subscriber(
                id=row_id,
                email=address,
                email_normal=address,
                name=name,
                source=source,
                status=status,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                token_sealed=crypto.seal(token),
                confirm_sent_at=at,
                confirmed_at=None if status == "pending" else at + timedelta(hours=1),
                unsubscribed_at=at + timedelta(days=55) if status == "unsubscribed" else None,
                created_at=at,
            )
        )
    for address, why, detail, days in SET_ASIDE:
        if await db.scalar(select(SetAside.email_normal).where(SetAside.email_normal == address)):
            continue
        db.add(
            SetAside(
                email_normal=address, why=why, detail=detail, since=ctx.now - timedelta(days=days)
            )
        )
    for key, kind, subject, preview, status, days, sent_to in EMAILS:
        row_id = uuid.uuid5(_NAMESPACE, f"email:{key}")
        if await db.scalar(select(Email.id).where(Email.id == row_id)) is not None:
            continue
        at = ctx.now + timedelta(days=days)
        made = ctx.now - timedelta(days=20)
        db.add(
            Email(
                id=row_id,
                version=1,
                kind=kind,
                subject=subject,
                preview=preview,
                body=BODY,
                status=status,
                send_at=None if status == "draft" else at,
                started_at=at if status == "sent" else None,
                sent_at=at if status == "sent" else None,
                sent_to=sent_to,
                created_at=made,
                updated_at=made,
            )
        )
