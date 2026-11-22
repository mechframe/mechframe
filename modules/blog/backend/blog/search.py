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


class Posts(search.Source):
    content_type = service.CONTENT_TYPE

    async def document(self, db: AsyncSession, content_id: uuid.UUID) -> search.Document | None:
        post = await db.scalar(select(Post).where(Post.id == content_id, lifecycle.visible(Post)))
        return None if post is None else service.document(post)

    async def documents(self, db: AsyncSession) -> AsyncIterator[search.Document]:
        for post in await db.scalars(select(Post).where(lifecycle.visible(Post)).order_by(Post.id)):
            yield service.document(post)


SEARCH: tuple[search.Source, ...] = (Posts(),)
