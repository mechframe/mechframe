"""The media library's logic (`dev plans/contracts/media.md`): upload, replace,
change what an image means, delete, list, and where each is placed.

Files go to the kernel's public bucket before the row that names them, so a
row never points at nothing; a failure after they're stored deletes them. A
replace or a delete takes the old files only once its row is committed
(`after_commit`), since until then the old row may still be the one read.
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, audit, storage
from media import pictures
from media.models import MAX_FILENAME, MediaImage, MediaUse

#: A page of the library.
PAGE = 40
_CURSOR = re.compile(r"(\d{1,20})\.([0-9a-f]{32})")
#: The kernel's people, read for the name an image's uploader goes by.
_people = sa.table("auth_user", sa.column("id"), sa.column("display_name"), sa.column("email"))


def now() -> datetime:
    return datetime.now(UTC)


# --- where the files are ---------------------------------------------------------------


def storage_on() -> bool:
    """Whether the public bucket is set, which every upload needs."""
    try:
        storage.public_url("media/x")
    except storage.StorageNotConfigured:
        return False
    return True


def _storage_off() -> Problem:
    return Problem(
        "media.storage_off",
        503,
        "Uploads need the public bucket: set STORAGE_PUBLIC_BUCKET and STORAGE_PUBLIC_URL.",
    )


def file_key(
    image_id: uuid.UUID, file_version: int, content_type: str, width: int | None = None
) -> str:
    extension = pictures.EXTENSIONS[content_type]
    size = "" if width is None else f"-{width}"
    return f"media/{image_id}/{file_version}{size}.{extension}"


def keys(image: MediaImage) -> list[str]:
    """Every file of the image's current version: itself, then each smaller copy."""
    widths: Sequence[int | None] = [None, *pictures.widths_below(image.width)]
    return [file_key(image.id, image.file_version, image.content_type, each) for each in widths]


def _public(key: str) -> str:
    """A file's address in the public bucket; 503 `media.storage_off` while it's off."""
    try:
        return storage.public_url(key)
    except storage.StorageNotConfigured:
        raise _storage_off() from None


def url(image: MediaImage) -> str:
    return _public(file_key(image.id, image.file_version, image.content_type))


def srcset(image: MediaImage) -> str:
    """Each smaller copy below the image's width, then itself, for `<img srcset>`."""
    sized = [
        f"{_public(file_key(image.id, image.file_version, image.content_type, width))} {width}w"
        for width in pictures.widths_below(image.width)
    ]
    return ", ".join([*sized, f"{url(image)} {image.width}w"])


async def put_files(
    image_id: uuid.UUID, file_version: int, prepared: pictures.Prepared
) -> list[str]:
    """The files of a prepared image, stored; their keys."""
    stored: list[str] = []
    try:
        for width, data in [(None, prepared.data), *prepared.sizes]:
            key = file_key(image_id, file_version, prepared.content_type, width)
            await storage.put(key, data, content_type=prepared.content_type, public=True)
            stored.append(key)
    except storage.StorageNotConfigured:
        await _delete(stored)
        raise _storage_off() from None
    except BaseException:
        await _delete(stored)
        raise
    return stored


async def _delete(stored: Sequence[str]) -> None:
    """Files taken out of the bucket, as far as it goes: one that stays is unreachable."""
    for key in stored:
        try:
            await storage.delete(key, public=True)
        except (storage.StorageError, storage.StorageNotConfigured):
            continue


def after_commit(db: AsyncSession, stored: Sequence[str]) -> None:
    """Deletes `stored` once the session's transaction commits."""
    gone = list(stored)
    if not gone:
        return

    def committed(_: Any) -> None:
        asyncio.get_running_loop().create_task(_delete(gone))

    sa.event.listen(db.sync_session, "after_commit", committed, once=True)


# --- reading ---------------------------------------------------------------------------


def clean_filename(name: str | None) -> str:
    """The name an upload came with, as a label: one line, no path, at most 150 characters."""
    text = unicodedata.normalize("NFC", name or "")
    text = re.split(r"[\\/]", text)[-1]
    text = "".join(each for each in text if unicodedata.category(each)[0] != "C").strip()
    return text[:MAX_FILENAME] or "image"


