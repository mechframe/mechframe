"""social's tables (`dev plans/contracts/social.md` §3).

- `social_channel`: the channels the token in use reached when Buffer was last
  asked, in Buffer's order, replaced whole at each check, so opening a Share
  card costs no call to Buffer. A change to the token clears it.
- `social_share`: one post of one thing to one channel. It's stored, as
  `sending`, before its request leaves, so a send whose answer is lost still
  counts as shared, and a second post to the same channel waits until someone
  says to post it again. It names the thing by its content type and id, with no
  foreign key: the row is another module's (SPEC 10). It's the thing's history,
  not a log, and stays while social is installed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base

MAX_CHANNEL_ID = 100
MAX_NAME = 300
MAX_SERVICE = 40
MAX_ADDRESS = 600
MAX_TYPE = 64
MAX_ADMIN_PATH = 300
MAX_TEXT = 5_000

#: When a post goes out: Buffer's queue for the channel, at once, at a set
#: time, or a draft in Buffer, which waits there for a person to schedule it.
MODES = ("queue", "now", "at", "draft")

#: A share's states. `sending`: stored, its request not yet answered. `queued`,
#: `draft`, `sent` and `failed` are Buffer's own. `refused`: Buffer took
#: nothing. `unknown`: the request went out and no answer came back, so it may
#: have been made. `removed`: taken back out of Buffer, or deleted there.
STATES = ("sending", "queued", "draft", "sent", "failed", "refused", "unknown", "removed")

#: The states in which the post never reached the channel, so another share to
#: it needs no second thought.
NOT_POSTED = ("refused", "removed")

#: The states still waiting in Buffer: Refresh asks about them, and they can be taken back.
WAITING = ("queued", "draft")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Channel(Base):
    __tablename__ = "social_channel"

    #: Buffer's channel id.
    id: Mapped[str] = mapped_column(String(MAX_CHANNEL_ID), primary_key=True)
    name: Mapped[str] = mapped_column(String(MAX_NAME), default="", server_default="")
    #: Buffer's own: `linkedin`, `facebook`, `twitter`, `threads`, `bluesky`, `mastodon`, …
    service: Mapped[str] = mapped_column(String(MAX_SERVICE), default="", server_default="")
    #: Buffer's words for what the channel is: "Page", "Profile", "Business".
    descriptor: Mapped[str] = mapped_column(String(MAX_NAME), default="", server_default="")
    #: Kept, never drawn: the browser loads nothing from Buffer's hosts.
    avatar: Mapped[str] = mapped_column(String(MAX_ADDRESS), default="", server_default="")
    organization_id: Mapped[str] = mapped_column(
        String(MAX_CHANNEL_ID), default="", server_default=""
    )
    disconnected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    queue_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: Its place in Buffer's list.
    position: Mapped[int] = mapped_column(Integer)
    listed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Share(Base):
    __tablename__ = "social_share"
    __table_args__ = (
        CheckConstraint(_in("mode", MODES), name="mode_known"),
        CheckConstraint(_in("state", STATES), name="state_known"),
        CheckConstraint(f"char_length(text) <= {MAX_TEXT}", name="text_short"),
        Index("ix_social_share_content", "content_type", "content_id", "created_at"),
        Index("ix_social_share_state_created_at", "state", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The thing shared, as `<module>.<entity>` and its id: no foreign key, it's another module's row.
    content_type: Mapped[str] = mapped_column(String(MAX_TYPE))
    content_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    #: The admin page it was shared from, where the Dashboard's notice sends people.
    admin_path: Mapped[str] = mapped_column(String(MAX_ADMIN_PATH))
    #: The channel, as it was named when the post went to it.
    channel_id: Mapped[str] = mapped_column(String(MAX_CHANNEL_ID))
    channel_name: Mapped[str] = mapped_column(String(MAX_NAME), default="", server_default="")
    service: Mapped[str] = mapped_column(String(MAX_SERVICE), default="", server_default="")
    #: The text as the person wrote it; each network got it with the link added where it shows none.
    text: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(String(MAX_ADDRESS))
    mode: Mapped[str] = mapped_column(String(8))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(10))
    buffer_post_id: Mapped[str | None] = mapped_column(String(MAX_CHANNEL_ID))
    #: Why it failed, or was refused, or may not have gone, in words.
    error: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: The post's address on the network, once Buffer says it's sent.
    external_link: Mapped[str | None] = mapped_column(String(MAX_ADDRESS))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Who pressed Share, and their name as it was then. The id is cleared when
    #: their account goes, or on an erase; the share stays the site's.
    sent_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL"), index=True
    )
    sent_by_name: Mapped[str] = mapped_column(String(MAX_NAME), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
