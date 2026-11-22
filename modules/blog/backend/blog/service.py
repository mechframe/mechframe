"""The blog's logic (`dev plans/contracts/blog.md` §2): write, save, publish,
unpublish and delete a post; read a live one or the move an old slug left;
list them by page and by category; their categories, covers, authors and
related posts.

**A save of a live post changes the site at once** (pages' contract §8, 3):
there is no working copy. Its search document is written again in the same
transaction; publishing and unpublishing are the kernel's to index.

**A move** follows the post, not a slug: it names the post, so a post moved
twice sends both old slugs to where it is now, and none chains. Only a live
post leaves one, since nobody could have found a draft. The slug a post holds
is its own, live or not: a post that takes a slug ends any move there.

**Its category** is one term of the kernel's `blog_category` (hook 2). A save
names an existing term: a writer never makes one, staff holding
`kernel.taxonomy.manage` do. **Its cover** is media's image: placing it
records the post as the image's use (`media.public.use`), and every other
image the post placed is let go. **Its related posts** are up to three live
posts; one unpublished later is shown nowhere and dropped at the next save
(VybeSite's `related_posts.py`).
"""

from __future__ import annotations

import math
import re
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from media import public as media
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from blog.models import (
    MAX_RELATED,
    MAX_SEARCH_DESCRIPTION,
    MAX_SLUG,
    SLUG_PATTERN,
    Post,
    Related,
    SlugMove,
)
from kernel import Problem, audit, clock, lifecycle, markdown, search, server_copy, taxonomy

CONTENT_TYPE = "blog.post"
VOCABULARY = "blog_category"
#: A live post's page: /blog/<slug>.
PREFIX = "/blog/"
#: The public list's page, and the admin's.
PER_PAGE = 12
ADMIN_PER_PAGE = 50
#: A reader's pace, for "n min read".
WORDS_A_MINUTE = 200
#: Who may be named a post's author: those holding this, through a role.
WRITE = "blog.post.write"
_SLUG = re.compile(SLUG_PATTERN)
#: The categories a site has: a few, so one read takes them all.
MAX_CATEGORIES = 500

#: The kernel's people and their roles, read for the names authors go by and
#: who may be one.
_people = sa.table(
    "auth_user",
    sa.column("id"),
    sa.column("display_name"),
    sa.column("email"),
    sa.column("status"),
)
_user_roles = sa.table("auth_user_role", sa.column("user_id"), sa.column("role_id"))
_grants = sa.table("auth_role_permission", sa.column("role_id"), sa.column("permission"))

#: What a save may change, as its body names them.
FIELDS = (
    "title",
    "slug",
    "summary",
    "body",
    "cover_id",
    "author_id",
    "search_title",
    "search_description",
    "allow_comments",
    "post_to_community",
    "email_subscribers",
)
#: Fields a save may send as null to clear.
_CLEARABLE = ("cover_id", "author_id", "search_title", "search_description")


def _not_found() -> Problem:
    return Problem("blog.post_not_found", 404, "There's no such post.")


def _invalid(field: str, code: str, message: str) -> Problem:
    return Problem(code, 422, message, errors={field: [message]})


def _uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise _invalid(field, "kernel.invalid_request", "That isn't an id.") from None


async def get(db: AsyncSession, post_id: uuid.UUID, *, lock: bool = False) -> Post:
    statement = select(Post).where(Post.id == post_id)
    found = await db.scalar(statement.with_for_update() if lock else statement)
    if found is None:
        raise _not_found()
    return found


def path(post: Post) -> str:
    return f"{PREFIX}{post.slug}"


def owner(post_id: uuid.UUID) -> str:
    """The post as the media library names a place an image is used."""
    return f"{CONTENT_TYPE}:{post_id}"


# --- slugs -----------------------------------------------------------------------------------


