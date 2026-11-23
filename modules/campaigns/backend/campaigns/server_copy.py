"""campaigns: its public pages for crawlers that run no JavaScript
(kernel.server_copy, SPEC.md section 9, decision 0041).

/newsletter/confirm and /newsletter/unsubscribe each say what their link is
for, answered `noindex`: they're a person's own links, never search results,
and never in the sitemap. Neither reads its token: a link scanner opening one
changes nothing, and the server copy shows nobody's address.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import render
from kernel import server_copy

PAGES_WORDS = {
    render.CONFIRM_PAGE: (
        "Confirm your subscription",
        "Press Confirm to start getting the site's news and releases by email.",
    ),
    render.UNSUBSCRIBE_PAGE: (
        "Unsubscribe from the newsletter",
        "Press Unsubscribe and the site won't email you its news again.",
    ),
}


class NewsletterPages(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | server_copy.Moved | None:
        words = PAGES_WORDS.get(path)
        if words is None:
            return None
        title, line = words
        site = await server_copy.identity(db)
        return server_copy.Page(
            f"{title} · {site.name}",
            line,
            server_copy.article(server_copy.h1(title), server_copy.p(line)),
            noindex=True,
        )

    async def sitemap(self, db: AsyncSession) -> Iterable[server_copy.Entry]:
        return []


PAGES: server_copy.Pages | None = NewsletterPages()
