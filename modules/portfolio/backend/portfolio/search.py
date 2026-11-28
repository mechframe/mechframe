"""portfolio: what site search finds of it (kernel.search, hook 3, decision
0052): each live piece, by its title, its words, its artist and its
discipline. The kernel indexes a piece as it's published and unpublished; a
save of a live piece indexes it again (`service.change`), and a delete takes
it out (`service.remove`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle, search
from portfolio import service
from portfolio.models import Piece

#: The pieces a reindex reads at a time.
PAGE = 200


class Pieces(search.Source):
    content_type = service.CONTENT_TYPE

    async def document(self, db: AsyncSession, content_id: uuid.UUID) -> search.Document | None:
        piece = await db.scalar(
            select(Piece).where(Piece.id == content_id, lifecycle.visible(Piece))
        )
        return None if piece is None else await service.document(db, piece)

    async def documents(self, db: AsyncSession) -> AsyncIterator[search.Document]:
        """Every live piece, a page at a time by id, so a big portfolio isn't read whole."""
        after: uuid.UUID | None = None
        while True:
            statement = select(Piece).where(lifecycle.visible(Piece)).order_by(Piece.id).limit(PAGE)
            if after is not None:
                statement = statement.where(Piece.id > after)
            found = list(await db.scalars(statement))
            for document in await service.documents(db, found):
                yield document
            if len(found) < PAGE:
                return
            after = found[-1].id


SEARCH: tuple[search.Source, ...] = (Pieces(),)
