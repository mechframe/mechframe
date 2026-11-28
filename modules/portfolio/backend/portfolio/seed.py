"""portfolio: its seed data (kernel.seed, hook 4, decision 0052): the four
disciplines, Paintings, Graphic design, Animation and Video; and, while the
media library can store images, three live pieces and a draft, each with a
picture made here and kept through `media.public.store` (the same bytes
again answer the image already kept). Each piece has a fixed id, so a second
run finds them and changes nothing; a slug another piece has is left to it."""

from __future__ import annotations

import asyncio
import io
import uuid

from media import public as media
from PIL import Image
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle, taxonomy
from kernel import seed as seeding
from portfolio import service
from portfolio.models import Piece

_NAMESPACE = uuid.UUID("3b8f0d52-7a1e-4c69-9e2d-5f4a0b6c8d17")
#: Slug and label, in the Art page's order.
DISCIPLINES = (
    ("paintings", "Paintings"),
    ("graphic-design", "Graphic design"),
    ("animation", "Animation"),
    ("video", "Video"),
)
LIVE, DRAFT = "live", "draft"
#: Slug, title, discipline, year, state, the words, and the picture's colours and alt text.
PIECES = (
    (
        "harbour-at-dusk",
        "Harbour at dusk",
        "paintings",
        2025,
        LIVE,
        "Oil on canvas, painted from the sea wall over three evenings.",
        ((32, 48, 96), (240, 128, 64)),
        "Boats in a harbour under an orange and blue evening sky",
    ),
    (
        "sunburst-sticker",
        "Sunburst sticker",
        "graphic-design",
        2026,
        LIVE,
        "A sticker for the collective's shows.",
        ((250, 200, 40), (200, 40, 90)),
        "A yellow and red sunburst with the collective's initials",
    ),
    (
        "night-shift-poster",
        "Night shift poster",
        "graphic-design",
        2024,
        LIVE,
        "",
        ((20, 20, 30), (90, 200, 220)),
        "A dark poster with a teal city skyline",
    ),
    (
        "study-in-blue",
        "Study in blue",
        "paintings",
        None,
        DRAFT,
        "Still drying.",
        ((10, 30, 120), (120, 170, 240)),
        "Blue brush strokes on a white ground",
    ),
)


def _made(start: tuple[int, int, int], end: tuple[int, int, int]) -> bytes:
    """A 1200 by 900 PNG fading from `start` to `end`, top to bottom: fixed pixels."""
    width, height = 1200, 900
    fade = Image.linear_gradient("L").resize((width, height))
    first = Image.new("RGB", (width, height), start)
    second = Image.new("RGB", (width, height), end)
    out = io.BytesIO()
    Image.composite(second, first, fade).save(out, "PNG")
    return out.getvalue()


async def _disciplines(db: AsyncSession, actor: uuid.UUID) -> None:
    found = taxonomy.vocabulary(service.VOCABULARY)
    if found is None:
        return
    have = {term["slug"] for term in await service.terms(db)}
    for position, (slug, label) in enumerate(DISCIPLINES):
        if slug not in have:
            await taxonomy.create(
                db, found, slug=slug, label=label, parent_id=None, position=position, actor=actor
            )


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    editor = await ctx.user("editor")
    await _disciplines(db, editor)
    if not media.storage_on():
        return
    for slug, title, discipline, year, state, about, colours, alt in PIECES:
        piece_id = uuid.uuid5(_NAMESPACE, slug)
        taken = await db.scalar(
            select(Piece.id).where(or_(Piece.id == piece_id, Piece.slug == slug))
        )
        if taken is not None:
            continue
        data = await asyncio.to_thread(_made, *colours)
        picture = await media.store(db, data, filename=f"{slug}.png", alt=alt, by=editor)
        piece = Piece(
            id=piece_id,
            version=1,
            title=title,
            slug=slug,
            artist_id=editor,
            year=year,
            about=about,
            image_id=picture.id,
            created_at=ctx.now,
            updated_at=ctx.now,
        )
        db.add(piece)
        await db.flush()
        await taxonomy.tag(db, service.CONTENT_TYPE, piece.id, service.VOCABULARY, [discipline])
        await media.use(
            db,
            picture.id,
            owner=service.owner(piece.id),
            label=title,
            link=f"/admin/portfolio?piece={piece.id}",
        )
        if state == LIVE:
            piece.published_at = ctx.now  # publish keeps it: the seed's own fixed instant
            await lifecycle.publish(db, piece)
