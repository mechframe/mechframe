"""What other modules may call (SPEC 7), when they list `media` in `requires`.

A module that places an image keeps its id, reads it back with `picture` to
draw it, and records the place with `use`, in its own transaction, so the
library shows where each image is and keeps it from being deleted while it's
placed. `release` takes every image off one thing, such as a post deleted.
`store` takes another module's own image, such as blog's generated cover, as
an upload is taken, with its alt text (media 0.1.4, decision 0065).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from media import service
from media.models import MAX_ALT, MAX_LABEL, MAX_LINK, MAX_OWNER, MediaImage, MediaUse


@dataclass(frozen=True)
class Picture:
    """An image as a page draws it."""

    id: uuid.UUID
    url: str
    srcset: str
    width: int
    height: int
    #: Empty for a picture that's only decoration; None while nobody has written any.
    alt: str | None
    decorative: bool


def _picture(image: MediaImage) -> Picture:
    return Picture(
        id=image.id,
        url=service.url(image),
        srcset=service.srcset(image),
        width=image.width,
        height=image.height,
        alt="" if image.decorative else image.alt,
        decorative=image.decorative,
    )


async def picture(db: AsyncSession, image_id: uuid.UUID) -> Picture | None:
    """The image to draw, or None when the library has no such image."""
    found = await db.scalar(select(MediaImage).where(MediaImage.id == image_id))
    return None if found is None else _picture(found)


async def pictures(db: AsyncSession, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Picture]:
    """Each image the library has of `ids`, by id."""
    wanted = set(ids)
    if not wanted:
        return {}
    rows = await db.scalars(select(MediaImage).where(MediaImage.id.in_(wanted)))
    return {row.id: _picture(row) for row in rows}


async def store(
    db: AsyncSession, data: bytes, *, filename: str, alt: str, by: uuid.UUID | None
) -> Picture:
    """Another module's image, through an upload's checks and stored with
    `alt`. The same bytes again answer the image already kept, its alt as it
    was. 503 `media.storage_off` while storage is off, as an upload."""
    image, made = await service.upload(db, data, filename=filename, by=by)
    if made:
        image.alt = alt.strip()[:MAX_ALT] or None
        await db.flush()
    return _picture(image)


async def use(db: AsyncSession, image_id: uuid.UUID, *, owner: str, label: str, link: str) -> None:
    """Records that `owner` (`<module>.<type>:<id>`) places the image, named `label`, at `link`.
    Again for the same pair, it updates the label and the link."""
    if not (0 < len(owner) <= MAX_OWNER and ":" in owner):
        raise ValueError(f"{owner!r} isn't a use's owner: <module>.<type>:<id>.")
    row = {
        "id": uuid.uuid4(),
        "image_id": image_id,
        "owner": owner,
        "label": label[:MAX_LABEL],
        "link": link[:MAX_LINK],
        "created_at": service.now(),
    }
    statement = insert(MediaUse).values(**row)
    await db.execute(
        statement.on_conflict_do_update(
            constraint="uq_media_use_image_id_owner",
            set_={"label": statement.excluded.label, "link": statement.excluded.link},
        )
    )


async def release(db: AsyncSession, *, owner: str, keep: Iterable[uuid.UUID] = ()) -> None:
    """Takes `owner` off every image it placed, but those in `keep`."""
    kept = set(keep)
    statement = delete(MediaUse).where(MediaUse.owner == owner)
    if kept:
        statement = statement.where(MediaUse.image_id.not_in(kept))
    await db.execute(statement)
