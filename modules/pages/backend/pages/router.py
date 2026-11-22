"""The pages' routes (`dev plans/contracts/pages.md` §2), mounted by the kernel
at /api/pages behind require_module("pages"). The live page and the menus are
the public's; everything under /admin is staff's."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, get_db, markdown, public, require_permission, server_copy
from pages import service
from pages.models import MAX_ADDRESS, Page
from pages.schemas import (
    Full,
    LivePage,
    Menu,
    Moved,
    NewPage,
    PageChange,
    PageList,
    Preview,
    PreviewBody,
    Publish,
)

router = APIRouter()

WRITE = require_permission("pages.page.write")
PUBLISH = require_permission("pages.page.publish")


def _routes(request: Request) -> server_copy.Routes | None:
    """The start's route table, which says who answers an address."""
    return getattr(request.app.state, "public_routes", None)


@router.get(
    "/page",
    response_model=LivePage | Moved,
    dependencies=[Depends(public)],
    responses={404: {"description": "No live page is at that address"}},
)
async def read_page(
    address: Annotated[str, Query(max_length=MAX_ADDRESS + 1)],
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The live page at `address` (`/about`), or `{moved}` for an address a live page left."""
    found = await service.live(db, address)
    if found is None:
        raise Problem("pages.page_not_found", 404, "There's no page at that address.")
    if isinstance(found, Page):
        return await service.shown(db, found)
    return {"moved": await service.moved_to(db, found)}


@router.get("/menu", response_model=Menu, dependencies=[Depends(public)])
async def read_menu(
    place: Literal["header", "footer"], db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The live pages in the header's menu or the footer's, in their order."""
    pages = await service.menu(db, place)
    return {"items": [{"title": page.title, "address": page.address} for page in pages]}


@router.get("/admin/pages", response_model=PageList, dependencies=[Depends(WRITE)])
async def list_pages(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Every page, newest edit first."""
    return {"items": await service.every(db)}


@router.post("/admin/pages", response_model=Full, status_code=201)
async def new_page(
    body: NewPage,
    request: Request,
    user: Any = Depends(WRITE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A draft; 409 `pages.address_taken`, naming who answers the address."""
    page = await service.create(db, body.model_dump(), by=user.id, routes=_routes(request))
    shown = await service.full(db, page)
    await db.commit()
    return shown


@router.get("/admin/pages/{page_id}", response_model=Full, dependencies=[Depends(WRITE)])
async def read_one(page_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """One page with its Markdown, its `version` and the addresses it left."""
    return await service.full(db, await service.get(db, page_id))


@router.patch("/admin/pages/{page_id}", response_model=Full)
async def save_page(
    page_id: uuid.UUID,
    body: PageChange,
    request: Request,
    user: Any = Depends(WRITE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves it, and a live page changes on the site at once; 409 `pages.changed`
    on a stale `version`, with the page now."""
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    page = await service.change(
        db, page_id, body.version, fields, by=user.id, routes=_routes(request)
    )
    shown = await service.full(db, page)
    await db.commit()
    return shown


@router.post("/admin/preview", response_model=Preview, dependencies=[Depends(WRITE)])
async def preview(body: PreviewBody) -> dict[str, str]:
    """The HTML the site would draw for `body`, saved or not."""
    return {"html": markdown.render(body.body)}


@router.post("/admin/pages/{page_id}/publish", response_model=Full)
async def publish_page(
    page_id: uuid.UUID,
    body: Publish | None = None,
    user: Any = Depends(PUBLISH),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Live now, or scheduled for `at`."""
    page = await service.publish(db, page_id, body.at if body else None, by=user.id)
    shown = await service.full(db, page)
    await db.commit()
    return shown


@router.post("/admin/pages/{page_id}/unpublish", response_model=Full)
async def unpublish_page(
    page_id: uuid.UUID, user: Any = Depends(PUBLISH), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Back to a draft: its address answers 404."""
    page = await service.unpublish(db, page_id, by=user.id)
    shown = await service.full(db, page)
    await db.commit()
    return shown


@router.delete("/admin/pages/{page_id}", status_code=204)
async def delete_page(
    page_id: uuid.UUID, user: Any = Depends(PUBLISH), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone, with the addresses it left."""
    await service.remove(db, page_id, by=user.id)
    await db.commit()
    return Response(status_code=204)
