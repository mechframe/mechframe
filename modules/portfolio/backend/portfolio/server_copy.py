"""portfolio: its public pages, readable by crawlers that run no JavaScript
(kernel.server_copy, SPEC.md section 9, decision 0041).

`/art` and `/art/<discipline>` answer the newest live pieces, each a link
with its line, the disciplines as links, and a `CollectionPage` JSON-LD; a
discipline that isn't one is a real 404. `/art/piece/<slug>` answers a live
piece: its title, its line, its words, its picture as `og:image`, its video
as a link, and a `VisualArtwork` JSON-LD. The words are the API's own
(`service`), so the two never say different things.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import lifecycle, server_copy, settings
from portfolio import service
from portfolio.models import Piece
from portfolio.schemas import Settings

#: A description's most characters, as search results show them.
MAX_DESCRIPTION = 160


def _excerpt(words: str) -> str:
    flat = " ".join(words.split())
    if len(flat) <= MAX_DESCRIPTION:
        return flat
    cut = flat[: MAX_DESCRIPTION - 1].rsplit(" ", 1)[0]
    return f"{cut}…"


def _byline(card: Mapping[str, Any]) -> str:
    """ "By petro, 2026", leaving out what it hasn't got."""
    parts = []
    if card["artist"]:
        parts.append(f"By {card['artist']}")
    if card["year"]:
        parts.append(str(card["year"]))
    return ", ".join(parts)


def _line(card: Mapping[str, Any]) -> server_copy.Html | str:
    line = service.line(card["discipline"], card["artist"], card["year"])
    return server_copy.p(line) if line else ""


def _paragraphs(words: str) -> list[server_copy.Html]:
    return [server_copy.p(each.strip()) for each in words.split("\n\n") if each.strip()]


async def _settings(db: AsyncSession) -> Settings:
    found = await settings.for_module(db, "portfolio")
    return found if isinstance(found, Settings) else Settings()


class Art(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | server_copy.Moved | None:
        site = await server_copy.identity(db)
        slug = params.get("slug")
        if slug is not None:
            found = await service.live(db, slug)
            return None if found is None else await self._piece(db, site, found)
        discipline = params.get("discipline")
        if discipline is not None and not await service.is_discipline(db, discipline):
            return None
        return await self._list(db, site, discipline)

    async def _piece(
        self, db: AsyncSession, site: server_copy.Identity, piece: Piece
    ) -> server_copy.Page:
        (card,) = await service.cards(db, [piece])
        line = service.line(card["discipline"], card["artist"], piece.year)
        description = _excerpt(piece.about) if piece.about else line or piece.title
        url = server_copy.absolute(service.path(piece), site.url)
        picture = card["picture"]
        artwork: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "VisualArtwork",
            "name": piece.title,
            "url": url,
            "mainEntityOfPage": url,
        }
        if piece.about:
            artwork["description"] = piece.about
        if card["discipline"] is not None:
            artwork["artform"] = card["discipline"]["label"]
        if card["artist"]:
            artwork["creator"] = {"@type": "Person", "name": card["artist"]}
        if piece.year:
            artwork["dateCreated"] = str(piece.year)
        if picture is not None:
            artwork["image"] = server_copy.absolute(picture["url"], site.url)
        named = f"{piece.title}, by {card['artist']}" if card["artist"] else piece.title
        byline = _byline(card)
        video = service.video_of(piece)
        return server_copy.Page(
            f"{named} · {site.name}" if site.name else named,
            description,
            server_copy.article(
                (
                    server_copy.p(
                        server_copy.link(
                            card["discipline"]["label"],
                            f"{service.ART}/{card['discipline']['slug']}",
                        )
                    )
                    if card["discipline"] is not None
                    else ""
                ),
                server_copy.h1(piece.title),
                server_copy.p(byline) if byline else "",
                *_paragraphs(piece.about),
                (
                    server_copy.p(server_copy.link("Watch the video on YouTube", video["url"]))
                    if video is not None
                    else ""
                ),
                server_copy.p(server_copy.link("All the art", service.ART)),
            ),
            data=(artwork,),
            image=picture["url"] if picture is not None else None,
            kind="article",
            published=piece.published_at,
            modified=piece.updated_at,
        )

    async def _list(
        self, db: AsyncSession, site: server_copy.Identity, discipline: str | None
    ) -> server_copy.Page:
        options = await _settings(db)
        pieces = await service.newest(db, discipline=discipline, limit=options.pieces_per_page)
        cards = await service.cards(db, pieces)
        disciplines = await service.live_disciplines(db)
        label = next((each["label"] for each in disciplines if each["slug"] == discipline), None)
        if discipline is not None and label is None:
            label = next(
                (each["label"] for each in await service.terms(db) if each["slug"] == discipline),
                discipline,
            )
        where = f"{service.ART}/{discipline}" if discipline else service.ART
        heading = "Art"
        title = f"{label} · Art" if label else heading
        description = options.lead or (f"Art from {site.name}." if site.name else "Art.")
        if label:
            description = f"{label} from {site.name}." if site.name else f"{label}."
        items = [
            server_copy.section(
                server_copy.h2(server_copy.link(card["title"], card["path"])),
                _line(card),
            )
            for card in cards
        ]
        chips = server_copy.ul(
            server_copy.link("All", service.ART),
            *(
                server_copy.link(each["label"], f"{service.ART}/{each['slug']}")
                for each in disciplines
            ),
        )
        return server_copy.Page(
            f"{title} · {site.name}" if site.name else title,
            description,
            [
                server_copy.h1(heading),
                server_copy.p(options.lead) if options.lead else "",
                chips if disciplines else "",
                *(items or [server_copy.p("Nothing here yet.")]),
            ],
            data=(_collection(site, where, title, cards),),
            modified=max((piece.updated_at for piece in pieces), default=None),
        )

    async def sitemap(self, db: AsyncSession) -> Iterable[server_copy.Entry]:
        found = list(
            await db.scalars(
                select(Piece)
                .where(lifecycle.visible(Piece))
                .order_by(Piece.published_at.desc(), Piece.id.desc())
            )
        )
        site = await server_copy.identity(db)
        newest = max((piece.updated_at for piece in found), default=None)
        return [
            server_copy.Entry(
                service.ART,
                modified=newest,
                title="Art",
                description=f"Art from {site.name}." if site.name else None,
            ),
            *(
                server_copy.Entry(
                    f"{service.ART}/{each['slug']}", modified=newest, title=each["label"]
                )
                for each in await service.live_disciplines(db)
            ),
            *(
                server_copy.Entry(service.path(piece), modified=piece.updated_at, title=piece.title)
                for piece in found
            ),
        ]


def _collection(
    site: server_copy.Identity,
    where: str,
    title: str,
    cards: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "url": server_copy.absolute(where, site.url),
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": number,
                    "url": server_copy.absolute(card["path"], site.url),
                    "name": card["title"],
                }
                for number, card in enumerate(cards, start=1)
            ],
        },
    }


PAGES: server_copy.Pages | None = Art()
