"""The blog's tables (`dev plans/contracts/blog.md` §3).

`blog_post` is one post: its title, its address under /blog (its slug), its
summary, its body in Markdown, its cover (media's image id, no foreign key
across modules), its author, its search words and the three After publishing
switches, drafted, scheduled and published through the kernel's lifecycle.
The HTML isn't stored: `kernel.markdown.render` makes it on each read. Its
category is the kernel's taxonomy (`blog_category`), not a column.

`blog_slug_move` is a slug a live post left: it sends visitors to the post,
wherever the post is now, so a move never chains (pages' moves).

`blog_post_related` is a post another lists under its body, in the order its
writer chose: up to three, never itself (VybeSite's `related_posts.py`).
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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base, lifecycle

#: A slug: lowercase letters and digits, single hyphens between them.
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_SLUG = 80
MAX_TITLE = 200
#: The card's line and the description's fallback.
MAX_SUMMARY = 300
#: A body's characters (kernel.markdown: a module caps its own).
MAX_BODY = 100_000
#: VybeSite's limits for the words in search results.
MAX_SEARCH_TITLE = 70
MAX_SEARCH_DESCRIPTION = 160
#: The most related posts one post lists.
MAX_RELATED = 3


def slug_rule(column: str) -> str:
    return f"{column} ~ '{SLUG_PATTERN}'"


class Post(lifecycle.Publishable, Base):
    __tablename__ = "blog_post"
    __content_type__ = "blog.post"
    __table_args__ = (
        CheckConstraint(slug_rule("slug"), name="slug_rule"),
        CheckConstraint("btrim(title) <> ''", name="titled"),
        CheckConstraint(f"char_length(body) <= {MAX_BODY}", name="body_length"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_blog_post_updated_at", "updated_at"),
        Index("ix_blog_post_published_at", "published_at"),
        Index("ix_blog_post_author_id", "author_id"),
        Index("ix_blog_post_cover_id", "cover_id"),
        *lifecycle.table_args("blog_post"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The row's edits: one more on each save, sent back with the next so two never cross.
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(MAX_TITLE))
    #: Where the site shows it: /blog/<slug>.
    slug: Mapped[str] = mapped_column(String(MAX_SLUG), unique=True)
    #: One line for its card and for sharing.
    summary: Mapped[str] = mapped_column(String(MAX_SUMMARY), default="", server_default="")
    #: What the post says, in Markdown.
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: The media library's image (`media.public`); none draws a plain card.
    cover_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    #: Who wrote it; cleared when their account goes, and the post stays the site's.
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_user.id", ondelete="SET NULL")
    )
    #: The title in search results and when shared; none uses the title and the site's name.
    search_title: Mapped[str | None] = mapped_column(String(MAX_SEARCH_TITLE))
    #: The description; none uses the summary, else the body's opening words.
    search_description: Mapped[str | None] = mapped_column(String(MAX_SEARCH_DESCRIPTION))
    #: After publishing (the board's three switches): stored for `comments`,
    #: and sent with `blog.post.published` for `community` and `campaigns`.
    allow_comments: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    post_to_community: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    email_subscribers: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: When `blog.post.published` went out: once a post, on its first publish.
    announced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SlugMove(Base):
    """A slug a live post left, sending visitors on to it (a 301). A live post
    at the same slug wins; the post's own slug is never one."""

    __tablename__ = "blog_slug_move"
    __table_args__ = (CheckConstraint(slug_rule("slug"), name="slug_rule"),)

    slug: Mapped[str] = mapped_column(String(MAX_SLUG), primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blog_post.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Related(Base):
    """A post `post_id` lists under its body, at `position` (from 0). Deleting
    either post deletes the link; one unpublished later is shown nowhere and
    dropped at the listing post's next save."""

    __tablename__ = "blog_post_related"
    __table_args__ = (
        CheckConstraint("post_id <> related_id", name="not_itself"),
        CheckConstraint(f"position >= 0 AND position < {MAX_RELATED}", name="position_range"),
        UniqueConstraint("post_id", "position"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("blog_post.id", ondelete="CASCADE"), primary_key=True
    )
    #: Indexed for the cascade from this side: a deleted post's links to it.
    related_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blog_post.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    position: Mapped[int] = mapped_column(SmallInteger)
