"""pages: its seed data (kernel.seed, hook 4, decision 0052): About and
Credits live in the footer, and a draft, so the list, the menus and the editor
have something to show. Each has a fixed id, so a second run finds them and
changes nothing; an address another page already has is left to it."""

from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle
from kernel import seed as seeding
from pages.models import Page

_NAMESPACE = uuid.UUID("3c1f8e2a-5d47-4b0e-9a6c-7e2b1f0d4a93")
#: Address, title, live in the footer, and the body.
PAGES = (
    (
        "/about",
        "About",
        True,
        "We're a small crew making music, words and pictures.\n\n"
        "## What we do\n\nWe write, record and play live, and we share the work here first.\n\n"
        "## Get in touch\n\nWrite to us from the contact page.",
    ),
    (
        "/credits",
        "Credits",
        True,
        "The people who made this site and what's on it.\n\n"
        "## Music\n\n- Every track: the crew\n\n"
        "## Photographs\n\n- The crew, unless a caption says otherwise",
    ),
    (
        "/press-kit",
        "Press kit",
        False,
        "Everything a writer needs: the crew's story, photos and how to reach us.\n\n"
        "## The short version\n\n[A paragraph about the crew]",
    ),
)


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    editor = await ctx.user("editor")
    for number, (address, title, live, body) in enumerate(PAGES):
        page_id = uuid.uuid5(_NAMESPACE, address)
        taken = await db.scalar(
            select(Page.id).where(or_(Page.id == page_id, Page.address == address))
        )
        if taken is not None:
            continue
        page = Page(
            id=page_id,
            version=1,
            title=title,
            address=address,
            body=body,
            in_header=False,
            in_footer=live,
            menu_order=number,
            updated_by=editor,
            created_at=ctx.now,
            updated_at=ctx.now,
        )
        db.add(page)
        if live:
            page.published_at = ctx.now  # publish keeps it: the seed's own fixed instant
            await lifecycle.publish(db, page)
