"""The newsletter's tables (`dev plans/contracts/campaigns.md` §3).

- `campaigns_subscriber`: one address that asked for the site's news, `pending`
  until it confirms, then `subscribed`, or `unsubscribed`. Its token names the
  subscription in the confirm and unsubscribe links: kept as its sha256 to look
  it up by, and sealed (`crypto.seal`) so each newsletter can carry it.
- `campaigns_set_aside`: an address that bounced, complained or unsubscribed.
  It's never deleted, so the address is never emailed again, even once its
  subscriber row is erased.
- `campaigns_email`: one email, a draft until it's scheduled or sent.
- `campaigns_delivery`: one row per recipient of a send, fixed when it starts,
  unique per email and address, so a job that runs twice sends nobody twice.
- `campaigns_webhook_seen`: Resend's delivery ids, kept 7 days, against replays.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base

#: One address, as sign-up takes it (kernel.email.MAX_ADDRESS).
MAX_EMAIL = 254
MAX_NAME = 200
MAX_SOURCE = 40
MAX_DETAIL = 300
MAX_SUBJECT = 150
MAX_PREVIEW = 150
MAX_BODY = 100_000
MAX_WEBHOOK_ID = 100

SUBSCRIBER_STATUSES = ("pending", "subscribed", "unsubscribed")
REASONS = ("bounced", "complained", "unsubscribed")
KINDS = ("newsletter", "release")
EMAIL_STATUSES = ("draft", "scheduled", "sending", "sent")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Subscriber(Base):
    __tablename__ = "campaigns_subscriber"
    __table_args__ = (
        CheckConstraint(_in("status", SUBSCRIBER_STATUSES), name="status_known"),
        Index("ix_campaigns_subscriber_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The address as it was typed, trimmed: the one mail goes to.
    email: Mapped[str] = mapped_column(String(MAX_EMAIL))
    #: The same, lowercased: one row per address, whatever its case.
    email_normal: Mapped[str] = mapped_column(String(MAX_EMAIL), unique=True)
    name: Mapped[str | None] = mapped_column(String(MAX_NAME))
    #: Where they asked: `form`, `contact`, `blog` or a site's own short name.
    source: Mapped[str] = mapped_column(String(MAX_SOURCE))
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    #: The sha256 of the token, in hex: how a link finds its subscription.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    #: The token, sealed: how each newsletter carries its own unsubscribe link.
    token_sealed: Mapped[str] = mapped_column(Text)
    confirm_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    #: Their account, when they were signed in; cleared when it goes.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"), index=True
    )


class SetAside(Base):
    __tablename__ = "campaigns_set_aside"
    __table_args__ = (
        CheckConstraint(_in("why", REASONS), name="why_known"),
        Index("ix_campaigns_set_aside_why_since", "why", "since"),
    )

    email_normal: Mapped[str] = mapped_column(String(MAX_EMAIL), primary_key=True)
    why: Mapped[str] = mapped_column(String(16))
    #: A bounce's status code, or what a person wrote setting it aside by hand.
    detail: Mapped[str] = mapped_column(String(MAX_DETAIL), default="", server_default="")
    since: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Email(Base):
    __tablename__ = "campaigns_email"
    __table_args__ = (
        CheckConstraint(_in("kind", KINDS), name="kind_known"),
        CheckConstraint(_in("status", EMAIL_STATUSES), name="status_known"),
        CheckConstraint(f"char_length(body) <= {MAX_BODY}", name="body_length"),
        Index("ix_campaigns_email_status_send_at", "status", "send_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    kind: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(MAX_SUBJECT))
    #: The inbox's preheader.
    preview: Mapped[str] = mapped_column(String(MAX_PREVIEW), default="", server_default="")
    #: Markdown.
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: The rows queued: the board's "Sent to".
    sent_to: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: Blog's post, when the email was made from one: no foreign key across modules.
    post_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Delivery(Base):
    __tablename__ = "campaigns_delivery"
    __table_args__ = (
        # One row per address in a send.
        UniqueConstraint("email_id", "email_normal"),
        # The send job's next rows: those not queued yet.
        Index(
            "ix_campaigns_delivery_waiting",
            "email_id",
            postgresql_where=text("queued_at IS NULL"),
        ),
        Index("ix_campaigns_delivery_queued_at", "queued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns_email.id", ondelete="CASCADE")
    )
    subscriber_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns_subscriber.id", ondelete="SET NULL"), index=True
    )
    #: The address as it stood when the send started.
    email_normal: Mapped[str] = mapped_column(String(MAX_EMAIL))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookSeen(Base):
    __tablename__ = "campaigns_webhook_seen"

    id: Mapped[str] = mapped_column(String(MAX_WEBHOOK_ID), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
