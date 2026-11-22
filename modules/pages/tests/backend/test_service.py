"""The pages' rules on the database (`dev plans/contracts/pages.md` §2, §3, §7):
addresses and who answers them, moves that never chain, saves that cross,
the menus, search, the hooks."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pages import addresses, dashboard, service
from pages import privacy as pages_privacy
from pages.models import Move, Page
from pages.seed import _NAMESPACE, PAGES
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, lifecycle, load_module, privacy, server_copy
from kernel import seed as seeding
from kernel.models import SearchDocument

from ..conftest import address, make_person

pytestmark = pytest.mark.db

MODULE = Path(__file__).resolve().parents[2]


class _Blog(server_copy.Pages):
    async def page(self, db: Any, path: str, params: Any) -> None:
        return None


def _routes() -> server_copy.Routes:
    """The start's route table with pages, a blog at /blog and the site's own /contact."""

    def module(raw: dict[str, Any], pages: server_copy.Pages) -> Any:
        """What `server_copy.build` reads of an installed module."""
        manifest = SimpleNamespace(raw=raw, name=raw["name"])
        return SimpleNamespace(id=raw["id"], manifest=manifest, pages=pages)

    from pages.server_copy import PAGES as LIVE

    pages = module({"id": "pages", "name": "Pages", "routes": {"public": ["/:address"]}}, LIVE)
    blog = module({"id": "blog", "name": "Blog", "routes": {"public": ["/blog"]}}, _Blog())
    site = server_copy.SitePages(public=("/contact",), pages=_Blog())
    return server_copy.build([pages, blog], site)


async def _new(db: AsyncSession, by: uuid.UUID | None = None, **fields: Any) -> Page:
    page = await service.create(
        db,
        {"title": "A page", "address": address(), "body": "Some words.", **fields},
        by=by,
        routes=None,
    )
    await db.commit()
    return page


async def _live(db: AsyncSession, **fields: Any) -> Page:
    page = await _new(db, **fields)
    await service.publish(db, page.id, None, by=None)
    await db.commit()
    return page


# --- addresses ---------------------------------------------------------------------------------


@pytest.mark.parametrize("given", ["/about", "/press-kit", "/a1", "/2026"])
def test_an_address_is_one_segment_of_lowercase_words_and_single_hyphens(given: str) -> None:
    assert addresses.valid(given)


@pytest.mark.parametrize(
    "given",
    [
        "/",
        "about",
        "/About",
        "/press--kit",
        "/-press",
        "/press-",
        "/a/b",
        "/a_b",
        "/a.b",
        "/" + "a" * 60,
    ],
)
def test_anything_else_isnt_an_address(given: str) -> None:
    assert not addresses.valid(given)


def test_an_address_the_site_answers_otherwise_names_who_does() -> None:
    routes = _routes()
    assert addresses.answered_by("/blog", routes) == "Blog"
    assert addresses.answered_by("/contact", routes) == "the site's own pages"
    for kernel in ("/sign-in", "/account", "/admin", "/api", "/auth", "/assets"):
        assert addresses.answered_by(kernel, routes) == "the kernel"
    assert addresses.answered_by("/about", routes) is None


async def test_a_page_cant_take_an_address_another_page_or_the_site_has(
    db: AsyncSession,
) -> None:
    first = await _new(db, title="First")
    first_id = str(first.id)  # read before the rollback expires the row
    with pytest.raises(Problem) as taken:
        await service.create(
            db, {"title": "Second", "address": first.address}, by=None, routes=None
        )
    await db.rollback()
    assert (taken.value.code, taken.value.status) == ("pages.address_taken", 409)
    assert taken.value.extra["page"] == {"id": first_id, "title": "First"}

    with pytest.raises(Problem) as blog:
        await service.create(db, {"title": "Blog", "address": "/blog"}, by=None, routes=_routes())
    await db.rollback()
    assert blog.value.extra == {"owner": "Blog"}
    assert "Blog's address" in blog.value.detail


# --- saving --------------------------------------------------------------------------------------


async def test_a_stale_save_is_refused_with_the_page_as_it_is_now(db: AsyncSession) -> None:
    page = await _new(db)
    await service.change(db, page.id, 1, {"title": "Theirs"}, by=None, routes=None)
    await db.commit()

    with pytest.raises(Problem) as stale:
        await service.change(db, page.id, 1, {"title": "Mine"}, by=None, routes=None)
    await db.rollback()

    assert (stale.value.code, stale.value.status) == ("pages.changed", 409)
    assert stale.value.extra["page"]["title"] == "Theirs"
    assert stale.value.extra["page"]["version"] == 2


async def test_a_save_sets_only_what_it_sends_and_an_empty_search_word_falls_back(
    db: AsyncSession,
) -> None:
    editor = await make_person(db, "Ana Editor")
    page = await _new(db, search_title="Ours", search_description="Said.")
    saved = await service.change(
        db, page.id, 1, {"search_title": "  ", "search_description": None}, by=editor, routes=None
    )
    await db.commit()
    assert (saved.title, saved.body, saved.search_title, saved.search_description) == (
        "A page",
        "Some words.",
        None,
        None,
    )
    assert saved.version == 2
    assert (await service.full(db, saved))["updated_by"] == "Ana Editor"
    assert service.description(saved) == "Some words."
    assert service.search_title(saved, "The Site") == "A page · The Site"


async def test_a_live_page_given_a_new_address_leaves_a_move_and_a_draft_none(
    db: AsyncSession,
) -> None:
    live = await _live(db)
    draft = await _new(db)
    old_live, old_draft = live.address, draft.address

    await service.change(db, live.id, 1, {"address": address()}, by=None, routes=None)
    await service.change(db, draft.id, 1, {"address": address()}, by=None, routes=None)
    await db.commit()

    assert await service.moves_of(db, live.id) == [old_live]
    assert await service.moves_of(db, draft.id) == []
    found = await service.live(db, old_live)
    assert isinstance(found, Move)
    assert await service.moved_to(db, found) == live.address
    assert await service.live(db, old_draft) is None


async def test_two_moves_both_go_to_where_the_page_is_now_and_never_chain(
    db: AsyncSession,
) -> None:
    page = await _live(db)
    first, second, third = page.address, address(), address()
    await service.change(db, page.id, 1, {"address": second}, by=None, routes=None)
    await service.change(db, page.id, 2, {"address": third}, by=None, routes=None)
    await db.commit()

    for old in (first, second):
        found = await service.live(db, old)
        assert isinstance(found, Move)
        assert await service.moved_to(db, found) == third

    # Back to where it began: its own address is never a move of its own.
    await service.change(db, page.id, 3, {"address": first}, by=None, routes=None)
    await db.commit()
    assert await service.moves_of(db, page.id) == sorted([second, third])
    assert isinstance(await service.live(db, first), Page)


async def test_a_page_taking_a_moves_address_ends_the_move_there(db: AsyncSession) -> None:
    """The address a page holds is its own, live or not: a move another page left
    there stops, so the page's unpublish answers 404 (CodeRabbit on #121)."""
    moved = await _live(db)
    left = moved.address
    await service.change(db, moved.id, 1, {"address": address()}, by=None, routes=None)
    await db.commit()
    assert isinstance(await service.live(db, left), Move)

    taker = await _new(db, address=left)
    assert await service.live(db, left) is None  # a draft holds it: no redirect
    await service.publish(db, taker.id, None, by=None)
    await db.commit()
    found = await service.live(db, left)
    assert isinstance(found, Page)
    assert found.id == taker.id

    await service.unpublish(db, taker.id, by=None)
    await db.commit()
    assert await service.live(db, left) is None
    assert left not in await service.moves_of(db, moved.id)


