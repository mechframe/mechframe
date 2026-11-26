"""discography: what site search finds of it (kernel.search, hook 3): each
live release, by its title, its lines, its playable tracks' titles, every
credit and, while the site shows them, its lyrics, so a track is found by its
name or a credit and lands on its release. The kernel indexes a release as
it's published and unpublished; a save of a live release or its tracks
indexes it again (`service._touched`), and a delete takes it out."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from discography.models import Release
from kernel import lifecycle, search

#: The releases a reindex reads at a time.
PAGE = 200


class Releases(search.Source):
    content_type = service.CONTENT_TYPE

    async def document(self, db: AsyncSession, content_id: uuid.UUID) -> search.Document | None:
        release = await db.scalar(
            select(Release).where(Release.id == content_id, lifecycle.visible(Release))
        )
        return None if release is None else await service.document(db, release)

    async def documents(self, db: AsyncSession) -> AsyncIterator[search.Document]:
        after: uuid.UUID | None = None
        while True:
            statement = (
                select(Release).where(lifecycle.visible(Release)).order_by(Release.id).limit(PAGE)
            )
            if after is not None:
                statement = statement.where(Release.id > after)
            found = list(await db.scalars(statement))
            for each in await service.documents(db, found):  # the page's reads at once
                yield each
            if len(found) < PAGE:
                return
            after = found[-1].id


SEARCH: tuple[search.Source, ...] = (Releases(),)
