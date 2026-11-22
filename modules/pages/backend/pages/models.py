"""The pages' tables (`dev plans/contracts/pages.md` §3).

`pages_page` is one of the site's fixed pages: its title, its address, its
body in Markdown and its search words, drafted, scheduled and published
through the kernel's lifecycle, and its place in the header's and the footer's
menus. The HTML isn't stored: `kernel.markdown.render` makes it on each read.
`pages_move` is an address a live page left: it sends visitors to the page,
wherever the page is now, so a move never chains.
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
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base, lifecycle

#: An address is one segment: lowercase letters and digits, single hyphens
#: between them (VybeSite's rule, one segment deep).
ADDRESS_PATTERN = r"^/[a-z0-9]+(-[a-z0-9]+)*$"
MAX_ADDRESS = 60
MAX_TITLE = 120
#: A body's characters (kernel.markdown: a module caps its own).
MAX_BODY = 100_000
#: VybeSite's limits for the words in search results.
MAX_SEARCH_TITLE = 70
MAX_SEARCH_DESCRIPTION = 160


def address_rule(column: str) -> str:
    return f"{column} ~ '{ADDRESS_PATTERN}'"


class Page(lifecycle.Publishable, Base):
    __tablename__ = "pages_page"
    __content_type__ = "pages.page"
    __table_args__ = (
        CheckConstraint(address_rule("address"), name="address_rule"),
        CheckConstraint("btrim(title) <> ''", name="titled"),
        CheckConstraint(f"char_length(body) <= {MAX_BODY}", name="body_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_pages_page_updated_at", "updated_at"),
        Index("ix_pages_page_updated_by", "updated_by"),
        *lifecycle.table_args("pages_page"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The row's edits: one more on each save, sent back with the next so two never cross.
    version: Mapped[int] = mapped_column(Integer, default=1)
    #: What the menu and the page's heading call it.
    title: Mapped[str] = mapped_column(String(MAX_TITLE))
    #: Where the site shows it, such as /about.
    address: Mapped[str] = mapped_column(String(MAX_ADDRESS), unique=True)
    #: What the page says, in Markdown.
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: The title in search results and when shared; none uses the title and the site's name.
    search_title: Mapped[str | None] = mapped_column(String(MAX_SEARCH_TITLE))
    #: The description; none uses the body's opening words.
    search_description: Mapped[str | None] = mapped_column(String(MAX_SEARCH_DESCRIPTION))
    in_header: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    in_footer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: Its place in the menus it's in: lower first, then by title.
    menu_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: Who changed it last; cleared when their account goes, and the page stays the site's.
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Move(Base):
    """An address a live page left, sending visitors on to it (a 301). A live
    page at the same address wins; the page's own address is never one."""

    __tablename__ = "pages_move"
    __table_args__ = (CheckConstraint(address_rule("address"), name="address_rule"),)

    address: Mapped[str] = mapped_column(String(MAX_ADDRESS), primary_key=True)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages_page.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