async def test_a_page_moved_onto_a_moves_address_ends_that_move_too(db: AsyncSession) -> None:
    moved = await _live(db)
    left = moved.address
    await service.change(db, moved.id, 1, {"address": address()}, by=None, routes=None)
    other = await _new(db)
    await service.change(db, other.id, 1, {"address": left}, by=None, routes=None)
    await db.commit()
    assert await service.moves_of(db, moved.id) == []
    assert await service.live(db, left) is None


async def test_deleting_a_page_takes_its_moves(db: AsyncSession) -> None:
    page = await _live(db)
    await service.change(db, page.id, 1, {"address": address()}, by=None, routes=None)
    await db.commit()

    await service.remove(db, page.id, by=None)
    await db.commit()

    left = await db.scalar(select(func.count()).select_from(Move).where(Move.page_id == page.id))
    assert left == 0


# --- the menus and search ----------------------------------------------------------------------------


async def test_each_menu_has_its_live_pages_in_their_order(db: AsyncSession) -> None:
    tag = uuid.uuid4().hex[:8]
    last = await _live(db, title=f"Zed {tag}", in_footer=True, menu_order=2)
    first = await _live(db, title=f"Bee {tag}", in_footer=True, in_header=True, menu_order=1)
    tie = await _live(db, title=f"Ant {tag}", in_footer=True, menu_order=2)
    await _new(db, title=f"Draft {tag}", in_footer=True, menu_order=0)

    footer = [page.id for page in await service.menu(db, "footer") if tag in page.title]
    header = [page.id for page in await service.menu(db, "header") if tag in page.title]

    assert footer == [first.id, tie.id, last.id]
    assert header == [first.id]


