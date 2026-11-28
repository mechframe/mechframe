"""portfolio's things another module may point at (kernel.refs, hook 11,
decision 0072): its pieces, `portfolio.piece` ("Pieces"), drafts too, so
`featured` can feature art and roster can point at a member's pieces without
importing portfolio.

- **A piece** is live while it's published; its line is "Graphic design, by
  petro, 2026", leaving out what it hasn't got, and its picture's smallest
  copy is its image.
- **The picker** finds by title, drafts included, newest edit first, a page
  at a time from a cursor of its own (`<updated_at>~<id>`); a cursor that
  isn't one is a ValueError, which `kernel.refs`' callers answer 422.
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

from kernel import lifecycle, refs
from portfolio import service
from portfolio.models import Piece


def _thumb(picture: media.Picture | None) -> str | None:
    """A picture's smallest copy: the first of its srcset, smallest first."""
    if picture is None:
        return None
    first = picture.srcset.split(",", 1)[0].strip().rsplit(" ", 1)[0]
    return first or picture.url


def _after(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    """A page's cursor, `<updated_at>~<id>`; ValueError for anything else."""
    if cursor is None:
        return None
    at, mark, ident = cursor.partition("~")
    when = datetime.fromisoformat(at) if mark else None
    if when is None or when.utcoffset() is None:
        raise ValueError(f"{cursor!r} isn't a page of portfolio's pieces.")
    return when, uuid.UUID(ident)


def _matching(column: Any, q: str | None) -> Any:
    """`column` holding `q`'s words as typed, `%` and `_` meaning themselves."""
    if not q:
        return sa.true()
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")


class Pieces(refs.Source):
    type = "portfolio.piece"
    label = "Pieces"

    async def _refs(self, db: AsyncSession, pieces: Sequence[Piece]) -> list[refs.Ref]:
        pictures = await service.pictures_of(db, pieces)
        cards = await service.cards(db, pieces)
        found: list[refs.Ref] = []
        for piece, card in zip(pieces, cards, strict=True):
            live = piece.status == lifecycle.PUBLISHED
            found.append(
                refs.Ref(
                    id=piece.id,
                    title=piece.title,
                    line=service.line(card["discipline"], card["artist"], piece.year),
                    image=_thumb(pictures.get(piece.image_id)),
                    path=service.path(piece) if live else None,
                    live=live,
                )
            )
        return found

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        pieces = list(await db.scalars(select(Piece).where(Piece.id.in_(list(ids)))))
        return {ref.id: ref for ref in await self._refs(db, pieces)}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        statement = select(Piece).where(_matching(Piece.title, q))
        after = _after(cursor)
        if after is not None:
            statement = statement.where(
                sa.tuple_(Piece.updated_at, Piece.id)
                < sa.tuple_(
                    sa.literal(after[0], Piece.updated_at.type),
                    sa.literal(after[1], Piece.id.type),
                )
            )
        rows = list(
            await db.scalars(
                statement.order_by(Piece.updated_at.desc(), Piece.id.desc()).limit(limit + 1)
            )
        )
        last = rows[limit - 1] if len(rows) > limit else None
        return {
            "items": await self._refs(db, rows[:limit]),
            "next_cursor": None if last is None else f"{last.updated_at.isoformat()}~{last.id}",
        }


REFS: tuple[refs.Source, ...] = (Pieces(),)
