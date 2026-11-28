"""blog's posts as another module points at them (kernel.refs, hook 11;
`dev plans/contracts/reactions.md` §2, "Blog 0.1.8"): `find` answers drafts
too, each with whether it's live and its page while it is, and leaves out a
post that's gone; `pick` matches the title, newest edit first, a page at a time."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from blog import service
from blog.models import Post
from blog.refs import Posts
from sqlalchemy.ext.asyncio import AsyncSession

from ..conftest import slug

pytestmark = pytest.mark.db


async def _new(db: AsyncSession, **fields: Any) -> Post:
    post = await service.create(
        db, {"title": "A post", "slug": slug(), "body": "Some words.", **fields}, by=None
    )
    await db.commit()
    return post


async def test_find_answers_drafts_too_and_leaves_out_whats_gone(db: AsyncSession) -> None:
    live = await _new(db, title="Catalyst is out")
    await service.publish(db, live.id, None, by=None)
    await db.commit()
    draft = await _new(db, title="Still writing")
    gone = uuid.uuid4()

    found = await Posts().find(db, [live.id, draft.id, gone])
    assert set(found) == {live.id, draft.id}
    shown = found[live.id]
    assert (shown.title, shown.path, shown.live) == ("Catalyst is out", service.path(live), True)
    assert shown.line.endswith(f"{live.published_at.day} {live.published_at:%B %Y}")  # type: ignore[union-attr]
    hidden = found[draft.id]
    assert (hidden.path, hidden.live, hidden.line) == (None, False, "Not published")


async def test_an_unpublished_post_isnt_live(db: AsyncSession) -> None:
    post = await _new(db)
    await service.publish(db, post.id, None, by=None)
    await db.commit()
    await service.unpublish(db, post.id, by=None)
    await db.commit()
    found = (await Posts().find(db, [post.id]))[post.id]
    assert (found.live, found.path, found.line) == (False, None, "Not published")


async def test_pick_matches_the_title_newest_edit_first_a_page_at_a_time(db: AsyncSession) -> None:
    word = uuid.uuid4().hex[:10]
    first = await _new(db, title=f"{word} one")
    second = await _new(db, title=f"{word} two")
    await _new(db, title="Something else")

    page = await Posts().pick(db, word, cursor=None, limit=1)
    assert [each.id for each in page["items"]] == [second.id]
    assert page["next_cursor"] is not None
    rest = await Posts().pick(db, word, cursor=page["next_cursor"], limit=1)
    assert [each.id for each in rest["items"]] == [first.id]
    assert rest["next_cursor"] is None
    with pytest.raises(ValueError, match="isn't a page"):
        await Posts().pick(db, word, cursor="not-a-cursor", limit=1)


async def test_pick_takes_percent_and_underscore_as_typed(db: AsyncSession) -> None:
    word = uuid.uuid4().hex[:10]
    await _new(db, title=f"{word} 100% off")
    await _new(db, title=f"{word} 100 off")
    page = await Posts().pick(db, f"{word} 100%", cursor=None, limit=10)
    assert [each.title for each in page["items"]] == [f"{word} 100% off"]
    # An underscore is itself, never any one character (cubic on #170).
    await _new(db, title=f"{word} a_b")
    await _new(db, title=f"{word} axb")
    page = await Posts().pick(db, f"{word} a_b", cursor=None, limit=10)
    assert [each.title for each in page["items"]] == [f"{word} a_b"]
