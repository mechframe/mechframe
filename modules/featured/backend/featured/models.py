"""featured's tables (`dev plans/contracts/featured.md` §3).

`featured_slot` is one of the site's players, such as the homepage's
Spotlight: the key its code reads, its tab's label, what it takes (types
another module gives through `kernel.refs`, or `"youtube"` for links), a
video's kinds, and whether the Dashboard shows it. `featured_placement` is one
thing in a slot's list, in order: another module's item, `{ref_type, ref_id}`,
or a YouTube link with its title and kind, each with optional dates.

No foreign key reaches another module (SPEC 10): an item that's gone shows as
removed on Players, and a save leaves it out.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base

#: A slot's key: lowercase letters and digits, single hyphens between them.
KEY_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_KEY = 40
MAX_LABEL = 60
#: A type as `kernel.refs` names it (its MAX_TYPE).
MAX_TYPE = 80
MAX_URL = 500
MAX_TITLE = 200
MAX_KIND = 40
#: A slot's kinds, and the placements one list holds.
MAX_KINDS = 12
MAX_PLACEMENTS = 100
#: What a slot takes for YouTube's links, beside the types of `kernel.refs`.
YOUTUBE = "youtube"


class Slot(Base):
    __tablename__ = "featured_slot"
    __table_args__ = (
        CheckConstraint(f"key ~ '{KEY_PATTERN}'", name="key_is_a_slug"),
        CheckConstraint(f"char_length(label) BETWEEN 1 AND {MAX_LABEL}", name="label_length"),
        CheckConstraint(
            "jsonb_typeof(accepts) = 'array' AND jsonb_array_length(accepts) >= 1",
            name="accepts_a_list",
        ),
        CheckConstraint(
            f"jsonb_typeof(kinds) = 'array' AND jsonb_array_length(kinds) <= {MAX_KINDS}",
            name="kinds_a_list",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    key: Mapped[str] = mapped_column(String(MAX_KEY), primary_key=True)
    label: Mapped[str] = mapped_column(String(MAX_LABEL))
    #: Each a type of `kernel.refs`, or `"youtube"`.
    accepts: Mapped[list[str]] = mapped_column(JSONB)
    #: `[{key, label}]`: a link's kinds, such as Music video.
    kinds: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    on_dashboard: Mapped[bool] = mapped_column(Boolean)
    #: Its tab's place: slots are listed in the order they were made.
    position: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Placement(Base):
    __tablename__ = "featured_placement"
    __table_args__ = (
        # Checked at the commit, so one save may move rows past each other.
        UniqueConstraint("slot_key", "position", deferrable=True, initially="DEFERRED"),
        CheckConstraint(
            "(ref_type IS NOT NULL AND ref_id IS NOT NULL AND url IS NULL AND video_id IS NULL "
            "AND title IS NULL AND kind IS NULL) OR (ref_type IS NULL AND ref_id IS NULL "
            "AND url IS NOT NULL AND video_id IS NOT NULL AND title IS NOT NULL)",
            name="an_item_or_a_link",
        ),
        CheckConstraint(
            f"title IS NULL OR char_length(title) BETWEEN 1 AND {MAX_TITLE}", name="title_length"
        ),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at", name="ends_after_start"
        ),
        CheckConstraint("position >= 0", name="position_not_negative"),
        Index("ix_featured_placement_ref", "ref_type", "ref_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_key: Mapped[str] = mapped_column(
        String(MAX_KEY), ForeignKey("featured_slot.key", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    ref_type: Mapped[str | None] = mapped_column(String(MAX_TYPE), default=None)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)
    #: A link: the video's watch address, its id, its title and its kind's key.
    url: Mapped[str | None] = mapped_column(String(MAX_URL), default=None)
    video_id: Mapped[str | None] = mapped_column(CHAR(11), default=None)
    title: Mapped[str | None] = mapped_column(String(MAX_TITLE), default=None)
    kind: Mapped[str | None] = mapped_column(String(MAX_KIND), default=None)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
