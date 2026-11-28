"""What other modules may call (SPEC 7), when they list `portfolio` in
`requires`, and what a site's own code may: live pieces as a grid shows them,
for roster's profile and a shop's listing. Only live pieces are ever
answered, each as `GET /api/portfolio/pieces` answers it."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from portfolio import service
from portfolio.schemas import PieceCard

__all__ = ["PieceCard", "piece_cards", "pieces_by"]


async def piece_cards(db: AsyncSession, ids: Sequence[uuid.UUID]) -> list[PieceCard]:
    """The live pieces of `ids`, in the order given; any other is left out."""
    pieces = await service.live_in_order(db, ids)
    return [PieceCard.model_validate(card) for card in await service.cards(db, pieces)]


async def pieces_by(
    db: AsyncSession, artist_id: uuid.UUID, *, limit: int = service.PER_PAGE
) -> list[PieceCard]:
    """The live pieces credited to `artist_id`, newest first."""
    page = await service.page_of(db, discipline=None, cursor=None, limit=limit, artist_id=artist_id)
    return [PieceCard.model_validate(card) for card in page["items"]]