async def get(db: AsyncSession, image_id: uuid.UUID, *, lock: bool = False) -> MediaImage:
    query = select(MediaImage).where(MediaImage.id == image_id)
    found = await db.scalar(query.with_for_update() if lock else query)
    if found is None:
        raise Problem("media.image_not_found", 404, "There's no such image in the library.")
    return found


def missing_alt() -> sa.ColumnElement[bool]:
    """An image a screen reader would say nothing of: no alt text, and not decoration."""
    return sa.and_(
        MediaImage.decorative.is_(False),
        or_(MediaImage.alt.is_(None), func.btrim(MediaImage.alt) == ""),
    )


def _cursor_of(image: MediaImage) -> str:
    micros = int(image.created_at.timestamp() * 1_000_000)
    return f"{micros}.{image.id.hex}"


def _after(cursor: str) -> sa.ColumnElement[bool]:
    matched = _CURSOR.fullmatch(cursor)
    if matched is None:
        raise Problem(
            "kernel.invalid_request",
            422,
            "That page doesn't follow on from a list of the library.",
            errors={"cursor": ["Use the next_cursor a page gave."]},
        )
    at = datetime.fromtimestamp(int(matched[1]) / 1_000_000, UTC)
    after = uuid.UUID(hex=matched[2])
    return or_(
        MediaImage.created_at < at, sa.and_(MediaImage.created_at == at, MediaImage.id < after)
    )


async def page(
    db: AsyncSession, *, cursor: str | None, q: str | None, only_missing_alt: bool
) -> tuple[list[MediaImage], str | None]:
    """The library newest first, `PAGE` at a time."""
    query = select(MediaImage)
    if cursor:
        query = query.where(_after(cursor))
    if q and q.strip():
        like = f"%{q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
        query = query.where(or_(MediaImage.filename.ilike(like), MediaImage.alt.ilike(like)))
    if only_missing_alt:
        query = query.where(missing_alt())
    rows = list(
        await db.scalars(
            query.order_by(MediaImage.created_at.desc(), MediaImage.id.desc()).limit(PAGE + 1)
        )
    )
    more = len(rows) > PAGE
    rows = rows[:PAGE]
    return rows, _cursor_of(rows[-1]) if more and rows else None


async def count_missing_alt(db: AsyncSession) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(MediaImage).where(missing_alt())) or 0
    )


async def uses_of(db: AsyncSession, image_id: uuid.UUID) -> list[MediaUse]:
    return list(
        await db.scalars(
            select(MediaUse).where(MediaUse.image_id == image_id).order_by(MediaUse.created_at)
        )
    )