async def test_a_save_of_a_live_page_is_what_search_finds_and_a_delete_takes_it_out(
    db: AsyncSession,
) -> None:
    page = await _live(db)
    # Published here without the app's listeners, so the page's own save writes its document.
    await service.change(
        db,
        page.id,
        1,
        {"title": "Found", "body": "## Studio\n\nWe **record** here."},
        by=None,
        routes=None,
    )
    await db.commit()

    row = await db.scalar(select(SearchDocument).where(SearchDocument.content_id == page.id))
    assert row is not None
    assert (row.title, row.body, row.path) == ("Found", "Studio We record here.", page.address)

    await service.remove(db, page.id, by=None)
    await db.commit()
    gone = await db.scalar(select(SearchDocument).where(SearchDocument.content_id == page.id))
    assert gone is None


async def test_a_draft_saved_is_never_in_search(db: AsyncSession) -> None:
    page = await _new(db)
    await service.change(db, page.id, 1, {"title": "Hidden"}, by=None, routes=None)
    await db.commit()
    assert (
        await db.scalar(select(SearchDocument).where(SearchDocument.content_id == page.id))
    ) is None


async def test_a_scheduled_page_needs_a_time_with_its_zone(db: AsyncSession) -> None:
    page = await _new(db)
    page_id, at = page.id, page.address  # read before the rollback expires the row
    with pytest.raises(Problem) as zoneless:
        await service.publish(db, page_id, "2099-01-01T09:00:00", by=None)
    await db.rollback()
    assert (zoneless.value.status, list(zoneless.value.errors)) == (422, ["at"])

    scheduled = await service.publish(db, page_id, "2099-01-01T09:00:00+00:00", by=None)
    await db.commit()
    assert scheduled.status == lifecycle.SCHEDULED
    assert await service.live(db, at) is None


# --- the hooks ------------------------------------------------------------------------------------


async def test_export_lists_a_persons_pages_and_erase_forgets_who_changed_them(
    db: AsyncSession,
) -> None:
    person = await make_person(db)
    page = await _new(db, by=person)
    subject = privacy.Subject(user_id=person, email="x@example.test")

    exported = await pages_privacy.export_user_data(db, subject)
    assert [each["address"] for each in exported["pages"]] == [page.address]
    assert set(exported["pages"][0]) == {"id", "title", "address", "status", "last_changed_at"}

    await pages_privacy.delete_user_data(db, subject)
    await db.commit()
    await db.refresh(page)
    assert page.updated_by is None
    assert (await pages_privacy.export_user_data(db, subject)) == {"pages": []}


async def test_the_privacy_item_shows_until_a_privacy_page_is_live(db: AsyncSession) -> None:
    await db.execute(text("DELETE FROM pages_page WHERE address = '/privacy'"))
    await db.commit()
    try:
        (item,) = await dashboard.ATTENTION(db, None)
        assert (item.key, item.permission, item.to) == (
            "pages.no_privacy",
            "pages.page.write",
            "/admin/pages/new?address=privacy",
        )
        draft = await _new(db, title="Privacy", address="/privacy")
        (item,) = await dashboard.ATTENTION(db, None)
        assert item.to == f"/admin/pages/{draft.id}"  # Write it opens the draft there

        await service.publish(db, draft.id, None, by=None)
        await db.commit()
        assert await dashboard.ATTENTION(db, None) == []
    finally:
        await db.rollback()
        await db.execute(text("DELETE FROM pages_page WHERE address = '/privacy'"))
        await db.commit()


async def test_the_seed_gives_two_live_footer_pages_and_a_draft_once(db: AsyncSession) -> None:
    pages = load_module(MODULE / "module.json")
    allowed = {"MECHFRAME_ALLOW_SEED": "1"}

    await seeding.run(db, [pages], environ=allowed)
    ids = [uuid.uuid5(_NAMESPACE, each[0]) for each in PAGES]
    first = {
        row.id: (row.address, row.status, row.in_footer, row.version)
        for row in await db.scalars(select(Page).where(Page.id.in_(ids)))
    }
    await seeding.run(db, [pages], environ=allowed)
    db.expire_all()
    again = {
        row.id: (row.address, row.status, row.in_footer, row.version)
        for row in await db.scalars(select(Page).where(Page.id.in_(ids)))
    }

    assert again == first
    by_address = {address: status for address, status, *_ in first.values()}
    assert by_address == {"/about": "published", "/credits": "published", "/press-kit": "draft"}


async def test_a_field_that_cant_be_empty_sent_as_null_is_left_as_it_is(db: AsyncSession) -> None:
    page = await _live(db)
    saved = await service.change(
        db, page.id, 1, {"address": None, "title": None, "body": None}, by=None, routes=None
    )
    await db.commit()
    assert (saved.address, saved.title, saved.body) == (page.address, "A page", "Some words.")
    assert await service.moves_of(db, page.id) == []
