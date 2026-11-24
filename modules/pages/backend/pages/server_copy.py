"""pages: its public pages, readable by crawlers that run no JavaScript
(kernel.server_copy, SPEC.md section 9, decision 0041).

module.json's `routes.public` is `/:address`, the least fixed pattern there
is, so any other module's or the site's page wins its address. Each live page
answers its title, search words, cleaned HTML under its own `h1` and the day
it last changed, and a `WebPage` JSON-LD; an address a live page left answers a 301 to it; anything
else is a real 404. The words are the API's own (`service`), so the two never
say different things.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle, markdown, server_copy
from pages import service
from pages.models import Page


class LivePages(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | server_copy.Moved | None:
        found = await service.live(db, path)
        if found is None:
            return None
        if not isinstance(found, Page):
            return server_copy.Moved(await service.moved_to(db, found))
        site = await server_copy.identity(db)
        description = service.description(found)
        return server_copy.Page(
            service.search_title(found, site.name),
            description,
            server_copy.article(
                server_copy.h1(found.title),
                # When it last changed, as the page draws it (pages 0.1.1, VM Website's ask).
                server_copy.p(
                    "Updated ",
                    server_copy.time(found.updated_at, f"{found.updated_at:%Y-%m-%d}"),
                ),
                server_copy.cleaned(markdown.render(found.body)),
            ),
            data=(
                {
                    "@context": "https://schema.org",
                    "@type": "WebPage",
                    "name": found.title,
                    "description": description,
                    "url": server_copy.absolute(found.address, site.url),
                    "dateModified": found.updated_at.isoformat(),
                },
            ),
            modified=found.updated_at,
        )

    async def sitemap(self, db: AsyncSession) -> Iterable[server_copy.Entry]:
        found = await db.scalars(select(Page).where(lifecycle.visible(Page)).order_by(Page.address))
        return [
            server_copy.Entry(
                page.address,
                modified=page.updated_at,
                title=page.title,
                description=service.description(page),
            )
            for page in found
        ]


PAGES: server_copy.Pages | None = LivePages()
