"""portfolio's logic (`dev plans/contracts/portfolio.md` §2): add, save,
publish, unpublish and delete a piece; read a live one; list them by page and
by discipline; their disciplines, pictures, videos and artists.

**Who may change a piece** (decision 0074): staff holding
`portfolio.piece.manage` change every piece. Someone holding
`portfolio.piece.add` changes the pieces credited to them, and only while
they hold it, so an artist whose role is taken away keeps no hold on the
pieces still credited to them. The routes say which each person holds; the
checks are made here, on the row as it's locked.

**A save of a live piece changes the site at once:** there is no working
copy. Its search document is written again in the same transaction;
publishing and unpublishing are the kernel's to index.

**Its discipline** is one term of the kernel's `portfolio_discipline` (hook 2).
A save names an existing term: an artist never makes one, staff holding
`kernel.taxonomy.manage` do. **Its picture** is media's image: placing it
records the piece as the image's use (`media.public.use`), and every other
image the piece placed is let go. **Its video** is a YouTube video, read by
`embeds.public.recognise` and kept as its watch address.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from embeds.public import recognise
from media import public as media
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, audit, clock, events, lifecycle, search, taxonomy
from portfolio.events import PieceDeleted
from portfolio.models import MAX_SLUG, MIN_YEAR, SLUG_PATTERN, Piece

CONTENT_TYPE = "portfolio.piece"
VOCABULARY = "portfolio_discipline"
#: The Art page, and a live piece's page: /art/piece/<slug>.
ART = "/art"
PREFIX = "/art/piece/"
#: The public list's page, when the settings aren't read; the admin's.
PER_PAGE = 24
ADMIN_PER_PAGE = 50
#: Who may be credited with a piece: those holding this, through a role.
ADD = "portfolio.piece.add"
MANAGE = "portfolio.piece.manage"
#: The disciplines read in one page of the kernel's terms.
MAX_DISCIPLINES = 500
#: What a save may change, as its body names them.
FIELDS = ("title", "slug", "artist_id", "year", "about", "image_id", "video_url")
#: Fields a save may send as null to clear.
_CLEARABLE = ("artist_id", "year", "video_url")
_SLUG = re.compile(SLUG_PATTERN)

#: The kernel's people and their roles, read for the names artists go by and
#: who may be one (blog's authors).
_people = sa.table(
    "auth_user",
    sa.column("id"),
    sa.column("display_name"),
    sa.column("email"),
    sa.column("status"),
)
_user_roles = sa.table("auth_user_role", sa.column("user_id"), sa.column("role_id"))
_grants = sa.table("auth_role_permission", sa.column("role_id"), sa.column("permission"))

WATCH = "https://www.youtube.com/watch?v="
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}", re.ASCII)
_PLAYER = re.compile(r"/embed/([A-Za-z0-9_-]{11})(?:\?|$)", re.ASCII)
#: The kinds of embeds' YouTube that are one video.
_VIDEOS = frozenset({"video", "short"})


def _not_found() -> Problem:
    return Problem("portfolio.piece_not_found", 404, "There's no such piece.")


def _forbidden() -> Problem:
    return Problem("kernel.forbidden", 403, "You don't have permission to do that.")


def _invalid(field: str, code: str, message: str) -> Problem:
    return Problem(code, 422, message, errors={field: [message]})


def _uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise _invalid(field, "kernel.invalid_request", "That isn't an id.") from None


async def get(db: AsyncSession, piece_id: uuid.UUID, *, lock: bool = False) -> Piece:
    statement = select(Piece).where(Piece.id == piece_id)
    found = await db.scalar(statement.with_for_update() if lock else statement)
    if found is None:
        raise _not_found()
    return found


def path(piece: Piece) -> str:
    return f"{PREFIX}{piece.slug}"


def owner(piece_id: uuid.UUID) -> str:
    """The piece as the media library names a place an image is used."""
    return f"{CONTENT_TYPE}:{piece_id}"


# --- who may ---------------------------------------------------------------------------------


def may_change(piece: Piece, *, by: uuid.UUID, manages: bool, adds: bool) -> None:
    """Returns for staff holding `manage`, and for the piece's own artist while
    they hold `add`; otherwise 403."""
    if manages:
        return
    if adds and piece.artist_id is not None and piece.artist_id == by:
        return
    raise _forbidden()


# --- slugs -----------------------------------------------------------------------------------


def slug_for(text: str) -> str:
    """The slug a title spells: "Don't stop" is `dont-stop`. Empty when it has
    no letters or digits to spell one with (blog's)."""
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
    """`base`, or `base-2`, `base-3` and on, the first no other piece has."""
    base = base or "piece"
    slug, number = base, 2
    while True:
        taken = select(Piece.id).where(Piece.slug == slug)
        if exclude is not None:
            taken = taken.where(Piece.id != exclude)
        if await db.scalar(taken) is None:
            return slug
        suffix = f"-{number}"
        slug = f"{base[: MAX_SLUG - len(suffix)].rstrip('-')}{suffix}"
        number += 1


def _taken(slug: str) -> Problem:
    said = f"Another piece is at {PREFIX}{slug}."
    return Problem(
        "portfolio.slug_taken", 409, f"{said} Choose another address.", errors={"slug": [said]}
    )


async def _free(db: AsyncSession, slug: str, piece_id: uuid.UUID | None) -> None:
    other = await db.scalar(select(Piece.id).where(Piece.slug == slug, Piece.id != piece_id))
    if other is not None:
        raise _taken(slug)


async def _flushed(db: AsyncSession, slug: str) -> None:
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise _taken(slug) from None


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
    """The name a visitor sees: a display name, never an address."""
    return str(row.display_name) if row is not None and row.display_name else None


async def artists(db: AsyncSession) -> list[dict[str, str]]:
    """Every active account that may add pieces, by name: an owner, or anyone
    whose role holds `portfolio.piece.add`."""
    adding_roles = select(_grants.c.role_id).where(_grants.c.permission == ADD)
    may = select(_user_roles.c.user_id).where(
        or_(_user_roles.c.role_id == "owner", _user_roles.c.role_id.in_(adding_roles))
    )
    rows = await db.execute(
        select(_people.c.id, _people.c.display_name, _people.c.email).where(
            _people.c.id.in_(may), _people.c.status == "active"
        )
    )
    found = [{"id": str(row.id), "name": _staff_name(row)} for row in rows]
    return sorted(found, key=lambda each: (each["name"].casefold(), each["id"]))


async def _check_artist(db: AsyncSession, artist_id: uuid.UUID) -> None:
    if str(artist_id) not in {each["id"] for each in await artists(db)}:
        raise _invalid(
            "artist_id",
            "portfolio.not_an_artist",
            "A piece is credited to someone who may add pieces.",
        )


# --- disciplines -----------------------------------------------------------------------------


async def terms(db: AsyncSession) -> list[dict[str, Any]]:
    """The disciplines, in the order staff set: each term's id, slug, label and position."""
    found = taxonomy.vocabulary(VOCABULARY)
    if found is None:
        return []
    out: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        listed = await taxonomy.listed(db, found, cursor=cursor, limit=MAX_DISCIPLINES)
        out.extend(listed["items"])
        cursor = listed["next_cursor"]
        if cursor is None:
            return out


def _no_discipline() -> Problem:
    return _invalid("discipline", "portfolio.unknown_discipline", "There's no such discipline.")


async def _check_discipline(db: AsyncSession, slug: str) -> str:
    """The id of the discipline `slug`, or 422: an artist never makes one."""
    found = next((term for term in await terms(db) if term["slug"] == slug), None)
    if found is None:
        raise _no_discipline()
    return str(found["id"])


async def _file(db: AsyncSession, piece_id: uuid.UUID, slug: str, term_id: str) -> None:
    """Files the piece under `slug`, the term `term_id` that was checked. If
    staff deleted it since, tagging would make it again: 422 instead, and the
    caller's transaction rolls back (blog's)."""
    tagged = await taxonomy.tag(db, CONTENT_TYPE, piece_id, VOCABULARY, [slug])
    if [str(term.id) for term in tagged] != [term_id]:
        raise _no_discipline()


async def disciplines_of(
    db: AsyncSession, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, dict[str, str] | None]:
    """Each piece's discipline, or None."""
    found = await taxonomy.terms_for(db, CONTENT_TYPE, ids)
    out: dict[uuid.UUID, dict[str, str] | None] = {}
    for ident, held in found.items():
        term = next((each for each in held if each.vocabulary == VOCABULARY), None)
        out[ident] = None if term is None else {"slug": term.slug, "label": term.label}
    return out


async def counted(db: AsyncSession, *, live: bool) -> list[dict[str, Any]]:
    """Every discipline with its pieces: the live ones, or all of them."""
    out = []
    for term in await terms(db):
        statement = (
            select(func.count())
            .select_from(Piece)
            .where(Piece.id.in_(taxonomy.tagged(CONTENT_TYPE, VOCABULARY, term["slug"])))
        )
        if live:
            statement = statement.where(lifecycle.visible(Piece))
        out.append({**term, "pieces": int(await db.scalar(statement) or 0)})
    return out


async def live_disciplines(db: AsyncSession) -> list[dict[str, str]]:
    """The disciplines with a live piece, as the public sees them, in staff's order."""
    return [
        {"slug": each["slug"], "label": each["label"]}
        for each in await counted(db, live=True)
        if each["pieces"] > 0
    ]


async def is_discipline(db: AsyncSession, slug: str) -> bool:
    return any(term["slug"] == slug for term in await terms(db))


# --- pictures and videos ---------------------------------------------------------------------


def picture_of(picture: media.Picture | None) -> dict[str, Any] | None:
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


async def pictures_of(db: AsyncSession, pieces: Sequence[Piece]) -> dict[uuid.UUID, media.Picture]:
    return await media.pictures(db, [piece.image_id for piece in pieces])


async def _check_image(db: AsyncSession, image_id: uuid.UUID) -> None:
    if await media.picture(db, image_id) is None:
        raise _invalid(
            "image_id", "portfolio.image_not_found", "The media library has no such image."
        )


async def _place_picture(db: AsyncSession, piece: Piece) -> None:
    """The piece's picture recorded as its use, and any other image it placed let go."""
    await media.use(
        db,
        piece.image_id,
        owner=owner(piece.id),
        label=piece.title,
        link=f"/admin/portfolio?piece={piece.id}",
    )
    await media.release(db, owner=owner(piece.id), keep=[piece.image_id])


def video_id(url: str) -> str | None:
    """The id of the one YouTube video `url` is, or None for any other link (featured's)."""
    found = recognise(url)
    if found is None or found.provider != "youtube" or found.kind not in _VIDEOS:
        return None
    match = _PLAYER.search(found.player)
    return match.group(1) if match else None


def watch(ident: str) -> str:
    if not _VIDEO_ID.fullmatch(ident):
        raise ValueError(f"{ident!r} isn't a YouTube video's id.")
    return WATCH + ident


def _video(url: str) -> tuple[str, str]:
    """The watch address and id of the YouTube video `url` is, or 422."""
    ident = video_id(url)
    if ident is None:
        raise _invalid(
            "video_url",
            "portfolio.not_youtube",
            "A piece's video is a YouTube video's address.",
        )
    return watch(ident), ident


def _check_year(year: int) -> None:
    latest = clock.now().year + 1
    if not MIN_YEAR <= year <= latest:
        raise _invalid("year", "portfolio.bad_year", f"A year from {MIN_YEAR} to {latest}.")


def video_of(piece: Piece) -> dict[str, str] | None:
    if piece.video_url is None or piece.video_id is None:
        return None
    return {"url": piece.video_url, "video_id": piece.video_id}


# --- what the site shows ---------------------------------------------------------------------


async def document(db: AsyncSession, piece: Piece) -> search.Document:
    """The piece as site search finds it: its title, its words, its artist and its discipline."""
    (card,) = await cards(db, [piece])
    discipline = card["discipline"]["label"] if card["discipline"] else ""
    words = " ".join(part for part in (piece.about, card["artist"] or "", discipline) if part)
    return search.Document(CONTENT_TYPE, piece.id, piece.title, words, path(piece))


def line(discipline: dict[str, str] | None, artist: str | None, year: int | None) -> str:
    """ "Graphic design, by petro, 2026", leaving out what it hasn't got."""
    parts = [discipline["label"]] if discipline else []
    if artist:
        parts.append(f"by {artist}")
    if year:
        parts.append(str(year))
    return ", ".join(parts)


async def live(db: AsyncSession, slug: str) -> Piece | None:
    """The live piece at `slug`, else None."""
    if len(slug) > MAX_SLUG or _SLUG.fullmatch(slug) is None:
        return None
    found: Piece | None = await db.scalar(
        select(Piece).where(Piece.slug == slug, lifecycle.visible(Piece))
    )
    return found


async def cards(db: AsyncSession, pieces: Sequence[Piece]) -> list[dict[str, Any]]:
    """Pieces as a grid shows them, in the order given."""
    pictures = await pictures_of(db, pieces)
    disciplines = await disciplines_of(db, [piece.id for piece in pieces])
    people = await _people_of(db, [piece.artist_id for piece in pieces])
    return [
        {
            "id": str(piece.id),
            "title": piece.title,
            "slug": piece.slug,
            "discipline": disciplines.get(piece.id),
            "artist": _public_name(people.get(piece.artist_id) if piece.artist_id else None),
            "year": piece.year,
            "picture": picture_of(pictures.get(piece.image_id)),
            "has_video": piece.video_id is not None,
            "path": path(piece),
        }
        for piece in pieces
    ]


async def shown(db: AsyncSession, piece: Piece) -> dict[str, Any]:
    (card,) = await cards(db, [piece])
    return {**card, "about": piece.about, "video": video_of(piece)}


def _cursor_of(at: datetime, ident: uuid.UUID) -> str:
    return f"{at.isoformat()}~{ident}"


def _mark(at: datetime, ident: uuid.UUID) -> Any:
    """A cursor's place, as a row's (a time, then an id) is compared with it."""
    return sa.tuple_(sa.literal(at, Piece.updated_at.type), sa.literal(ident, Piece.id.type))


def _after(cursor: str) -> tuple[datetime, uuid.UUID]:
    at, mark, ident = cursor.partition("~")
    try:
        when, found = datetime.fromisoformat(at), uuid.UUID(ident)
    except ValueError:
        when = None
    if not mark or when is None or when.utcoffset() is None:
        raise _invalid("cursor", "kernel.invalid_request", "Not a page of these pieces.")
    return when, found


def _no_such_discipline() -> Problem:
    return Problem("portfolio.discipline_not_found", 404, "There's no such discipline.")


def _live(statement: Any) -> Any:
    return statement.where(lifecycle.visible(Piece))


async def page_of(
    db: AsyncSession,
    *,
    discipline: str | None,
    cursor: str | None,
    limit: int = PER_PAGE,
    artist_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """A page of live pieces, newest first, of one discipline when it's named
    (404 for one that isn't), of one artist when one is given."""
    statement = _live(select(Piece))
    if discipline is not None:
        if not await is_discipline(db, discipline):
            raise _no_such_discipline()
        statement = statement.where(
            Piece.id.in_(taxonomy.tagged(CONTENT_TYPE, VOCABULARY, discipline))
        )
    if artist_id is not None:
        statement = statement.where(Piece.artist_id == artist_id)
    if cursor is not None:
        at, ident = _after(cursor)
        statement = statement.where(sa.tuple_(Piece.published_at, Piece.id) < _mark(at, ident))
    rows = list(
        await db.scalars(
            statement.order_by(Piece.published_at.desc(), Piece.id.desc()).limit(limit + 1)
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


async def newest(db: AsyncSession, *, discipline: str | None, limit: int) -> list[Piece]:
    """The newest live pieces, of one discipline when it's named (an existing one)."""
    statement = _live(select(Piece))
    if discipline is not None:
        statement = statement.where(
            Piece.id.in_(taxonomy.tagged(CONTENT_TYPE, VOCABULARY, discipline))
        )
    return list(
        await db.scalars(
            statement.order_by(Piece.published_at.desc(), Piece.id.desc()).limit(limit)
        )
    )


async def live_in_order(db: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Piece]:
    """The live pieces of `ids`, in the order given."""
    if not ids:
        return []
    found = {
        piece.id: piece
        for piece in await db.scalars(_live(select(Piece)).where(Piece.id.in_(list(ids))))
    }
    return [found[each] for each in dict.fromkeys(ids) if each in found]


# --- the admin's reads -----------------------------------------------------------------------


def _when(at: datetime | None) -> str | None:
    return at.isoformat() if at is not None else None


async def full(db: AsyncSession, pieces: Sequence[Piece]) -> list[dict[str, Any]]:
    """Pieces as the admin's grid and editor show them, in the order given."""
    pictures = await pictures_of(db, pieces)
    disciplines = await disciplines_of(db, [piece.id for piece in pieces])
    people = await _people_of(db, [piece.artist_id for piece in pieces])
    out = []
    for piece in pieces:
        person = people.get(piece.artist_id) if piece.artist_id else None
        out.append(
            {
                "id": str(piece.id),
                "title": piece.title,
                "slug": piece.slug,
                "discipline": disciplines.get(piece.id),
                "artist": (
                    None if person is None else {"id": str(person.id), "name": _staff_name(person)}
                ),
                "year": piece.year,
                "about": piece.about,
                "image_id": str(piece.image_id),
                "picture": picture_of(pictures.get(piece.image_id)),
                "video": video_of(piece),
                "status": piece.status,
                "publish_at": _when(piece.publish_at),
                "published_at": _when(piece.published_at),
                "version": piece.version,
                "updated_at": piece.updated_at.isoformat(),
                "path": path(piece) if piece.status == lifecycle.PUBLISHED else None,
            }
        )
    return out


async def one(db: AsyncSession, piece: Piece) -> dict[str, Any]:
    (shown_in_admin,) = await full(db, [piece])
    return shown_in_admin


def _like(words: str) -> str:
    escaped = words.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def every(
    db: AsyncSession,
    *,
    mine: uuid.UUID | None,
    q: str | None,
    discipline: str | None,
    cursor: str | None,
    limit: int = ADMIN_PER_PAGE,
) -> dict[str, Any]:
    """A page of pieces, newest edit first: every piece, or only `mine`'s
    (those credited to them); of one discipline, and matching `q` in the title."""
    statement = select(Piece)
    if mine is not None:
        statement = statement.where(Piece.artist_id == mine)
    if q and q.strip():
        statement = statement.where(Piece.title.ilike(_like(q.strip()), escape="\\"))
    if discipline is not None:
        statement = statement.where(
            Piece.id.in_(taxonomy.tagged(CONTENT_TYPE, VOCABULARY, discipline))
        )
    if cursor is not None:
        at, ident = _after(cursor)
        statement = statement.where(sa.tuple_(Piece.updated_at, Piece.id) < _mark(at, ident))
    rows = list(
        await db.scalars(
            statement.order_by(Piece.updated_at.desc(), Piece.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    rows = rows[:limit]
    no_artist = None
    if mine is None:
        no_artist = int(
            await db.scalar(
                select(func.count()).select_from(Piece).where(Piece.artist_id.is_(None))
            )
            or 0
        )
    return {
        "items": await full(db, rows),
        "next_cursor": _cursor_of(rows[-1].updated_at, rows[-1].id) if more else None,
        "no_artist": no_artist,
    }


# --- changing --------------------------------------------------------------------------------


async def create(
    db: AsyncSession, fields: dict[str, Any], *, by: uuid.UUID, manages: bool
) -> Piece:
    """A new piece, a draft, from the fields sent. Its slug, left out, is made
    from its title. Its artist, left out, is whoever adds it; only staff
    holding `manage` credit it to someone else, or to no one."""
    title: str = fields["title"]
    if "artist_id" in fields:
        artist = _uuid(fields["artist_id"], "artist_id") if fields["artist_id"] else None
    else:
        artist = by
    if artist != by and not manages:
        raise _forbidden()
    if artist is not None and artist != by:
        await _check_artist(db, artist)
    if fields.get("slug"):
        slug = fields["slug"]
        await _free(db, slug, None)
    else:
        slug = await unique_slug(db, slug_for(title))
    discipline: str = fields["discipline"]
    term_id = await _check_discipline(db, discipline)
    image = _uuid(fields["image_id"], "image_id")
    await _check_image(db, image)
    year = fields.get("year")
    if year is not None:
        _check_year(year)
    video_url, video = _video(fields["video_url"]) if fields.get("video_url") else (None, None)
    now = clock.now()
    piece = Piece(
        id=uuid.uuid4(),
        version=1,
        title=title,
        slug=slug,
        artist_id=artist,
        year=year,
        about=fields.get("about") or "",
        image_id=image,
        video_url=video_url,
        video_id=video,
        created_at=now,
        updated_at=now,
    )
    db.add(piece)
    await _flushed(db, slug)
    await _file(db, piece.id, discipline, term_id)
    await _place_picture(db, piece)
    audit.record(db, "portfolio.piece.created", actor=by, target=(CONTENT_TYPE, piece.id))
    return piece


async def change(
    db: AsyncSession,
    piece_id: uuid.UUID,
    version: int,
    fields: dict[str, Any],
    *,
    by: uuid.UUID,
    manages: bool,
    adds: bool,
) -> Piece:
    """Saves the fields sent; 409 `portfolio.changed` on a stale `version`,
    with the piece now. Changing who it's credited to needs `manage`."""
    piece = await get(db, piece_id, lock=True)
    may_change(piece, by=by, manages=manages, adds=adds)
    if version != piece.version:
        raise Problem(
            "portfolio.changed",
            409,
            "Someone saved this piece since you opened it. Here is how it reads now.",
            extra={"piece": await one(db, piece)},
        )
    old_slug, old_image, old_title = piece.slug, piece.image_id, piece.title
    slug = fields.get("slug") or old_slug  # null leaves it as it is
    if slug != old_slug:
        await _free(db, slug, piece.id)
    term_id = None
    if fields.get("discipline") is not None:
        term_id = await _check_discipline(db, fields["discipline"])
    if "artist_id" in fields:
        artist = _uuid(fields["artist_id"], "artist_id") if fields["artist_id"] else None
        if artist != piece.artist_id:
            if not manages:
                raise _forbidden()
            if artist is not None:
                await _check_artist(db, artist)
        fields["artist_id"] = artist
    if fields.get("image_id") is not None:
        fields["image_id"] = _uuid(fields["image_id"], "image_id")
        if fields["image_id"] != old_image:
            await _check_image(db, fields["image_id"])
    if fields.get("year") is not None:
        _check_year(fields["year"])
    changed: list[str] = []
    for name in FIELDS:
        if name not in fields:
            continue
        value = fields[name]
        if value is None and name not in _CLEARABLE:
            continue  # a field that can't be empty, sent as null, is left as it is
        if name == "video_url":
            url, ident = _video(value) if value else (None, None)
            if url != piece.video_url:
                piece.video_url, piece.video_id = url, ident
                changed.append(name)
            continue
        if name == "about":
            value = value or ""
        if getattr(piece, name) != value:
            setattr(piece, name, value)
            changed.append(name)
    piece.slug = slug
    if slug != old_slug and "slug" not in changed:
        changed.append("slug")
    if fields.get("discipline") is not None and term_id is not None:
        await _file(db, piece.id, fields["discipline"], term_id)
        changed.append("discipline")
    piece.version += 1
    piece.updated_at = clock.now()
    await _flushed(db, slug)
    if piece.image_id != old_image or piece.title != old_title:
        await _place_picture(db, piece)
    if piece.status == lifecycle.PUBLISHED:
        await search.index(db, await document(db, piece))
    audit.record(
        db,
        "portfolio.piece.changed",
        actor=by,
        target=(CONTENT_TYPE, piece.id),
        details={"fields": sorted(set(changed))},
    )
    return piece


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
    db: AsyncSession,
    piece_id: uuid.UUID,
    at: str | None,
    *,
    by: uuid.UUID,
    manages: bool,
    adds: bool,
) -> Piece:
    """Live now, or at `at` (the kernel's `publish_due` shows it within a minute)."""
    piece = await get(db, piece_id, lock=True)
    may_change(piece, by=by, manages=manages, adds=adds)
    if at is None:
        await lifecycle.publish(db, piece)
        audit.record(db, "portfolio.piece.published", actor=by, target=(CONTENT_TYPE, piece.id))
    else:
        when = _at(at)
        await lifecycle.schedule(db, piece, when)
        audit.record(
            db,
            "portfolio.piece.scheduled",
            actor=by,
            target=(CONTENT_TYPE, piece.id),
            details={"at": when.isoformat()},
        )
    return piece


async def unpublish(
    db: AsyncSession, piece_id: uuid.UUID, *, by: uuid.UUID, manages: bool, adds: bool
) -> Piece:
    """Back to a draft: its address answers 404."""
    piece = await get(db, piece_id, lock=True)
    may_change(piece, by=by, manages=manages, adds=adds)
    await lifecycle.unpublish(db, piece)
    audit.record(db, "portfolio.piece.unpublished", actor=by, target=(CONTENT_TYPE, piece.id))
    return piece


async def remove(
    db: AsyncSession, piece_id: uuid.UUID, *, by: uuid.UUID, manages: bool, adds: bool
) -> None:
    """The piece gone, with its discipline, its picture's use and its search document."""
    piece = await get(db, piece_id, lock=True)
    may_change(piece, by=by, manages=manages, adds=adds)
    slug = piece.slug
    await db.delete(piece)
    await db.flush()
    await taxonomy.untag_all(db, CONTENT_TYPE, piece_id)
    await media.release(db, owner=owner(piece_id))
    await search.remove(db, CONTENT_TYPE, piece_id)
    await events.emit(db, "portfolio.piece.deleted", PieceDeleted(id=piece_id))
    audit.record(
        db,
        "portfolio.piece.deleted",
        actor=by,
        target=(CONTENT_TYPE, piece_id),
        details={"slug": slug},
    )