def slug_for(text: str) -> str:
    """The slug a title spells: "Don't stop" is `dont-stop`. Empty when it has
    no letters or digits to spell one with (VybeSite drops an apostrophe)."""
    folded = unicodedata.normalize("NFKD", text.replace("'", "").replace(chr(0x2019), ""))
    words: list[str] = []
    word = ""
    for each in folded.lower():
        if unicodedata.combining(each):
            continue
        if each.isascii() and each.isalnum():
            word += each
        elif word:
            words.append(word)
            word = ""
    if word:
        words.append(word)
    return "-".join(words)[:MAX_SLUG].strip("-")


async def unique_slug(db: AsyncSession, base: str, exclude: uuid.UUID | None = None) -> str:
    """`base`, or `base-2`, `base-3` and on, the first no other post has."""
    base = base or "post"
    slug, number = base, 2
    while True:
        taken = select(Post.id).where(Post.slug == slug)
        if exclude is not None:
            taken = taken.where(Post.id != exclude)
        if await db.scalar(taken) is None:
            return slug
        suffix = f"-{number}"
        slug = f"{base[: MAX_SLUG - len(suffix)].rstrip('-')}{suffix}"
        number += 1


def _taken(slug: str, title: str | None = None) -> Problem:
    said = (
        f"Another post, {title}, is at {PREFIX}{slug}."
        if title
        else (f"Another post took {PREFIX}{slug} just now.")
    )
    return Problem(
        "blog.slug_taken",
        409,
        f"{said} Choose another address.",
        errors={"slug": [said]},
    )


async def _free(db: AsyncSession, slug: str, post_id: uuid.UUID | None) -> None:
    other = await db.scalar(select(Post).where(Post.slug == slug, Post.id != post_id))
    if other is not None:
        raise _taken(slug, other.title)


# --- people ----------------------------------------------------------------------------------


async def _people_of(db: AsyncSession, ids: Iterable[uuid.UUID | None]) -> dict[uuid.UUID, Any]:
    wanted = {each for each in ids if each is not None}
    if not wanted:
        return {}
    rows = await db.execute(
        select(_people.c.id, _people.c.display_name, _people.c.email).where(
            _people.c.id.in_(wanted)
        )
    )
    return {row.id: row for row in rows}


def _staff_name(row: Any) -> str:
    return str(row.display_name or row.email)


def _public_name(row: Any | None) -> str | None:
    """The name a reader sees: a display name, never an address."""
    return str(row.display_name) if row is not None and row.display_name else None


async def authors(db: AsyncSession) -> list[dict[str, str]]:
    """Every active account that may write posts, by name: an owner, or anyone
    whose role holds `blog.post.write`."""
    writing_roles = select(_grants.c.role_id).where(_grants.c.permission == WRITE)
    may = select(_user_roles.c.user_id).where(
        or_(_user_roles.c.role_id == "owner", _user_roles.c.role_id.in_(writing_roles))
    )
    rows = await db.execute(
        select(_people.c.id, _people.c.display_name, _people.c.email).where(
            _people.c.id.in_(may), _people.c.status == "active"
        )
    )
    found = [{"id": str(row.id), "name": _staff_name(row)} for row in rows]
    return sorted(found, key=lambda each: (each["name"].casefold(), each["id"]))


async def _check_author(db: AsyncSession, author_id: uuid.UUID) -> None:
    if str(author_id) not in {each["id"] for each in await authors(db)}:
        raise _invalid(
            "author_id",
            "blog.author_not_allowed",
            "A post's author is someone who may write posts.",
        )


# --- categories ------------------------------------------------------------------------------


async def terms(db: AsyncSession) -> list[dict[str, Any]]:
    """The blog's categories, in the order staff set: each term's id, slug, label and position."""
    found = taxonomy.vocabulary(VOCABULARY)
    if found is None:
        return []
    listed = await taxonomy.listed(db, found, cursor=None, limit=MAX_CATEGORIES)
    return list(listed["items"])


async def _check_category(db: AsyncSession, slug: str) -> None:
    if slug not in {term["slug"] for term in await terms(db)}:
        raise _invalid("category", "blog.category_not_found", "There's no such category.")


