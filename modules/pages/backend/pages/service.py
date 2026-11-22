"""The pages' logic (`dev plans/contracts/pages.md` §2): write, save,
publish, unpublish and delete a page, read a live one or the move an old
address left, and list each menu.

**A save of a live page changes the site at once** (the owner, §8, 3): there
is no working copy. Its search document is written again in the same
transaction (`kernel.search.index`); publishing and unpublishing are the
kernel's to index, through the lifecycle's events.

**A move** follows the page, not an address: it names the page, so a page
moved twice sends both old addresses to where it is now, and none chains.
Only a live page leaves one, since nobody could have found a draft.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, audit, clock, lifecycle, markdown, search, server_copy
from pages import addresses
from pages.models import MAX_SEARCH_DESCRIPTION, Move, Page

CONTENT_TYPE = "pages.page"
#: The kernel's people, read for the name the last editor goes by.
_people = sa.table("auth_user", sa.column("id"), sa.column("display_name"), sa.column("email"))
#: What a save may change.
FIELDS = (
    "title",
    "address",
    "body",
    "search_title",
    "search_description",
    "in_header",
    "in_footer",
    "menu_order",
)


def _not_found() -> Problem:
    return Problem("pages.page_not_found", 404, "There's no such page.")


async def get(db: AsyncSession, page_id: uuid.UUID, *, lock: bool = False) -> Page:
    statement = select(Page).where(Page.id == page_id)
    found = await db.scalar(statement.with_for_update() if lock else statement)
    if found is None:
        raise _not_found()
    return found


async def names(db: AsyncSession, people: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The name each editor goes by: their display name, else their address."""
    if not people:
        return {}
    rows = await db.execute(
        select(_people.c.id, _people.c.display_name, _people.c.email).where(
            _people.c.id.in_(people)
        )
    )
    return {row.id: (row.display_name or row.email) for row in rows}


async def moves_of(db: AsyncSession, page_id: uuid.UUID) -> list[str]:
    return list(
        await db.scalars(select(Move.address).where(Move.page_id == page_id).order_by(Move.address))
    )


def _when(at: datetime | None) -> str | None:
    return at.isoformat() if at is not None else None


def listed(page: Page, named: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "id": str(page.id),
        "title": page.title,
        "address": page.address,
        "status": page.status,
        "in_header": page.in_header,
        "in_footer": page.in_footer,
        "menu_order": page.menu_order,
        "publish_at": _when(page.publish_at),
        "updated_at": page.updated_at.isoformat(),
        "updated_by": named.get(page.updated_by) if page.updated_by else None,
    }


async def full(db: AsyncSession, page: Page) -> dict[str, Any]:
    named = await names(db, {page.updated_by} if page.updated_by else set())
    return {
        **listed(page, named),
        "body": page.body,
        "search_title": page.search_title,
        "search_description": page.search_description,
        "published_at": _when(page.published_at),
        "version": page.version,
        "moves": await moves_of(db, page.id),
    }


async def every(db: AsyncSession) -> list[dict[str, Any]]:
    """Every page, newest edit first."""
    rows = list(await db.scalars(select(Page).order_by(Page.updated_at.desc(), Page.id)))
    named = await names(db, {row.updated_by for row in rows if row.updated_by})
    return [listed(row, named) for row in rows]


# --- what the site shows --------------------------------------------------------------------


def description(page: Page) -> str:
    """The page's description: its own, else its body's opening words."""
    return page.search_description or markdown.excerpt(
        markdown.plain(page.body), MAX_SEARCH_DESCRIPTION
    )


def search_title(page: Page, site_name: str) -> str:
    """Its title in search results: its own, else the title and the site's name,
    as the kernel titles its own pages."""
    return page.search_title or (f"{page.title} · {site_name}" if site_name else page.title)


async def live(db: AsyncSession, address: str) -> Page | Move | None:
    """The live page at `address`, else the move a live page left there, else None."""
    if not addresses.valid(address):
        return None
    page = await db.scalar(select(Page).where(Page.address == address, lifecycle.visible(Page)))
    if page is not None:
        return page
    move = await db.scalar(
        select(Move)
        .join(Page, Page.id == Move.page_id)
        .where(Move.address == address, lifecycle.visible(Page), Page.address != address)
    )
    return move


async def moved_to(db: AsyncSession, move: Move) -> str:
    page = await get(db, move.page_id)
    return page.address


async def shown(db: AsyncSession, page: Page) -> dict[str, Any]:
    site = await server_copy.identity(db)
    return {
        "title": page.title,
        "address": page.address,
        "html": markdown.render(page.body),
        "search_title": search_title(page, site.name),
        "search_description": description(page),
        "updated_at": page.updated_at.isoformat(),
    }


async def menu(db: AsyncSession, place: str) -> list[Page]:
    """The live pages in the header's menu or the footer's, in their order."""
    column = Page.in_header if place == "header" else Page.in_footer
    return list(
        await db.scalars(
            select(Page)
            .where(column.is_(True), lifecycle.visible(Page))
            .order_by(Page.menu_order, Page.title, Page.id)
        )
    )


def document(page: Page) -> search.Document:
    return search.Document(
        CONTENT_TYPE, page.id, page.title, markdown.plain(page.body), page.address
    )


# --- changing -------------------------------------------------------------------------------


async def _free(
    db: AsyncSession, address: str, routes: server_copy.Routes | None, page_id: uuid.UUID | None
) -> None:
    """Refuses an address another page has, or that the site answers otherwise."""
    other = await db.scalar(select(Page).where(Page.address == address, Page.id != page_id))
    if other is not None:
        raise Problem(
            "pages.address_taken",
            409,
            f"Another page, {other.title}, is at {address}. Choose another address.",
            errors={"address": [f"{other.title} is at {address}."]},
            extra={"owner": "pages", "page": {"id": str(other.id), "title": other.title}},
        )
    owner = addresses.answered_by(address, routes)
    if owner is not None:
        raise Problem(
            "pages.address_taken",
            409,
            f"{address} is {owner}'s address, so a page there would never show. Choose another.",
            errors={"address": [f"{address} belongs to {owner}."]},
            extra={"owner": owner},
        )


