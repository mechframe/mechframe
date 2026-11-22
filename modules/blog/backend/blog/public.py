"""What a site's own code may call (SPEC 7): blog's public reads.

A site whose own Blog and Post pages replace blog's at `/blog` and
`/blog/<slug>` (the same rank, which `kernel.server_copy.build` allows) draws
blog's posts with these, in its server copy as blog's own `server_copy.py`
does. Each answer is the one the API gives for the same read (`GET
/api/blog/posts`, `/api/blog/posts/{slug}` and `/api/blog/categories`), so a
crawler reads what a person sees. Only live posts are ever answered.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from blog import service
from blog.models import Post
from blog.schemas import BlogCategoryList, LivePost, PostCard, PostCards, PostMoved

#: A page of the public list: 12 posts.
PER_PAGE = service.PER_PAGE


def path(slug: str) -> str:
    """A post's page on the site, such as /blog/new-words."""
    return f"{service.PREFIX}{slug}"


async def posts(
    db: AsyncSession,
    *,
    category: str | None = None,
    cursor: str | None = None,
    limit: int = PER_PAGE,
) -> PostCards:
    """A page of live posts, newest first, of one category when it's named; `next_cursor`
    asks for the page after it. A cursor that isn't one of these pages' is a 422 Problem."""
    return PostCards.model_validate(
        await service.page_of(db, category=category, cursor=cursor, limit=limit)
    )


async def newest(db: AsyncSession, limit: int = PER_PAGE) -> list[PostCard]:
    """The newest live posts, as a list shows them."""
    return [
        PostCard.model_validate(card)
        for card in await service.cards(db, await service.newest(db, limit))
    ]


async def post(db: AsyncSession, slug: str) -> LivePost | PostMoved | None:
    """The live post at `slug`; where it is now for a slug a live post left; else None."""
    found = await service.live(db, slug)
    if found is None:
        return None
    if isinstance(found, Post):
        return LivePost.model_validate(await service.shown(db, found))
    return PostMoved(moved=await service.moved_to(db, found))


async def categories(db: AsyncSession) -> BlogCategoryList:
    """Every category, in the order staff set, with its live posts."""
    return BlogCategoryList.model_validate({"items": await service.live_categories(db)})