async def categories_of(
    db: AsyncSession, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, dict[str, str] | None]:
    """Each post's category, or None."""
    found = await taxonomy.terms_for(db, CONTENT_TYPE, ids)
    out: dict[uuid.UUID, dict[str, str] | None] = {}
    for ident, held in found.items():
        term = next((each for each in held if each.vocabulary == VOCABULARY), None)
        out[ident] = None if term is None else {"slug": term.slug, "label": term.label}
    return out


async def counted(db: AsyncSession, *, live: bool) -> list[dict[str, Any]]:
    """Every category with its posts: the live ones, or all of them."""
    out = []
    for term in await terms(db):
        statement = (
            select(func.count())
            .select_from(Post)
            .where(Post.id.in_(taxonomy.tagged(CONTENT_TYPE, VOCABULARY, term["slug"])))
        )
        if live:
            statement = statement.where(lifecycle.visible(Post))
        out.append({**term, "posts": int(await db.scalar(statement) or 0)})
    return out


# --- covers ----------------------------------------------------------------------------------


def _cover(picture: media.Picture | None) -> dict[str, Any] | None:
    if picture is None:
        return None
    return {
        "id": str(picture.id),
        "url": picture.url,
        "srcset": picture.srcset,
        "width": picture.width,
        "height": picture.height,
        "alt": picture.alt,
        "decorative": picture.decorative,
    }


async def covers_of(db: AsyncSession, posts: Sequence[Post]) -> dict[uuid.UUID, media.Picture]:
    return await media.pictures(db, [post.cover_id for post in posts if post.cover_id])


async def _check_cover(db: AsyncSession, cover_id: uuid.UUID) -> None:
    if await media.picture(db, cover_id) is None:
        raise _invalid("cover_id", "blog.cover_not_found", "The media library has no such image.")


async def _place_cover(db: AsyncSession, post: Post) -> None:
    """The post's cover recorded as its use, and any other image it placed let go."""
    if post.cover_id is not None:
        await media.use(
            db,
            post.cover_id,
            owner=owner(post.id),
            label=post.title,
            link=f"/admin/blog/{post.id}",
        )
    await media.release(db, owner=owner(post.id), keep=[post.cover_id] if post.cover_id else [])


# --- related posts ---------------------------------------------------------------------------


async def _check_related(
    db: AsyncSession, post_id: uuid.UUID | None, wanted: list[uuid.UUID]
) -> None:
    def refused(message: str) -> Problem:
        return _invalid("related", "blog.related_refused", message)

    if len(wanted) > MAX_RELATED:
        raise refused(f"A post lists up to {MAX_RELATED} related posts.")
    if len(set(wanted)) < len(wanted):
        raise refused("Each related post is listed once.")
    if post_id is not None and post_id in wanted:
        raise refused("A post can't be related to itself.")
    if not wanted:
        return
    found = {
        row.id: row
        for row in await db.execute(
            select(Post.id, Post.title, Post.status).where(Post.id.in_(wanted))
        )
    }
    for related_id in wanted:
        row = found.get(related_id)
        if row is None:
            raise refused("A related post no longer exists. Remove it and save again.")
        if row.status != lifecycle.PUBLISHED:
            raise refused(f"{row.title} isn't live, so it can't be a related post.")


async def _replace_related(db: AsyncSession, post_id: uuid.UUID, wanted: list[uuid.UUID]) -> None:
    await db.execute(delete(Related).where(Related.post_id == post_id))
    for position, related_id in enumerate(wanted):
        db.add(Related(post_id=post_id, related_id=related_id, position=position))
    await db.flush()


async def _prune_related(db: AsyncSession, post_id: uuid.UUID) -> None:
    """Drops the links to posts that aren't live any more."""
    live = select(Post.id).where(lifecycle.visible(Post))
    await db.execute(
        delete(Related).where(Related.post_id == post_id, Related.related_id.not_in(live))
    )


