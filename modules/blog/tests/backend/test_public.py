"""blog's public reads for a site's own pages (`blog.public`, SPEC 7): each the
API's answer for the same read, only live posts ever answered."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from blog import public, service
from blog.models import Post
from blog.schemas import BlogCategoryList, LivePost, PostCards, PostMoved
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, clock, taxonomy

from ..conftest import make_person, slug

pytestmark = pytest.mark.db


async def _new(db: AsyncSession, **fields: Any) -> Post:
    post = await service.create(
        db, {"title": "A post", "slug": slug(), "body": "Some words.", **fields}, by=None
    )
    await db.commit()
    return post


async def _live(db: AsyncSession, **fields: Any) -> Post:
    post = await _new(db, **fields)
    await service.publish(db, post.id, None, by=None)
    await db.commit()
    return post


async def _category(db: AsyncSession, label: str) -> str:
    found = taxonomy.vocabulary("blog_category")
    assert found is not None
    term = f"c-{uuid.uuid4().hex[:10]}"
    await taxonomy.create(
        db, found, slug=term, label=label, parent_id=None, position=0, actor=await make_person(db)
    )
    await db.commit()
    return term


def test_a_posts_page_is_under_blog() -> None:
    assert public.path("ten-years") == "/blog/ten-years"
    assert public.PER_PAGE == 12


async def test_the_posts_are_the_apis_a_page_at_a_time_of_one_category(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    term = await _category(db, "News")
    # One minute apart, so newest first is one order. Only the clock goes back after: undo()
    # would take the conftest's patches too.
    now = clock.now
    start = now()
    monkeypatch.setattr(clock, "now", lambda: start)
    first = await _live(db, category=term, title="First")
    monkeypatch.setattr(clock, "now", lambda: start + timedelta(minutes=1))
    second = await _live(db, category=term, title="Second")
    monkeypatch.setattr(clock, "now", now)
    await _new(db, category=term, title="A draft")

    page = await public.posts(db, category=term, limit=1)
    assert isinstance(page, PostCards)
    assert page.model_dump() == await service.page_of(db, category=term, cursor=None, limit=1)
    assert [card.slug for card in page.items] == [second.slug]
    assert page.next_cursor is not None
    after = await public.posts(db, category=term, cursor=page.next_cursor, limit=1)
    assert [card.slug for card in after.items] == [first.slug]
    assert after.next_cursor is None

    with pytest.raises(Problem) as refused:
        await public.posts(db, cursor="yesterday")
    assert refused.value.status == 422


async def test_the_newest_are_the_first_page_of_the_list(db: AsyncSession) -> None:
    await _live(db, title="New")
    newest = await public.newest(db)
    listed = await service.page_of(db, category=None, cursor=None)
    assert [card.model_dump() for card in newest] == listed["items"]


async def test_a_post_is_the_live_one_or_where_it_moved_and_nothing_else(db: AsyncSession) -> None:
    post = await _live(db, title="Ten years", body="Hello **there**.")
    found = await public.post(db, post.slug)
    assert isinstance(found, LivePost)
    assert found.model_dump() == await service.shown(db, post)
    assert "<strong>there</strong>" in found.html

    old = post.slug
    post = await service.change(db, post.id, post.version, {"slug": slug()}, by=None)
    await db.commit()
    assert await public.post(db, old) == PostMoved(moved=public.path(post.slug))

    draft = await _new(db)
    assert await public.post(db, draft.slug) is None
    assert await public.post(db, "Not A Slug!") is None


async def test_the_categories_count_their_live_posts(db: AsyncSession) -> None:
    term = await _category(db, "Poetry")
    await _live(db, category=term)
    await _new(db, category=term)
    found = await public.categories(db)
    assert isinstance(found, BlogCategoryList)
    counted = {each.slug: (each.label, each.posts) for each in found.items}
    assert counted[term] == ("Poetry", 1)
    assert found.model_dump() == {"items": await service.live_categories(db)}
