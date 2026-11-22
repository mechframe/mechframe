"""contact: its seed data (kernel.seed, hook 4, decision 0052): a message in
each tab and one the filters held, from `@example.com` senders, so the Inbox
has something in every tab. Each has a fixed id, so a second run finds them
and changes nothing. Seeding tells nobody: no notice, no newsletter sign-up."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contact import service
from contact.models import Message
from kernel import seed as seeding

_NAMESPACE = uuid.UUID("8d2b6f41-0c3e-4a7d-b5e9-2f61c0a9d374")
#: Name, address, topic key, status, held reason, days ago, wants news, the message.
MESSAGES: tuple[tuple[str, str, str, str, str | None, int, bool, str], ...] = (
    (
        "Rae Okafor",
        "rae@example.com",
        "work",
        "new",
        None,
        1,
        True,
        "We're putting on a night at the Lantern Room in March and would love you to play. "
        "Could you send your rates and what you need on stage?",
    ),
    (
        "Sam Ito",
        "sam@example.com",
        "question",
        "new",
        None,
        3,
        False,
        "Is the new record coming out on vinyl? I'd like to order one for a friend.",
    ),
    (
        "Lee Marsh",
        "lee@example.com",
        "press",
        "replied",
        None,
        6,
        True,
        "I write for a local music blog and would like a short interview before the tour.",
    ),
    (
        "Ana Duarte",
        "ana@example.com",
        "other",
        "archived",
        None,
        20,
        False,
        "Just wanted to say the last show was wonderful. Thank you.",
    ),
    (
        "Best Deals",
        "deals@example.com",
        "other",
        "spam",
        "links",
        2,
        False,
        "Cheap followers at https://spam.example/a https://spam.example/b https://spam.example/c",
    ),
)


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    topics = [(topic.key, topic.label) for topic in (await service.current(db)).topics]
    labels = dict(topics)
    for name, address, key, status, reason, days, news, text in MESSAGES:
        message_id = uuid.uuid5(_NAMESPACE, address)
        if await db.scalar(select(Message.id).where(Message.id == message_id)) is not None:
            continue
        # A site that renamed the defaults: its first topic stands in.
        topic, label = (key, labels[key]) if key in labels else topics[0]
        at = ctx.now - timedelta(days=days)
        db.add(
            Message(
                id=message_id,
                received_at=at,
                name=name,
                email=address,
                email_normal=service.normal(address),
                topic=topic,
                topic_label=label,
                message=text,
                wants_news=news,
                status=status,
                held_reason=reason,
                status_at=at,
                notified_at=None if status == "spam" else at,
            )
        )
