"""blog: what site search finds of it (kernel.search, hook 3, decision 0052):
each live post, by its title, its summary and its body's words. The kernel
indexes a post as it's published and unpublished; a save of a live post
indexes it again (`service.change`), and a delete takes it out
(`service.remove`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blog import service
from blog.models import Post
from kernel import lifecycle, search

#: The posts a reindex reads at a time.
PAGE = 200


class Posts(search.Source):
    content_type = service.CONTENT_TYPE

    async def document(self, db: AsyncSession, content_id: uuid.UUID) -> search.Document | None:
        post = await db.scalar(select(Post).where(Post.id == content_id, lifecycle.visible(Post)))
        return None if post is None else service.document(post)

    async def documents(self, db: AsyncSession) -> AsyncIterator[search.Document]:
        """Every live post, a page at a time by id, so a big blog isn't read whole
        (CodeRabbit on #123)."""
        after: uuid.UUID | None = None
        while True:
            statement = select(Post).where(lifecycle.visible(Post)).order_by(Post.id).limit(PAGE)
            if after is not None:
                statement = statement.where(Post.id > after)
            found = list(await db.scalars(statement))
            for post in found:
                yield service.document(post)
            if len(found) < PAGE:
                return
            after = found[-1].id


SEARCH: tuple[search.Source, ...] = (Posts(),)
