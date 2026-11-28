"""portfolio's routes (`dev plans/contracts/portfolio.md` §2), mounted by the
kernel at /api/portfolio behind require_module("portfolio"). The live pieces
and their disciplines are the public's; everything under /admin is for
someone holding `portfolio.piece.add` (their own pieces) or
`portfolio.piece.manage` (every piece), worked out by `who`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import (
    OwnerOr,
    Problem,
    get_db,
    public,
    require_owner_or,
    require_permission,
    settings,
    taxonomy,
)
from portfolio import service
from portfolio.schemas import (
    AdminDisciplineList,
    AdminPiece,
    AdminPieceList,
    ArtistList,
    ArtPage,
    DisciplineList,
    LivePiece,
    NewPiece,
    PieceCards,
    PieceChange,
    PublishPiece,
    Settings,
)

router = APIRouter()

MANAGE = require_permission(service.MANAGE)
_MANAGER = require_owner_or(service.MANAGE)
_ADDER = require_owner_or(service.ADD)
_SLUG = f"^{taxonomy.SLUG.pattern}$"


@dataclass(frozen=True)
class Who:
    """The signed-in person, and which of portfolio's two permissions they hold."""

    id: uuid.UUID
    manages: bool
    adds: bool


async def _holds(guard: OwnerOr) -> bool:
    """Whether the guard's permission is held: `check(None)` passes staff
    holding it alone, since no one owns nothing."""
    try:
        await guard.check(None)
    except Problem:
        return False
    return True


async def who(manager: OwnerOr = Depends(_MANAGER), adder: OwnerOr = Depends(_ADDER)) -> Who:
    """403 unless the person holds `portfolio.piece.add` or `portfolio.piece.manage`."""
    manages, adds = await _holds(manager), await _holds(adder)
    if not (manages or adds):
        raise Problem("kernel.forbidden", 403, "You don't have permission to do that.")
    return Who(manager.user.id, manages, adds)


async def _settings(db: AsyncSession) -> Settings:
    found = await settings.for_module(db, "portfolio")
    return found if isinstance(found, Settings) else Settings()


async def _per_page(db: AsyncSession) -> int:
    return (await _settings(db)).pieces_per_page


# --- the public's ----------------------------------------------------------------------------


@router.get("/pieces", response_model=PieceCards, dependencies=[Depends(public)])
async def list_pieces(
    discipline: Annotated[str | None, Query(max_length=80, pattern=_SLUG)] = None,
    cursor: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int | None, Query(ge=1, le=60)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The live pieces, newest first, the settings' `pieces_per_page` a page;
    of one discipline when it's named, 404 for one that isn't."""
    return await service.page_of(
        db, discipline=discipline, cursor=cursor, limit=limit or await _per_page(db)
    )


@router.get("/pieces/{slug}", response_model=LivePiece, dependencies=[Depends(public)])
async def read_piece(slug: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The live piece at /art/piece/<slug>."""
    found = await service.live(db, slug)
    if found is None:
        raise Problem("portfolio.piece_not_found", 404, "There's no piece at that address.")
    return await service.shown(db, found)


@router.get("/art", response_model=ArtPage, dependencies=[Depends(public)])
async def art_page(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The Art page's lead and its commission link, from the settings."""
    found = await _settings(db)
    return {"lead": found.lead, "commission_link": found.commission_link}


@router.get("/disciplines", response_model=DisciplineList, dependencies=[Depends(public)])
async def list_disciplines(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The disciplines with a live piece, in the order staff set."""
    return {"items": await service.live_disciplines(db)}


# --- the admin's -----------------------------------------------------------------------------


@router.get("/admin/pieces", response_model=AdminPieceList)
async def list_admin_pieces(
    q: Annotated[str | None, Query(max_length=200)] = None,
    discipline: Annotated[str | None, Query(max_length=80, pattern=_SLUG)] = None,
    cursor: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = service.ADMIN_PER_PAGE,
    person: Who = Depends(who),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Every piece for `manage`, else the ones credited to you, newest edit
    first, 50 a page: of one discipline, and matching `q` in the title."""
    return await service.every(
        db,
        mine=None if person.manages else person.id,
        q=q,
        discipline=discipline,
        cursor=cursor,
        limit=limit,
    )


@router.post("/admin/pieces", response_model=AdminPiece, status_code=201)
async def new_piece(
    body: NewPiece, person: Who = Depends(who), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A draft; 409 `portfolio.slug_taken` for a slug another piece has."""
    # Only the fields sent: an artist left out is whoever adds it, one sent as null no one.
    piece = await service.create(
        db,
        body.model_dump(exclude_unset=True),
        by=person.id,
        manages=person.manages,
        adds=person.adds,
    )
    shown = await service.one(db, piece)
    await db.commit()
    return shown


@router.get("/admin/pieces/{piece_id}", response_model=AdminPiece)
async def read_one(
    piece_id: uuid.UUID, person: Who = Depends(who), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """One piece with its `version`, for its artist or `manage`."""
    piece = await service.get(db, piece_id)
    service.may_change(piece, by=person.id, manages=person.manages, adds=person.adds)
    return await service.one(db, piece)


@router.patch("/admin/pieces/{piece_id}", response_model=AdminPiece)
async def save_piece(
    piece_id: uuid.UUID,
    body: PieceChange,
    person: Who = Depends(who),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves it, and a live piece changes on the site at once; 409
    `portfolio.changed` on a stale `version`, with the piece now."""
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    piece = await service.change(
        db,
        piece_id,
        body.version,
        fields,
        by=person.id,
        manages=person.manages,
        adds=person.adds,
    )
    shown = await service.one(db, piece)
    await db.commit()
    return shown


@router.post("/admin/pieces/{piece_id}/publish", response_model=AdminPiece)
async def publish_piece(
    piece_id: uuid.UUID,
    body: PublishPiece | None = None,
    person: Who = Depends(who),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Live now, or scheduled for `at`."""
    piece = await service.publish(
        db,
        piece_id,
        body.at if body else None,
        by=person.id,
        manages=person.manages,
        adds=person.adds,
    )
    shown = await service.one(db, piece)
    await db.commit()
    return shown


@router.post("/admin/pieces/{piece_id}/unpublish", response_model=AdminPiece)
async def unpublish_piece(
    piece_id: uuid.UUID, person: Who = Depends(who), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Back to a draft: its address answers 404."""
    piece = await service.unpublish(
        db, piece_id, by=person.id, manages=person.manages, adds=person.adds
    )
    shown = await service.one(db, piece)
    await db.commit()
    return shown


@router.delete("/admin/pieces/{piece_id}", status_code=204)
async def delete_piece(
    piece_id: uuid.UUID, person: Who = Depends(who), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone, with its discipline, its picture's use and its search document."""
    await service.remove(db, piece_id, by=person.id, manages=person.manages, adds=person.adds)
    await db.commit()
    return Response(status_code=204)


@router.get("/admin/artists", response_model=ArtistList, dependencies=[Depends(MANAGE)])
async def list_artists(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Who a piece may be credited to: every active account that may add pieces."""
    return {"items": await service.artists(db)}


@router.get("/admin/disciplines", response_model=AdminDisciplineList)
async def list_admin_disciplines(
    _: Who = Depends(who), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Every discipline with its id and all its pieces, for the chips and the Disciplines dialog."""
    found = await service.counted(db, live=False)
    return {
        "items": [
            {
                "id": each["id"],
                "slug": each["slug"],
                "label": each["label"],
                "position": each["position"],
                "pieces": each["pieces"],
            }
            for each in found
        ]
    }
