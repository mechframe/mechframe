"""featured's routes (`dev plans/contracts/featured.md` §2), mounted by the
kernel at /api/featured behind require_module("featured"). A slot's live
read is the public's; its list, the picker and YouTube's links need
`featured.placement.manage`, and making, changing and removing slots
`featured.slot.manage`."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from featured import service
from featured.schemas import (
    AdminSlots,
    FullSlot,
    LiveSlot,
    NewSlot,
    PastedIn,
    PastedLinks,
    PlacementsPut,
    RefChoices,
    SlotChange,
)
from kernel import answer, get_db, public, rate_limit, require_permission

router = APIRouter()

PLACE = require_permission("featured.placement.manage")
SLOTS = require_permission("featured.slot.manage")
#: The homepage reads its players at each visit; a minute old is fine.
CACHE = "public, max-age=60"
#: YouTube's titles, asked for at each paste.
PASTES_PER_ACCOUNT = "120/1h"


@router.get("/slots/{key}", response_model=LiveSlot, dependencies=[Depends(public)])
async def read_live_slot(key: str, db: AsyncSession = Depends(get_db)) -> Response:
    """What's live in the slot now, in order. Built with `answer`, as a route
    that sets a header is (SPEC 7)."""
    found = await service.live_slot(db, key)
    if found is None:
        raise service.slot_not_found()
    return answer(LiveSlot, found, headers={"Cache-Control": CACHE})


@router.get("/admin/slots", response_model=AdminSlots, dependencies=[Depends(PLACE)])
async def list_slots(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Every slot with its counts and what's live first, in the order they were
    made, and the types a slot may take."""
    return await service.every_slot(db)


@router.get("/admin/slots/{key}", response_model=FullSlot, dependencies=[Depends(PLACE)])
async def read_slot(key: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The slot and every placement in it, live, scheduled and ended."""
    return await service.full_slot(db, await service.get_slot(db, key))


@router.put("/admin/slots/{key}/placements", response_model=FullSlot)
async def save_placements(
    key: str,
    body: PlacementsPut,
    user: Any = Depends(PLACE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The whole list in one save, live at once. 409 `featured.changed` on a
    stale `version`, with the slot as it is now."""
    slot = await service.save_placements(db, key, body.version, body.items, by=user.id)
    shown = await service.full_slot(db, slot)
    await db.commit()
    return shown


@router.get("/admin/slots/{key}/pick", response_model=RefChoices, dependencies=[Depends(PLACE)])
async def pick(
    key: str,
    type: Annotated[str, Query(min_length=1, max_length=80)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A page of things of `type` to add, drafts too, newest edit first."""
    return await service.choices(db, key, type, q, cursor)


@router.post(
    "/admin/youtube",
    response_model=PastedLinks,
    dependencies=[Depends(PLACE), Depends(rate_limit(PASTES_PER_ACCOUNT, key="account"))],
)
async def read_links(body: PastedIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Each link read as a YouTube video, with YouTube's title while
    `oembed_titles` is on; the others refused."""
    return await service.pasted(db, body.urls)


@router.post("/admin/slots", response_model=FullSlot, status_code=201)
async def new_slot(
    body: NewSlot, user: Any = Depends(SLOTS), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A new slot. 409 `featured.key_taken`; 422 `featured.unknown_type`."""
    slot = await service.create_slot(
        db, body.key, body.label, body.accepts, body.kinds, body.on_dashboard, by=user.id
    )
    shown = await service.full_slot(db, slot)
    await db.commit()
    return shown


@router.patch("/admin/slots/{key}", response_model=FullSlot)
async def change_slot(
    key: str,
    body: SlotChange,
    user: Any = Depends(SLOTS),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves the fields sent. 409 `featured.changed` on a stale `version`, and
    `featured.in_use` for a type or a kind a placement still uses."""
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    slot = await service.change_slot(db, key, body.version, fields, by=user.id)
    shown = await service.full_slot(db, slot)
    await db.commit()
    return shown


@router.delete("/admin/slots/{key}", status_code=204)
async def delete_slot(
    key: str, user: Any = Depends(SLOTS), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone, with its placements."""
    await service.remove_slot(db, key, by=user.id)
    await db.commit()
    return Response(status_code=204)
