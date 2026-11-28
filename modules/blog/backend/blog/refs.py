"""blog's things another module may point at (kernel.refs, hook 11, decision
0072; `dev plans/contracts/reactions.md` §2, "Blog 0.1.8"): its posts,
`blog.post` ("Posts"), drafts too.

- **A post** is live while the site shows it (`lifecycle.visible`); its line is
  its category and the day it was published, "News, 28 November 2026", or
  "News, not published" for a draft.
- **The picker** finds by title, drafts included, newest edit first, a page at
  a time from a cursor of its own (`<updated_at>~<id>`); a cursor that isn't
  one is a ValueError, which `kernel.refs`' callers answer 422.

Its picture is its cover's smallest copy. Reactions asks through `kernel.refs`
whether a post takes a reaction now, and a featured slot may hold posts:
nothing here imports either.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from media import public as media
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blog import service
from blog.models import Post
from kernel import lifecycle, refs


def _thumb(picture: media.Picture | None) -> str | None:
    """A cover's smallest copy: the first of its srcset, smallest first."""
    if picture is None:
        return None
    first = picture.srcset.split(",", 1)[0].strip().rsplit(" ", 1)[0]
    return first or picture.url


def line(post: Post, category: dict[str, str] | None, *, live: bool) -> str:
    """ "News, 28 November 2026": its category when it has one, and the day it
    was published, or "not published" while the site doesn't show it."""
    day = post.published_at
    parts = [category["label"]] if category else []
    parts.append(f"{day.day} {day:%B %Y}" if live and day is not None else "not published")
    text = ", ".join(parts)
    return text[:1].upper() + text[1:]


def _after(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    """A page's cursor, `<updated_at>~<id>`; ValueError for anything else."""
    if cursor is None:
        return None
    at, mark, ident = cursor.partition("~")
    when = datetime.fromisoformat(at) if mark else None
    if when is None or when.utcoffset() is None:
        raise ValueError(f"{cursor!r} isn't a page of blog's posts.")
    return when, uuid.UUID(ident)


def _matching(q: str | None) -> Any:
    """The title holding `q`'s words as typed, `%` and `_` meaning themselves."""
    if not q:
        return sa.true()
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return Post.title.ilike(f"%{escaped}%", escape="\\")


class Posts(refs.Source):
    type = service.CONTENT_TYPE
    label = "Posts"

    async def _refs(self, db: AsyncSession, posts: Sequence[Post]) -> list[refs.Ref]:
        pictures = await service.covers_of(db, posts)
        categories = await service.categories_of(db, [post.id for post in posts])
        found: list[refs.Ref] = []
        for post in posts:
            live = post.status == lifecycle.PUBLISHED
            found.append(
                refs.Ref(
                    id=post.id,
                    title=post.title,
                    line=line(post, categories.get(post.id), live=live),
                    image=_thumb(pictures.get(post.cover_id) if post.cover_id else None),
                    path=service.path(post) if live else None,
                    live=live,
                )
            )
        return found

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        posts = list(await db.scalars(select(Post).where(Post.id.in_(list(ids)))))
        return {ref.id: ref for ref in await self._refs(db, posts)}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        statement = select(Post).where(_matching(q))
        after = _after(cursor)
        if after is not None:
            statement = statement.where(
                sa.tuple_(Post.updated_at, Post.id)
                < sa.tuple_(
                    sa.literal(after[0], Post.updated_at.type),
                    sa.literal(after[1], Post.id.type),
                )
            )
        rows = list(
            await db.scalars(
                statement.order_by(Post.updated_at.desc(), Post.id.desc()).limit(limit + 1)
            )
        )
        last = rows[limit - 1] if len(rows) > limit else None
        return {
            "items": await self._refs(db, rows[:limit]),
            "next_cursor": f"{last.updated_at.isoformat()}~{last.id}" if last else None,
        }


REFS: tuple[refs.Source, ...] = (Posts(),)
