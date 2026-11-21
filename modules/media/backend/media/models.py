"""The media library's tables (`dev plans/contracts/media.md` §3).

`media_image` is one image of the library: its file is in the kernel's public
bucket at `media/<id>/<file_version>.<ext>`, with its smaller copies beside it
(`pictures.WIDTHS`), and the row says what it is and what it means. A replace
gives it a new `version` under the same id, so every page that places it shows
the new file. `media_use` is where a module placed one (`public.use`): the
image can't be deleted while any is left.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base

#: The longest alt text, as VybeSite's library has it.
MAX_ALT = 250
#: The longest file name kept as a label.
MAX_FILENAME = 150
#: The longest use key, label and link a module may record.
MAX_OWNER = 200
MAX_LABEL = 200
MAX_LINK = 500


class MediaImage(Base):
    __tablename__ = "media_image"
    __table_args__ = (
        CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'image/webp')", name="content_type_known"
        ),
        # Read aloud: one line, no control character. The line breaks above
        # U+007F by number, since only some databases' ctype counts them.
        CheckConstraint(
            "alt !~ '[[:cntrl:]]' AND strpos(alt, chr(133)) = 0 AND strpos(alt, chr(8232)) = 0 "
            "AND strpos(alt, chr(8233)) = 0",
            name="alt_one_line",
        ),
        # A picture that is only decoration says nothing.
        CheckConstraint(
            "NOT decorative OR alt IS NULL OR btrim(alt) = ''", name="decorative_unsaid"
        ),
        CheckConstraint("version >= 1 AND file_version >= 1", name="versions_positive"),
        Index("ix_media_image_created_at", "created_at"),
        Index("ix_media_image_uploaded_by", "uploaded_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The row's edits: one more on each change, sent back with the next so two never cross.
    version: Mapped[int] = mapped_column(Integer, default=1)
    #: Which file is the image's now, in its keys: 1, then one more on each replace.
    file_version: Mapped[int] = mapped_column(Integer, default=1)
    content_type: Mapped[str] = mapped_column(String(20))
    #: Of our encoding: the same image uploaded again is found by this, not stored twice.
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    #: The length of the stored file. Not `bytes`, which would hide the builtin.
    byte_count: Mapped[int] = mapped_column("bytes", Integer)
    #: The name it was uploaded with, cleaned: a label for people, never part of a key.
    filename: Mapped[str] = mapped_column(String(MAX_FILENAME))
    #: What a screen reader says of it, wherever it's placed; none until typed.
    alt: Mapped[str | None] = mapped_column(String(MAX_ALT))
    #: Only decoration: drawn with empty alt text, so screen readers skip it.
    decorative: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: Who uploaded it; cleared when their account goes, and the image stays the site's.
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MediaUse(Base):
    """Where a module placed an image: `owner` is the using thing's key,
    `<module>.<type>:<id>`, `label` names it for people and `link` goes to it."""

    __tablename__ = "media_use"
    __table_args__ = (UniqueConstraint("image_id", "owner", name="uq_media_use_image_id_owner"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_image.id", ondelete="RESTRICT")
    )
    owner: Mapped[str] = mapped_column(String(MAX_OWNER), index=True)
    label: Mapped[str] = mapped_column(String(MAX_LABEL))
    link: Mapped[str] = mapped_column(String(MAX_LINK))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
