"""The media library's routes (`dev plans/contracts/media.md` §2), mounted by
the kernel at /api/media behind require_module("media"). All are staff's: the
images themselves are served from the public bucket, not from here."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import answer, get_db, require_permission
from media import pictures, service
from media.schemas import Image, ImageChange, ImagePage

router = APIRouter()

UPLOAD = require_permission("media.image.upload")
MANAGE = require_permission("media.image.manage")


async def _read(file: UploadFile) -> bytes:
    """The upload's bytes, reading one past the limit at most, so a huge one costs nothing more."""
    data = await file.read(pictures.MAX_UPLOAD_BYTES + 1)
    return bytes(data)


async def _shown(db: AsyncSession, image: Any, *, uses: bool = False) -> dict[str, Any]:
    named = await service.names(db, {image.uploaded_by} if image.uploaded_by else set())
    placed = await service.uses_of(db, image.id) if uses else None
    return service.as_answer(image, named, placed)


@router.post(
    "/admin/images",
    response_model=Image,
    status_code=201,
    responses={200: {"model": Image, "description": "The same image, already in the library"}},
)
async def upload_image(
    file: Annotated[UploadFile, File()],
    user: Any = Depends(UPLOAD),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """An image into the library: 201 when it's new, 200 with the one stored when it's there."""
    image, made = await service.upload(db, await _read(file), filename=file.filename, by=user.id)
    shown = await _shown(db, image)
    await db.commit()
    return answer(Image, shown, status_code=201 if made else 200)


@router.get("/admin/images", response_model=ImagePage, dependencies=[Depends(UPLOAD)])
async def list_images(
    cursor: str | None = None,
    q: str | None = None,
    missing_alt: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The library newest first, 40 at a time: by its name or alt text (`q`), or only those without alt text."""
    rows, next_cursor = await service.page(db, cursor=cursor, q=q, only_missing_alt=missing_alt)
    named = await service.names(db, {row.uploaded_by for row in rows if row.uploaded_by})
    return {
        "items": [service.as_answer(row, named) for row in rows],
        "next_cursor": next_cursor,
        "missing_alt": await service.count_missing_alt(db),
    }


@router.get("/admin/images/{image_id}", response_model=Image, dependencies=[Depends(UPLOAD)])
async def read_image(image_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """One image, with where it's placed."""
    return await _shown(db, await service.get(db, image_id), uses=True)


@router.patch("/admin/images/{image_id}", response_model=Image)
async def change_image(
    image_id: uuid.UUID,
    body: ImageChange,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Its alt text, or that it's only decoration; 409 `media.changed` on a stale `version`."""
    image = await service.change(
        db, image_id, version=body.version, alt=body.alt, decorative=body.decorative, by=user.id
    )
    shown = await _shown(db, image, uses=True)
    await db.commit()
    return shown


@router.put("/admin/images/{image_id}/file", response_model=Image)
async def replace_image(
    image_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A new file under the same id: every page that places it shows the new one."""
    image = await service.replace(
        db, image_id, await _read(file), filename=file.filename, by=user.id
    )
    shown = await _shown(db, image, uses=True)
    await db.commit()
    return shown


@router.delete("/admin/images/{image_id}", status_code=204)
async def delete_image(
    image_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone, once nothing places it; 409 `media.in_use` naming the uses until then."""
    await service.delete(db, image_id, by=user.id)
    await db.commit()
    return Response(status_code=204)
