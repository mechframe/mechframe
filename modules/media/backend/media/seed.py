"""media: its seed data (kernel.seed, hook 4, decision 0052): three images
with alt text, made here, so the library and the pickers have something to
show. Each has a fixed id and fixed pixels, so a second run finds them and
changes nothing. Their files are stored with the rows, under those ids: a run
that fails after storing them leaves files a rerun writes again, unreachable
until then. (`ctx.put_image` gives one key per name, where an image here
needs its smaller copies beside it under the library's own keys.)"""

from __future__ import annotations

import asyncio
import io
import uuid

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import seed as seeding
from media import pictures, service
from media.models import MediaImage

_NAMESPACE = uuid.UUID("6f1d3a6e-6b1f-4f45-9a54-3b1f0f0e2c11")
IMAGES = (
    ("seed-sunrise.jpg", (1600, 900), "JPEG", "An orange sunrise over a still lake"),
    ("seed-studio.png", (1200, 800), "PNG", "A mixing desk in a dim recording studio"),
    ("seed-crowd.webp", (960, 640), "WEBP", "Hands raised in a crowd at a concert"),
)


def _made(size: tuple[int, int], kind: str, colour: int) -> bytes:
    across = Image.linear_gradient("L").resize(size)
    down = Image.linear_gradient("L").rotate(90).resize(size)
    flat = Image.new("L", size, colour)
    out = io.BytesIO()
    Image.merge("RGB", (across, flat, down)).save(out, kind)
    return out.getvalue()


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    editor = await ctx.user("editor")
    for number, (name, size, kind, alt) in enumerate(IMAGES):
        image_id = uuid.uuid5(_NAMESPACE, name)
        if await db.scalar(select(MediaImage.id).where(MediaImage.id == image_id)) is not None:
            continue
        data = await asyncio.to_thread(_made, size, kind, 60 + 60 * number)
        prepared = await asyncio.to_thread(pictures.prepare, data)
        await service.put_files(image_id, 1, prepared)
        db.add(
            MediaImage(
                id=image_id,
                version=1,
                file_version=1,
                content_type=prepared.content_type,
                sha256=prepared.sha256,
                width=prepared.width,
                height=prepared.height,
                byte_count=len(prepared.data),
                filename=name,
                alt=alt,
                decorative=False,
                uploaded_by=editor,
                created_at=ctx.now,
                updated_at=ctx.now,
            )
        )
