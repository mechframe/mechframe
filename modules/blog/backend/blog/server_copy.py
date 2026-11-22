"""blog: its public pages, readable by crawlers that run no JavaScript
(kernel.server_copy, SPEC.md section 9, decision 0041).

`/blog` answers the newest live posts, each a link with its summary and its
date, and a `Blog` JSON-LD. `/blog/<slug>` answers a live post: its title,
its search words, its cover as `og:image`, its byline, its cleaned HTML under
its own `h1` and a `BlogPosting` JSON-LD; a slug a live post left answers a
301 to it; anything else is a real 404. The words are the API's own
(`service`), so the two never say different things.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blog import service
from blog.models import Post
from kernel import lifecycle, markdown, server_copy

BLOG = "/blog"


def _byline(card: Mapping[str, Any], post: Post) -> server_copy.Html:
    parts: list[Any] = []
    if card["author"]:
        parts.append(f"{card['author']}, ")
    if post.published_at is not None:
        parts.append(server_copy.time(post.published_at, f"{post.published_at:%Y-%m-%d}"))
    parts.append(f", {card['reading_minutes']} min read")
    return server_copy.p(*parts)


def _related(related: list[dict[str, str]]) -> server_copy.Html | str:
    """The live posts a post lists, as its page shows them under its body."""
    if not related:
        return ""
    return server_copy.section(
        server_copy.h2("Related posts"),
        server_copy.ul(
            *(
                server_copy.link(each["title"], f"{service.PREFIX}{each['slug']}")
                for each in related
            )
        ),
    )


class Posts(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | server_copy.Moved | None:
        site = await server_copy.identity(db)
        slug = params.get("slug")
        if slug is None:
            return await self._blog(db, site)
        found = await service.live(db, slug)
        if found is None:
            return None
        if not isinstance(found, Post):
            return server_copy.Moved(await service.moved_to(db, found))
        (card,) = await service.cards(db, [found])
        description = service.description(found)
        url = server_copy.absolute(service.path(found), site.url)
        cover = card["cover"]
        posting: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": found.title,
            "description": description,
            "url": url,
            "mainEntityOfPage": url,
            "datePublished": found.published_at.isoformat() if found.published_at else None,
            "dateModified": found.updated_at.isoformat(),
        }
        if card["author"]:
            posting["author"] = {"@type": "Person", "name": card["author"]}
        if cover is not None:
            posting["image"] = server_copy.absolute(cover["url"], site.url)
        if card["category"] is not None:
            posting["articleSection"] = card["category"]["label"]
        return server_copy.Page(
            service.search_title(found, site.name),
            description,
            server_copy.article(
                server_copy.h1(found.title),
                _byline(card, found),
                server_copy.cleaned(markdown.render(found.body)),
                _related(await service.related_of(db, found.id)),
            ),
            data=(posting,),
            image=cover["url"] if cover is not None else None,
            kind="article",
            published=found.published_at,
            modified=found.updated_at,
        )

    async def _blog(self, db: AsyncSession, site: server_copy.Identity) -> server_copy.Page:
        posts = await service.newest(db)
        cards = await service.cards(db, posts)
        description = f"The newest posts from {site.name}." if site.name else "The newest posts."
        items = [
            server_copy.section(
                server_copy.h2(server_copy.link(card["title"], service.path(post))),
                server_copy.p(card["summary"]) if card["summary"] else "",
                _byline(card, post),
            )
            for post, card in zip(posts, cards, strict=True)
        ]
        return server_copy.Page(
            f"Blog · {site.name}" if site.name else "Blog",
            description,
            (
                [server_copy.h1("Blog"), *items]
                if items
                else [
                    server_copy.h1("Blog"),
                    server_copy.p("Nothing's posted yet."),
                ]
            ),
            data=(
                {
                    "@context": "https://schema.org",
                    "@type": "Blog",
                    "name": f"{site.name} blog" if site.name else "Blog",
                    "url": server_copy.absolute(BLOG, site.url),
                    "blogPost": [
                        {
                            "@type": "BlogPosting",
                            "headline": post.title,
                            "url": server_copy.absolute(service.path(post), site.url),
                            "datePublished": (
                                post.published_at.isoformat() if post.published_at else None
                            ),
                        }
                        for post in posts
                    ],
                },
            ),
            modified=posts[0].updated_at if posts else None,
        )

    async def sitemap(self, db: AsyncSession) -> Iterable[server_copy.Entry]:
        found = list(
            await db.scalars(
                select(Post)
                .where(lifecycle.visible(Post))
                .order_by(Post.published_at.desc(), Post.id.desc())
            )
        )
        site = await server_copy.identity(db)
        newest = max((post.updated_at for post in found), default=None)
        return [
            server_copy.Entry(
                BLOG,
                modified=newest,
                title="Blog",
                description=f"The newest posts from {site.name}." if site.name else None,
            ),
            *(
                server_copy.Entry(
                    service.path(post),
                    modified=post.updated_at,
                    title=post.title,
                    description=service.description(post),
                )
                for post in found
            ),
        ]


PAGES: server_copy.Pages | None = Posts()