async def related_of(db: AsyncSession, post_id: uuid.UUID) -> list[dict[str, str]]:
    """The live posts `post_id` lists, in its order: id, title and slug."""
    rows = await db.execute(
        select(Post.id, Post.title, Post.slug)
        .join(Related, Related.related_id == Post.id)
        .where(Related.post_id == post_id, lifecycle.visible(Post))
        .order_by(Related.position)
    )
    return [{"id": str(row.id), "title": row.title, "slug": row.slug} for row in rows]


# --- what the site shows ---------------------------------------------------------------------


def reading_minutes(post: Post) -> int:
    return max(1, math.ceil(len(markdown.plain(post.body).split()) / WORDS_A_MINUTE))


def description(post: Post) -> str:
    """Its description: its own, else its summary, else its body's opening words."""
    return (
        post.search_description
        or post.summary
        or markdown.excerpt(markdown.plain(post.body), MAX_SEARCH_DESCRIPTION)
    )


def search_title(post: Post, site_name: str) -> str:
    """Its title in search results: its own, else the title and the site's name."""
    return post.search_title or (f"{post.title} · {site_name}" if site_name else post.title)


def document(post: Post) -> search.Document:
    words = " ".join(part for part in (post.summary, markdown.plain(post.body)) if part)
    return search.Document(CONTENT_TYPE, post.id, post.title, words, path(post))


async def live(db: AsyncSession, slug: str) -> Post | SlugMove | None:
    """The live post at `slug`, else the move a live post left there, else None."""
    if len(slug) > MAX_SLUG or _SLUG.fullmatch(slug) is None:
        return None
    found = await db.scalar(select(Post).where(Post.slug == slug, lifecycle.visible(Post)))
    if found is not None:
        return found
    move: SlugMove | None = await db.scalar(
        select(SlugMove)
        .join(Post, Post.id == SlugMove.post_id)
        .where(SlugMove.slug == slug, lifecycle.visible(Post), Post.slug != slug)
    )
    return move


async def moved_to(db: AsyncSession, move: SlugMove) -> str:
    return path(await get(db, move.post_id))


async def cards(db: AsyncSession, posts: Sequence[Post]) -> list[dict[str, Any]]:
    """Live posts as a list shows them, in the order given."""
    pictures = await covers_of(db, posts)
    categories = await categories_of(db, [post.id for post in posts])
    people = await _people_of(db, [post.author_id for post in posts])
    return [
        {
            "title": post.title,
            "slug": post.slug,
            "summary": post.summary,
            "cover": _cover(pictures.get(post.cover_id) if post.cover_id else None),
            "category": categories.get(post.id),
            "author": _public_name(people.get(post.author_id) if post.author_id else None),
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "reading_minutes": reading_minutes(post),
        }
        for post in posts
    ]


def _cursor_of(at: datetime, ident: uuid.UUID) -> str:
    return f"{at.isoformat()}~{ident}"


def _mark(at: datetime, ident: uuid.UUID) -> Any:
    """A cursor's place, as a row's (a time, then an id) is compared with it."""
    return sa.tuple_(sa.literal(at, Post.updated_at.type), sa.literal(ident, Post.id.type))


def _after(cursor: str) -> tuple[datetime, uuid.UUID]:
    at, mark, ident = cursor.partition("~")
    try:
        when, found = datetime.fromisoformat(at), uuid.UUID(ident)
    except ValueError:
        when = None
    if not mark or when is None or when.utcoffset() is None:
        raise _invalid("cursor", "kernel.invalid_request", "Not a page of these posts.")
    return when, found


