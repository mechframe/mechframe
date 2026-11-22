"""contact: its public page, readable by crawlers that run no JavaScript
(kernel.server_copy, SPEC.md section 9, decision 0041).

/contact answers its heading, Settings' intro line and the topics a message
can be about, with a `ContactPage` JSON-LD, and is listed in the sitemap. A
site whose own /contact page wins the address answers for it instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from contact import service
from kernel import server_copy

PATH = "/contact"
TITLE = "Contact"


class ContactPages(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | server_copy.Moved | None:
        if path != PATH:
            return None
        cfg = await service.current(db)
        site = await server_copy.identity(db)
        return server_copy.Page(
            f"{TITLE} · {site.name}",
            cfg.intro,
            server_copy.article(
                server_copy.h1(TITLE),
                server_copy.p(cfg.intro),
                server_copy.p("What a message can be about:"),
                server_copy.ul(*(topic.label for topic in cfg.topics)),
            ),
            data=(
                {
                    "@context": "https://schema.org",
                    "@type": "ContactPage",
                    "name": TITLE,
                    "description": cfg.intro,
                    "url": server_copy.absolute(PATH, site.url),
                },
            ),
        )

    async def sitemap(self, db: AsyncSession) -> Iterable[server_copy.Entry]:
        cfg = await service.current(db)
        return [server_copy.Entry(PATH, title=TITLE, description=cfg.intro)]


PAGES: server_copy.Pages | None = ContactPages()
