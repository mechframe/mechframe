"""The contact form's messages (`dev plans/contracts/contact.md` §3).

`contact_message` is one message a visitor sent: who, from which address,
about what, what they wrote and whether they want the site's news. Its
`status` is where the Inbox shows it: `new` until someone replies or archives
it, or `spam`, set apart, when the bot check or the site's word and link
filters held it (`held_reason` says which) or someone put it there.
`notified_at` is when it first counted as a real message: the Inbox's
readers were told, and a newsletter sign-up went out, once and only once.
The topic's label is kept as it was sent, so a topic renamed or removed in
Settings changes no old message.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base

MAX_NAME = 200
#: One address, as sign-up takes it (kernel.email.MAX_ADDRESS).
MAX_EMAIL = 254
MAX_TOPIC = 40
MAX_TOPIC_LABEL = 80
MAX_MESSAGE = 5_000
MAX_REASON = 40
STATUSES = ("new", "replied", "archived", "spam")


class Message(Base):
    __tablename__ = "contact_message"
    __table_args__ = (
        CheckConstraint("status IN ('new', 'replied', 'archived', 'spam')", name="status_known"),
        CheckConstraint(f"char_length(message) <= {MAX_MESSAGE}", name="message_length"),
        Index("ix_contact_message_status_received_at", "status", "received_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    name: Mapped[str] = mapped_column(String(MAX_NAME))
    #: The address as the sender typed it, trimmed: the one a reply goes to.
    email: Mapped[str] = mapped_column(String(MAX_EMAIL))
    #: The same, lowercased, so export and erase find a person's messages
    #: whatever case they typed (as `auth_user.email_normal`).
    email_normal: Mapped[str] = mapped_column(String(MAX_EMAIL), index=True)
    #: The topic's key in Settings, and its label when the message was sent.
    topic: Mapped[str] = mapped_column(String(MAX_TOPIC))
    topic_label: Mapped[str] = mapped_column(String(MAX_TOPIC_LABEL))
    message: Mapped[str] = mapped_column(Text)
    wants_news: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new")
    #: Why the bot check or the filters held it, such as `too_fast` or `links`.
    held_reason: Mapped[str | None] = mapped_column(String(MAX_REASON))
    #: When its status last changed: the clock its retention runs on.
    status_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: The sender, when they were signed in; cleared when their account goes.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"), index=True
    )
