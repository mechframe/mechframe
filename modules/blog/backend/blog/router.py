"""The blog's routes (`dev plans/contracts/blog.md` §2), mounted by the kernel
at /api/blog behind require_module("blog"). The live posts and the categories
are the public's; everything under /admin is staff's."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from blog import service
from blog.models import Post
from blog.schemas import (
    BlogAdminCategoryList,
    BlogAuthorList,
    BlogCategoryList,
    FullPost,
    LivePost,
    NewPost,
    PostCards,
    PostChange,
    PostList,
    PostMoved,
    PostPreview,
    PostPreviewBody,
    PublishPost,
)
from kernel import Problem, get_db, markdown, public, require_permission, taxonomy

router = APIRouter()

WRITE = require_permission("blog.post.write")
PUBLISH = require_permission("blog.post.publish")
_SLUG = f"^{taxonomy.SLUG.pattern}$"


@router.get("/posts", response_model=PostCards, dependencies=[Depends(public)])
async def list_posts(
    category: Annotated[str | None, Query(max_length=80, pattern=_SLUG)] = None,
    cursor: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = service.PER_PAGE,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The live posts, newest first, 12 a page; of one category when it's named."""
    return await service.page_of(db, category=category, cursor=cursor, limit=limit)


@router.get("/posts/{slug}", response_model=LivePost | PostMoved, dependencies=[Depends(public)])
async def read_post(slug: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The live post at /blog/<slug>, or `{moved}` for a slug a live post left."""
    found = await service.live(db, slug)
    if found is None:
        raise Problem("blog.post_not_found", 404, "There's no post at that address.")
    if isinstance(found, Post):
        return await service.shown(db, found)
    return {"moved": await service.moved_to(db, found)}


@router.get("/categories", response_model=BlogCategoryList, dependencies=[Depends(public)])
async def list_categories(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Every category, in the order staff set, with its live posts."""
    found = await service.counted(db, live=True)
    return {
        "items": [
            {"slug": each["slug"], "label": each["label"], "posts": each["posts"]} for each in found
        ]
    }


@router.get("/admin/posts", response_model=PostList, dependencies=[Depends(WRITE)])
async def list_admin_posts(
    q: Annotated[str | None, Query(max_length=200)] = None,
    status: Literal["draft", "scheduled", "published"] | None = None,
    cursor: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = service.ADMIN_PER_PAGE,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Every post, newest edit first, 50 a page: of one state, and matching `q` in its title."""
    return await service.every(db, q=q, status=status, cursor=cursor, limit=limit)


@router.post("/admin/posts", response_model=FullPost, status_code=201)
async def new_post(
    body: NewPost, user: Any = Depends(WRITE), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A draft; 409 `blog.slug_taken` for a slug another post has."""
    # Only the fields sent: an author left out is the writer, one sent as null no one.
    post = await service.create(db, body.model_dump(exclude_unset=True), by=user.id)
    shown = await service.full(db, post)
    await db.commit()
    return shown


@router.get("/admin/posts/{post_id}", response_model=FullPost, dependencies=[Depends(WRITE)])
async def read_one(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """One post with its Markdown, its `version`, the slugs it left and its related posts."""
    return await service.full(db, await service.get(db, post_id))


@router.patch("/admin/posts/{post_id}", response_model=FullPost)
async def save_post(
    post_id: uuid.UUID,
    body: PostChange,
    user: Any = Depends(WRITE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves it, and a live post changes on the site at once; 409 `blog.changed`
    on a stale `version`, with the post now."""
    fields = body.model_dump(include=body.model_fields_set - {"version"})
    post = await service.change(db, post_id, body.version, fields, by=user.id)
    shown = await service.full(db, post)
    await db.commit()
    return shown


@router.post("/admin/preview", response_model=PostPreview, dependencies=[Depends(WRITE)])
async def preview(body: PostPreviewBody) -> dict[str, str]:
    """The HTML the site would draw for `body`, saved or not."""
    return {"html": markdown.render(body.body)}


@router.post("/admin/posts/{post_id}/publish", response_model=FullPost)
async def publish_post(
    post_id: uuid.UUID,
    body: PublishPost | None = None,
    user: Any = Depends(PUBLISH),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Live now, or scheduled for `at`."""
    post = await service.publish(db, post_id, body.at if body else None, by=user.id)
    shown = await service.full(db, post)
    await db.commit()
    return shown


@router.post("/admin/posts/{post_id}/unpublish", response_model=FullPost)
async def unpublish_post(
    post_id: uuid.UUID, user: Any = Depends(PUBLISH), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Back to a draft: its address answers 404."""
    post = await service.unpublish(db, post_id, by=user.id)
    shown = await service.full(db, post)
    await db.commit()
    return shown


@router.delete("/admin/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: uuid.UUID, user: Any = Depends(PUBLISH), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone, with the slugs it left, its links and its cover's use."""
    await service.remove(db, post_id, by=user.id)
    await db.commit()
    return Response(status_code=204)


@router.get(
    "/admin/categories", response_model=BlogAdminCategoryList, dependencies=[Depends(WRITE)]
)
async def list_admin_categories(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Every category with its id and all its posts, for the board's Categories card."""
    found = await service.counted(db, live=False)
    return {
        "items": [
            {
                "id": each["id"],
                "slug": each["slug"],
                "label": each["label"],
                "position": each["position"],
                "posts": each["posts"],
            }
            for each in found
        ]
    }


@router.get("/admin/authors", response_model=BlogAuthorList, dependencies=[Depends(WRITE)])
async def list_authors(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Who a post may name as its author: every active account that may write posts."""
    return {"items": await service.authors(db)}
