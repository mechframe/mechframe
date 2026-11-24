"""The blog's routes (`dev plans/contracts/blog.md` §2), mounted by the kernel
at /api/blog behind require_module("blog"). The live posts and the categories
are the public's; everything under /admin is staff's. A generated cover
(decision 0065) is drawn by the AI and kept in the media library."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from media import public as media
from sqlalchemy.ext.asyncio import AsyncSession

from blog import covers, service
from blog.models import Post
from blog.schemas import (
    BlogAdminCategoryList,
    BlogAuthorList,
    BlogCategoryList,
    CoverAsk,
    CoverDrawn,
    CoverState,
    CoverStored,
    CoverUse,
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
from kernel import Problem, ai, get_db, markdown, public, require_permission, svg, taxonomy

router = APIRouter()

WRITE = require_permission("blog.post.write")
PUBLISH = require_permission("blog.post.publish")
AI = require_permission("kernel.ai.write")
UPLOAD = require_permission("media.image.upload")
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
    return {"items": await service.live_categories(db)}


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


# --- generated covers (decision 0065, `dev plans/contracts/blog-covers.md` §2) ----------------

REFUSED = "That cover can't be used. Draw it again."


def _asked(field: str, message: str) -> Problem:
    return Problem(
        "kernel.invalid_request",
        422,
        "Some of what was sent isn't valid.",
        errors={field: [message]},
    )


def _cleaned(drawing: str) -> str:
    """A drawing the browser sent, cleaned again: 422 `blog.cover_refused` when nothing is left."""
    try:
        return covers.clean(drawing)
    except svg.Refused:
        raise Problem("blog.cover_refused", 422, REFUSED, errors={"svg": [REFUSED]}) from None


@router.get("/admin/covers", response_model=CoverState, dependencies=[Depends(WRITE)])
async def cover_state() -> dict[str, Any]:
    """Whether a drawn cover could be kept now: Draw a cover shows only while it could."""
    return {"storage": media.storage_on()}


@router.post(
    "/admin/covers/draw",
    response_model=CoverDrawn,
    dependencies=[Depends(WRITE), Depends(AI), Depends(ai.budget)],
)
async def draw_cover(body: CoverAsk, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """A cover drawn by the AI from the post as it stands, cleaned, with its
    preview rendered as the PNG kept will be: one call against the AI's budget,
    its repair try included. For a revision, `current` and `changes`."""
    if body.style == "custom" and not body.description.strip():
        raise _asked("description", "Say what to draw.")
    if body.style != "custom" and not (body.title.strip() or body.body.strip()):
        raise _asked("title", "Give the post a title or some words first.")
    if body.changes.strip() and body.current is None:
        raise _asked("current", "Send the cover to change.")
    current = (
        covers.without_wordmark(_cleaned(body.current))
        if body.current is not None and body.changes.strip()
        else None
    )
    colours = covers.Colours(**body.colours.model_dump()) if body.colours else None
    writer = await ai.client(db)
    drawn = await covers.draw(
        writer,
        title=body.title,
        summary=body.summary,
        body=body.body,
        style=body.style,
        description=body.description,
        colours=colours,
        wordmark=body.wordmark,
        current=current,
        changes=body.changes,
    )
    try:
        shown = await covers.preview(drawn.svg)
    except svg.Refused:
        raise Problem("kernel.ai_failed", 502, covers.FAILED) from None
    return {"svg": drawn.svg, "alt": drawn.alt, "preview": shown}


@router.post("/admin/covers", response_model=CoverStored, status_code=201)
async def keep_cover(
    body: CoverUse,
    user: Any = Depends(WRITE),
    _: Any = Depends(UPLOAD),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The cover shown, cleaned again, made a PNG twice the card and kept in
    the media library with its alt text. It spends no AI budget."""
    cleaned = _cleaned(body.svg)
    try:
        data = await covers.png(cleaned)
    except svg.Refused as refused:
        raise Problem("blog.cover_refused", 422, REFUSED, errors={"svg": [str(refused)]}) from None
    picture = await media.store(db, data, filename="cover.png", alt=body.alt, by=user.id)
    await db.commit()
    return {"cover": service.cover_of(picture)}