async def page_of(
    db: AsyncSession, *, category: str | None, cursor: str | None, limit: int = PER_PAGE
) -> dict[str, Any]:
    """A page of live posts, newest first, of one category when it's named."""
    statement = select(Post).where(lifecycle.visible(Post))
    if category is not None:
        statement = statement.where(
            Post.id.in_(taxonomy.tagged(CONTENT_TYPE, VOCABULARY, category))
        )
    if cursor is not None:
        at, ident = _after(cursor)
        statement = statement.where(sa.tuple_(Post.published_at, Post.id) < _mark(at, ident))
    rows = list(
        await db.scalars(
            statement.order_by(Post.published_at.desc(), Post.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    last = rows[-1] if rows else None
    return {
        "items": await cards(db, rows),
        "next_cursor": (
            _cursor_of(last.published_at, last.id)
            if more and last is not None and last.published_at
            else None
        ),
    }


async def newest(db: AsyncSession, limit: int = PER_PAGE) -> list[Post]:
    return list(
        await db.scalars(
            select(Post)
            .where(lifecycle.visible(Post))
            .order_by(Post.published_at.desc(), Post.id.desc())
            .limit(limit)
        )
    )


async def shown(db: AsyncSession, post: Post) -> dict[str, Any]:
    site = await server_copy.identity(db)
    (card,) = await cards(db, [post])
    return {
        **card,
        "html": markdown.render(post.body),
        "updated_at": post.updated_at.isoformat(),
        "search_title": search_title(post, site.name),
        "search_description": description(post),
        "related": [
            {"title": each["title"], "slug": each["slug"]} for each in await related_of(db, post.id)
        ],
        "allow_comments": post.allow_comments,
    }


# --- the admin's reads -----------------------------------------------------------------------


def _when(at: datetime | None) -> str | None:
    return at.isoformat() if at is not None else None


async def listed(db: AsyncSession, posts: Sequence[Post]) -> list[dict[str, Any]]:
    categories = await categories_of(db, [post.id for post in posts])
    people = await _people_of(db, [post.author_id for post in posts])
    out = []
    for post in posts:
        person = people.get(post.author_id) if post.author_id else None
        out.append(
            {
                "id": str(post.id),
                "title": post.title,
                "slug": post.slug,
                "status": post.status,
                "category": categories.get(post.id),
                "author": (
                    None if person is None else {"id": str(person.id), "name": _staff_name(person)}
                ),
                "publish_at": _when(post.publish_at),
                "published_at": _when(post.published_at),
                "updated_at": post.updated_at.isoformat(),
                "has_cover": post.cover_id is not None,
            }
        )
    return out


async def moves_of(db: AsyncSession, post_id: uuid.UUID) -> list[str]:
    return list(
        await db.scalars(
            select(SlugMove.slug).where(SlugMove.post_id == post_id).order_by(SlugMove.slug)
        )
    )


async def full(db: AsyncSession, post: Post) -> dict[str, Any]:
    (shown_in_list,) = await listed(db, [post])
    picture = await media.picture(db, post.cover_id) if post.cover_id else None
    return {
        **shown_in_list,
        "summary": post.summary,
        "body": post.body,
        "cover_id": str(post.cover_id) if post.cover_id else None,
        "cover": _cover(picture),
        "search_title": post.search_title,
        "search_description": post.search_description,
        "allow_comments": post.allow_comments,
        "post_to_community": post.post_to_community,
        "email_subscribers": post.email_subscribers,
        "version": post.version,
        "moves": await moves_of(db, post.id),
        "related": await related_of(db, post.id),
    }


def _like(words: str) -> str:
    escaped = words.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def needs_cover(db: AsyncSession) -> Post | None:
    """The soonest scheduled post with no cover."""
    found: Post | None = await db.scalar(
        select(Post)
        .where(Post.status == lifecycle.SCHEDULED, Post.cover_id.is_(None))
        .order_by(Post.publish_at, Post.id)
        .limit(1)
    )
    return found


async def every(
    db: AsyncSession,
    *,
    q: str | None,
    status: str | None,
    cursor: str | None,
    limit: int = ADMIN_PER_PAGE,
) -> dict[str, Any]:
    """A page of posts, newest edit first, matching `q` in the title and of one state."""
    statement = select(Post)
    if q and q.strip():
        statement = statement.where(Post.title.ilike(_like(q.strip()), escape="\\"))
    if status is not None:
        statement = statement.where(Post.status == status)
    if cursor is not None:
        at, ident = _after(cursor)
        statement = statement.where(sa.tuple_(Post.updated_at, Post.id) < _mark(at, ident))
    rows = list(
        await db.scalars(
            statement.order_by(Post.updated_at.desc(), Post.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    waiting = await needs_cover(db)
    return {
        "items": await listed(db, rows),
        "next_cursor": _cursor_of(rows[-1].updated_at, rows[-1].id) if more else None,
        "needs_cover": (
            None
            if waiting is None or waiting.publish_at is None
            else {
                "id": str(waiting.id),
                "title": waiting.title,
                "publish_at": waiting.publish_at.isoformat(),
            }
        ),
    }


# --- changing --------------------------------------------------------------------------------


def _blank(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


async def _flushed(db: AsyncSession, slug: str) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise _taken(slug) from None


async def create(db: AsyncSession, fields: dict[str, Any], *, by: uuid.UUID | None) -> Post:
    """A new post, a draft. Its slug, left out, is made from its title."""
    title: str = fields["title"]
    if fields.get("slug"):
        slug = fields["slug"]
        await _free(db, slug, None)
    else:
        slug = await unique_slug(db, slug_for(title))
    category = fields.get("category")
    if category is not None:
        await _check_category(db, category)
    cover = _uuid(fields["cover_id"], "cover_id") if fields.get("cover_id") else None
    if cover is not None:
        await _check_cover(db, cover)
    author = _uuid(fields["author_id"], "author_id") if fields.get("author_id") else by
    if author is not None and author != by:
        await _check_author(db, author)
    related = [_uuid(each, "related") for each in fields.get("related") or []]
    await _check_related(db, None, related)
    now = clock.now()
    post = Post(
        id=uuid.uuid4(),
        version=1,
        title=title,
        slug=slug,
        summary=fields.get("summary") or "",
        body=fields.get("body") or "",
        cover_id=cover,
        author_id=author,
        search_title=_blank(fields.get("search_title")),
        search_description=_blank(fields.get("search_description")),
        allow_comments=fields.get("allow_comments", True),
        post_to_community=fields.get("post_to_community", False),
        email_subscribers=fields.get("email_subscribers", False),
        created_at=now,
        updated_at=now,
    )
    db.add(post)
    await _flushed(db, slug)
    # The slug a post holds is its own, live or not: a move there ends.
    await db.execute(delete(SlugMove).where(SlugMove.slug == slug))
    if category is not None:
        await taxonomy.tag(db, CONTENT_TYPE, post.id, VOCABULARY, [category])
    await _place_cover(db, post)
    if related:
        await _replace_related(db, post.id, related)
    audit.record(db, "blog.post.created", actor=by, target=(CONTENT_TYPE, post.id))
    return post


async def _leave(db: AsyncSession, post: Post, old: str) -> None:
    """The live post left `old`: a move from there to wherever it goes."""
    statement = insert(SlugMove).values(slug=old, post_id=post.id, created_at=clock.now())
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[SlugMove.slug],
            set_={
                "post_id": statement.excluded.post_id,
                "created_at": statement.excluded.created_at,
            },
        )
    )


async def change(
    db: AsyncSession,
    post_id: uuid.UUID,
    version: int,
    fields: dict[str, Any],
    *,
    by: uuid.UUID | None,
) -> Post:
    """Saves the fields sent; 409 `blog.changed` on a stale `version`, with the post now."""
    post = await get(db, post_id, lock=True)
    if version != post.version:
        raise Problem(
            "blog.changed",
            409,
            "Someone saved this post since you opened it. Here is how it reads now.",
            extra={"post": await full(db, post)},
        )
    old_slug, old_cover, old_title = post.slug, post.cover_id, post.title
    slug = fields.get("slug") or old_slug  # null leaves it as it is
    if slug != old_slug:
        await _free(db, slug, post.id)
    if "category" in fields and fields["category"] is not None:
        await _check_category(db, fields["category"])
    if fields.get("cover_id") is not None:
        fields["cover_id"] = _uuid(fields["cover_id"], "cover_id")
        if fields["cover_id"] != old_cover:
            await _check_cover(db, fields["cover_id"])
    if fields.get("author_id") is not None:
        fields["author_id"] = _uuid(fields["author_id"], "author_id")
        if fields["author_id"] != post.author_id:
            await _check_author(db, fields["author_id"])
    related = None
    if fields.get("related") is not None:
        related = [_uuid(each, "related") for each in fields["related"]]
        await _check_related(db, post.id, related)
    for name in FIELDS:
        if name not in fields:
            continue
        value = fields[name]
        if name in ("search_title", "search_description"):
            value = _blank(value)
        elif value is None and name not in _CLEARABLE:
            continue  # a field that can't be empty, sent as null, is left as it is
        setattr(post, name, value)
    post.slug = slug
    post.version += 1
    post.updated_at = clock.now()
    await _flushed(db, slug)
    if slug != old_slug:
        # The slug a post holds is its own, live or not: a move there ends;
        # the one it left is a move, while it's live.
        await db.execute(delete(SlugMove).where(SlugMove.slug == slug))
        if post.status == lifecycle.PUBLISHED:
            await _leave(db, post, old_slug)
    if "category" in fields:
        category = fields["category"]
        await taxonomy.tag(db, CONTENT_TYPE, post.id, VOCABULARY, [category] if category else [])
    if post.cover_id != old_cover or post.title != old_title:
        await _place_cover(db, post)
    await _prune_related(db, post.id)
    if related is not None:
        await _replace_related(db, post.id, related)
    if post.status == lifecycle.PUBLISHED:
        await search.index(db, document(post))
    audit.record(
        db,
        "blog.post.changed",
        actor=by,
        target=(CONTENT_TYPE, post.id),
        details={"moved_from": old_slug} if slug != old_slug else None,
    )
    return post


def _at(text: str) -> datetime:
    try:
        at = datetime.fromisoformat(text)
    except ValueError:
        at = None
    if at is None or at.utcoffset() is None:
        raise _invalid(
            "at",
            "kernel.invalid_request",
            "A time with its zone, such as 2026-12-01T09:00:00+00:00.",
        )
    return at


async def publish(
    db: AsyncSession, post_id: uuid.UUID, at: str | None, *, by: uuid.UUID | None
) -> Post:
    """Live now, or at `at` (the kernel's `publish_due` shows it within a minute)."""
    post = await get(db, post_id, lock=True)
    if at is None:
        await lifecycle.publish(db, post)
        audit.record(db, "blog.post.published", actor=by, target=(CONTENT_TYPE, post.id))
    else:
        when = _at(at)
        await lifecycle.schedule(db, post, when)
        audit.record(
            db,
            "blog.post.scheduled",
            actor=by,
            target=(CONTENT_TYPE, post.id),
            details={"at": when.isoformat()},
        )
    return post


async def unpublish(db: AsyncSession, post_id: uuid.UUID, *, by: uuid.UUID | None) -> Post:
    """Back to a draft: its address answers 404, and its moves with it."""
    post = await get(db, post_id, lock=True)
    await lifecycle.unpublish(db, post)
    audit.record(db, "blog.post.unpublished", actor=by, target=(CONTENT_TYPE, post.id))
    return post


async def remove(db: AsyncSession, post_id: uuid.UUID, *, by: uuid.UUID | None) -> None:
    """The post gone, with its moves and its links; its terms, its cover's use
    and its search document with it."""
    post = await get(db, post_id, lock=True)
    slug = post.slug
    await db.delete(post)
    await db.flush()
    await taxonomy.untag_all(db, CONTENT_TYPE, post_id)
    await media.release(db, owner=owner(post_id))
    await search.remove(db, CONTENT_TYPE, post_id)
    audit.record(
        db,
        "blog.post.deleted",
        actor=by,
        target=(CONTENT_TYPE, post_id),
        details={"slug": slug},
    )