def _taken(address: str) -> Problem:
    """Another page took the address as this one was saved (the unique index)."""
    return Problem(
        "pages.address_taken",
        409,
        f"Another page took {address} just now. Choose another address.",
        errors={"address": [f"Another page is at {address}."]},
        extra={"owner": "pages"},
    )


def _blank(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


async def create(
    db: AsyncSession,
    fields: dict[str, Any],
    *,
    by: uuid.UUID | None,
    routes: server_copy.Routes | None,
) -> Page:
    """A new page, a draft."""
    await _free(db, fields["address"], routes, None)
    now = clock.now()
    page = Page(
        id=uuid.uuid4(),
        version=1,
        title=fields["title"],
        address=fields["address"],
        body=fields.get("body", ""),
        search_title=_blank(fields.get("search_title")),
        search_description=_blank(fields.get("search_description")),
        in_header=fields.get("in_header", False),
        in_footer=fields.get("in_footer", False),
        menu_order=fields.get("menu_order", 0),
        updated_by=by,
        created_at=now,
        updated_at=now,
    )
    db.add(page)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise _taken(fields["address"]) from None
    # The address a page holds is its own, live or not: a move there ends (CodeRabbit on #121).
    await db.execute(delete(Move).where(Move.address == page.address))
    audit.record(db, "pages.page.created", actor=by, target=(CONTENT_TYPE, page.id))
    return page


async def _leave(db: AsyncSession, page: Page, old: str) -> None:
    """The live page left `old`: a move from there to wherever it goes."""
    statement = insert(Move).values(address=old, page_id=page.id, created_at=clock.now())
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[Move.address],
            set_={
                "page_id": statement.excluded.page_id,
                "created_at": statement.excluded.created_at,
            },
        )
    )


async def change(
    db: AsyncSession,
    page_id: uuid.UUID,
    version: int,
    fields: dict[str, Any],
    *,
    by: uuid.UUID | None,
    routes: server_copy.Routes | None,
) -> Page:
    """Saves the fields sent; 409 `pages.changed` on a stale `version`, with the page now."""
    page = await get(db, page_id, lock=True)
    if version != page.version:
        raise Problem(
            "pages.changed",
            409,
            "Someone saved this page since you opened it. Here is how it reads now.",
            extra={"page": await full(db, page)},
        )
    old = page.address
    address = fields.get("address") or old  # null leaves it as it is
    if address != old:
        await _free(db, address, routes, page.id)
    for name in FIELDS:
        if name not in fields:
            continue
        value = fields[name]
        if name in ("search_title", "search_description"):
            value = _blank(value)
        elif value is None:
            continue  # a field that can't be empty, sent as null, is left as it is
        setattr(page, name, value)
    page.version += 1
    page.updated_at = clock.now()
    page.updated_by = by
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise _taken(address) from None
    if address != old:
        # The address a page holds is its own, live or not: a move there ends
        # (CodeRabbit on #121); the one it left is a move, while it's live.
        await db.execute(delete(Move).where(Move.address == address))
        if page.status == lifecycle.PUBLISHED:
            await _leave(db, page, old)
    if page.status == lifecycle.PUBLISHED:
        await search.index(db, document(page))
    audit.record(
        db,
        "pages.page.changed",
        actor=by,
        target=(CONTENT_TYPE, page.id),
        details={"moved_from": old} if address != old else None,
    )
    return page


def _at(text: str) -> datetime:
    try:
        at = datetime.fromisoformat(text)
    except ValueError:
        at = None
    if at is None or at.utcoffset() is None:
        raise Problem(
            "kernel.invalid_request",
            422,
            "That isn't a time with its zone, such as 2026-12-01T09:00:00+00:00.",
            errors={"at": ["A time with its zone, such as 2026-12-01T09:00:00+00:00."]},
        )
    return at


async def publish(
    db: AsyncSession, page_id: uuid.UUID, at: str | None, *, by: uuid.UUID | None
) -> Page:
    """Live now, or at `at` (the kernel's `publish_due` shows it within a minute)."""
    page = await get(db, page_id, lock=True)
    if at is None:
        await lifecycle.publish(db, page)
        audit.record(db, "pages.page.published", actor=by, target=(CONTENT_TYPE, page.id))
    else:
        when = _at(at)
        await lifecycle.schedule(db, page, when)
        audit.record(
            db,
            "pages.page.scheduled",
            actor=by,
            target=(CONTENT_TYPE, page.id),
            details={"at": when.isoformat()},
        )
    return page


async def unpublish(db: AsyncSession, page_id: uuid.UUID, *, by: uuid.UUID | None) -> Page:
    """Back to a draft: its address answers 404, and its moves with it."""
    page = await get(db, page_id, lock=True)
    await lifecycle.unpublish(db, page)
    audit.record(db, "pages.page.unpublished", actor=by, target=(CONTENT_TYPE, page.id))
    return page


async def remove(db: AsyncSession, page_id: uuid.UUID, *, by: uuid.UUID | None) -> None:
    """The page gone, with its moves; out of search."""
    page = await get(db, page_id, lock=True)
    await db.delete(page)
    await db.flush()
    await search.remove(db, CONTENT_TYPE, page_id)
    audit.record(
        db,
        "pages.page.deleted",
        actor=by,
        target=(CONTENT_TYPE, page_id),
        details={"address": page.address},
    )
