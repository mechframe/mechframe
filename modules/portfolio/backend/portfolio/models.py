"""portfolio's table (`dev plans/contracts/portfolio.md` §3).

`portfolio_piece` is one piece: its title, its address under /art/piece (its
slug), the account it's credited to (who may also edit it as their own), its
year, a few words about it, its picture (media's image id, no foreign key
across modules) and, for a video, its YouTube link, drafted, scheduled and
published through the kernel's lifecycle. Its discipline is the kernel's
taxonomy (`portfolio_discipline`), not a column.
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
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base, lifecycle

#: A slug: lowercase letters and digits, single hyphens between them (blog's and discography's).
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_SLUG = 120
MAX_TITLE = 200
#: The words about a piece, its line breaks kept.
MAX_ABOUT = 2000
MAX_VIDEO_URL = 500
#: The earliest year a piece can carry; the latest is next year (`service`).
MIN_YEAR = 1000
#: A YouTube video's id.
VIDEO_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"


def slug_rule(column: str) -> str:
    return f"{column} ~ '{SLUG_PATTERN}'"


class Piece(lifecycle.Publishable, Base):
    __tablename__ = "portfolio_piece"
    __content_type__ = "portfolio.piece"
    __table_args__ = (
        CheckConstraint(slug_rule("slug"), name="slug_rule"),
        CheckConstraint("btrim(title) <> ''", name="titled"),
        CheckConstraint(f"char_length(about) <= {MAX_ABOUT}", name="about_length"),
        CheckConstraint(f"year IS NULL OR year >= {MIN_YEAR}", name="year_range"),
        CheckConstraint("(video_url IS NULL) = (video_id IS NULL)", name="video_whole"),
        # A YouTube video's id is 11 of its letters, never fewer (cubic on #171).
        CheckConstraint(
            f"video_id IS NULL OR video_id ~ '{VIDEO_ID_PATTERN}'", name="video_id_shape"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_portfolio_piece_live", "status", "published_at"),
        Index("ix_portfolio_piece_updated_at", "updated_at"),
        Index("ix_portfolio_piece_artist_id", "artist_id"),
        *lifecycle.table_args("portfolio_piece"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The row's edits: one more on each save, sent back with the next so two never cross.
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(MAX_TITLE))
    #: Where the site shows it: /art/piece/<slug>.
    slug: Mapped[str] = mapped_column(String(MAX_SLUG), unique=True)
    #: Who it's by, and whose it is to edit; cleared when their account goes,
    #: and the piece stays the site's.
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL")
    )
    year: Mapped[int | None] = mapped_column(SmallInteger)
    #: A few words about it, plain text.
    about: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: Its picture, the media library's image (`media.public`): always one.
    image_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    #: A video's watch address, https://www.youtube.com/watch?v=<id>, and its id.
    video_url: Mapped[str | None] = mapped_column(String(MAX_VIDEO_URL))
    video_id: Mapped[str | None] = mapped_column(String(11))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