async def names(db: AsyncSession, people: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The name each uploader goes by: their display name, else their address."""
    if not people:
        return {}
    rows = await db.execute(
        select(_people.c.id, _people.c.display_name, _people.c.email).where(
            _people.c.id.in_(people)
        )
    )
    return {row.id: (row.display_name or row.email) for row in rows}


def as_answer(
    image: MediaImage, named: dict[uuid.UUID, str], uses: list[MediaUse] | None = None
) -> dict[str, Any]:
    shown: dict[str, Any] = {
        "id": str(image.id),
        "url": url(image),
        "srcset": srcset(image),
        "width": image.width,
        "height": image.height,
        "bytes": image.byte_count,
        "content_type": image.content_type,
        "filename": image.filename,
        "alt": image.alt,
        "decorative": image.decorative,
        "uploaded_by": named.get(image.uploaded_by) if image.uploaded_by else None,
        "created_at": image.created_at.isoformat(),
        "version": image.version,
    }
    if uses is not None:
        shown["uses"] = [{"label": each.label, "link": each.link} for each in uses]
    return shown


# --- changing --------------------------------------------------------------------------


async def _prepared(data: bytes) -> pictures.Prepared:
    try:
        return await asyncio.to_thread(pictures.prepare, data)
    except pictures.Refused as refused:
        raise Problem(refused.code, refused.status, str(refused)) from None


async def _by_sha(db: AsyncSession, sha256: str) -> MediaImage | None:
    found: MediaImage | None = await db.scalar(
        select(MediaImage).where(MediaImage.sha256 == sha256)
    )
    return found


async def upload(
    db: AsyncSession, data: bytes, *, filename: str | None, by: uuid.UUID | None
) -> tuple[MediaImage, bool]:
    """The image for an upload, stored now (`True`) or found already stored (`False`)."""
    if not storage_on():
        raise _storage_off()
    prepared = await _prepared(data)
    found = await _by_sha(db, prepared.sha256)
    if found is not None:
        return found, False
    image_id = uuid.uuid4()
    stored = await put_files(image_id, 1, prepared)
    at = now()
    image = MediaImage(
        id=image_id,
        version=1,
        file_version=1,
        content_type=prepared.content_type,
        sha256=prepared.sha256,
        width=prepared.width,
        height=prepared.height,
        byte_count=len(prepared.data),
        filename=clean_filename(filename),
        alt=None,
        decorative=False,
        uploaded_by=by,
        created_at=at,
        updated_at=at,
    )
    try:
        async with db.begin_nested():
            db.add(image)
    except IntegrityError:
        # The same image, uploaded at once by someone else: theirs is the one kept.
        await _delete(stored)
        found = await _by_sha(db, prepared.sha256)
        if found is None:
            raise
        return found, False
    except BaseException:
        await _delete(stored)
        raise
    audit.record(
        db,
        "media.image.uploaded",
        actor=by,
        target=("media.image", image.id),
        details={"filename": image.filename},
    )
    return image, True


async def replace(
    db: AsyncSession,
    image_id: uuid.UUID,
    data: bytes,
    *,
    filename: str | None,
    by: uuid.UUID | None,
) -> MediaImage:
    """The image with a new file under the same id: every page that places it shows it."""
    if not storage_on():
        raise _storage_off()
    prepared = await _prepared(data)
    image = await get(db, image_id, lock=True)
    if prepared.sha256 == image.sha256:
        return image
    other = await _by_sha(db, prepared.sha256)
    if other is not None:
        raise Problem(
            "media.already_in_library",
            409,
            "That image is already in the library: place that one instead.",
            extra={"id": str(other.id)},
        )
    old = keys(image)
    stored = await put_files(image.id, image.file_version + 1, prepared)
    try:
        image.file_version += 1
        image.version += 1
        image.content_type = prepared.content_type
        image.sha256 = prepared.sha256
        image.width = prepared.width
        image.height = prepared.height
        image.byte_count = len(prepared.data)
        image.filename = clean_filename(filename)
        image.updated_at = now()
        await db.flush()
    except BaseException:
        await _delete(stored)
        raise
    audit.record(db, "media.image.replaced", actor=by, target=("media.image", image.id))
    after_commit(db, old)
    return image


_LINE_BREAKS = (chr(0x85), chr(0x2028), chr(0x2029))


async def change(
    db: AsyncSession,
    image_id: uuid.UUID,
    *,
    version: int,
    alt: str | None,
    decorative: bool,
    by: uuid.UUID | None,
) -> MediaImage:
    """What an image means: its alt text, or that it's only decoration."""
    image = await get(db, image_id, lock=True)
    if version != image.version:
        raise Problem(
            "media.changed",
            409,
            "Someone changed this image since you opened it. Here is how it reads now.",
            extra={"version": image.version, "alt": image.alt, "decorative": image.decorative},
        )
    said = (alt or "").strip()
    if any(unicodedata.category(each) == "Cc" or each in _LINE_BREAKS for each in said):
        raise Problem(
            "kernel.invalid_request",
            422,
            "Alt text is one line.",
            errors={"alt": ["Alt text is one line, with no line breaks or control characters."]},
        )
    if decorative and said:
        raise Problem(
            "kernel.invalid_request",
            422,
            "A picture that's only decoration has no alt text.",
            errors={"alt": ["Leave it empty, or untick Only decoration."]},
        )
    image.alt = said or None
    image.decorative = decorative
    image.version += 1
    image.updated_at = now()
    await db.flush()
    audit.record(
        db,
        "media.image.described",
        actor=by,
        target=("media.image", image.id),
        details={"decorative": decorative},
    )
    return image


async def delete(db: AsyncSession, image_id: uuid.UUID, *, by: uuid.UUID | None) -> None:
    """The image gone, once nothing places it; its files after the commit."""
    image = await get(db, image_id, lock=True)
    uses = await uses_of(db, image_id)
    if uses:
        raise Problem(
            "media.in_use",
            409,
            "That image is in use. Take it off those pages first.",
            extra={"uses": [{"label": each.label, "link": each.link} for each in uses]},
        )
    gone = keys(image)
    await db.delete(image)
    await db.flush()
    audit.record(db, "media.image.deleted", actor=by, target=("media.image", image_id))
    after_commit(db, gone)
