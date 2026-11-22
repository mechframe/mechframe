"""pages: what site search finds of it (kernel.search, hook 3, decision 0052):
each live page, by its title and its body's words. The kernel indexes a page
as it's published and unpublished; a save of a live page indexes it again
(`service.change`), and a delete takes it out (`service.remove`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle, search
from pages import service
from pages.models import Page


class Pages(search.Source):
    content_type = service.CONTENT_TYPE

    async def document(self, db: AsyncSession, content_id: uuid.UUID) -> search.Document | None:
        page = await db.scalar(select(Page).where(Page.id == content_id, lifecycle.visible(Page)))
        return None if page is None else service.document(page)

    async def documents(self, db: AsyncSession) -> AsyncIterator[search.Document]:
        for page in await db.scalars(select(Page).where(lifecycle.visible(Page)).order_by(Page.id)):
            yield service.document(page)


SEARCH: tuple[search.Source, ...] = (Pages(),)
