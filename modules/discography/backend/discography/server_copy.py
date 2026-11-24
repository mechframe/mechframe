"""discography: its public pages, readable by crawlers that run no JavaScript
(kernel.server_copy, SPEC.md section 9).

`/music` answers the live releases and an `ItemList` of `MusicAlbum`s.
`/music/<release>` answers the release's lines, tracklist and credits under
its own `h1`, its front cover as `og:image` and a `MusicAlbum` JSON-LD whose
`track` lists `MusicRecording`s. `/music/<release>/<track>` answers the
track, its credits and, while the site shows them, its lyrics, with a
`MusicRecording` JSON-LD. No stream address goes to crawlers. An address a
live release or track left answers a 301; anything else is a real 404.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from discography import service
from discography.models import Release
from kernel import lifecycle, server_copy

MUSIC = "/music"
RELEASE_TYPES = {
    "album": "https://schema.org/AlbumRelease",
    "ep": "https://schema.org/EPRelease",
    "single": "https://schema.org/SingleRelease",
}
KIND_WORDS = {"album": "Album", "ep": "EP", "single": "Single"}


def iso_duration(ms: int | None) -> str | None:
    """ISO 8601, as schema.org reads a duration: PT3M41S."""
    if ms is None:
        return None
    seconds = round(ms / 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return (
        "PT" + (f"{hours}H" if hours else "") + (f"{minutes}M" if minutes else "") + f"{seconds}S"
    )


def _clock(ms: int | None) -> str:
    if ms is None:
        return ""
    seconds = round(ms / 1000)
    return f" ({seconds // 60}:{seconds % 60:02d})"


def _description(card: Mapping[str, Any]) -> str:
    said = str(card["summary"] or card["credit_line"])
    if said:
        return said
    kind = KIND_WORDS[card["kind"]]
    return f"{kind} by {card['artist_line']}." if card["artist_line"] else f"{kind}."


def _album(card: Mapping[str, Any], url: str, site_url: str) -> dict[str, Any]:
    album: dict[str, Any] = {
        "@type": "MusicAlbum",
        "name": card["title"],
        "url": url,
        "albumReleaseType": RELEASE_TYPES[card["kind"]],
        "numTracks": card["track_count"],
    }
    if card["artist_line"]:
        album["byArtist"] = {"@type": "MusicGroup", "name": card["artist_line"]}
    if card["year"]:
        album["datePublished"] = str(card["year"])
    if card["cover"] is not None:
        album["image"] = server_copy.absolute(card["cover"]["url"], site_url)
    return album


def _credits(credits: list[dict[str, str]]) -> server_copy.Html | str:
    if not credits:
        return ""
    return server_copy.section(
        server_copy.h2("Credits"),
        server_copy.ul(*(f"{each['role']}: {each['name']}" for each in credits)),
    )


class Music(server_copy.Pages):
    async def page(
        self, db: AsyncSession, path: str, params: Mapping[str, str]
    ) -> server_copy.Page | server_copy.Moved | None:
        site = await server_copy.identity(db)
        slug, track_slug = params.get("release"), params.get("track")
        if slug is None:
            return await self._music(db, site)
        if track_slug is not None:
            return await self._track(db, site, slug, track_slug)
        found = await service.live(db, slug)
        if found is None:
            return None
        if isinstance(found, str):
            return server_copy.Moved(found)
        shown = await service.shown(db, found)
        url = server_copy.absolute(shown["path"], site.url)
        album = {"@context": "https://schema.org", **_album(shown, url, site.url)}
        album["track"] = {
            "@type": "ItemList",
            "numberOfItems": len(shown["tracks"]),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": line["number"],
                    "item": {
                        "@type": "MusicRecording",
                        "name": line["title"],
                        "url": server_copy.absolute(line["path"], site.url),
                        **(
                            {"duration": iso_duration(line["duration_ms"])}
                            if line["duration_ms"]
                            else {}
                        ),
                    },
                }
                for line in shown["tracks"]
            ],
        }
        lines = [
            each for each in (shown["artist_line"], shown["credit_line"], shown["summary"]) if each
        ]
        return server_copy.Page(
            f"{found.title} · {site.name}" if site.name else found.title,
            _description(shown),
            server_copy.article(
                server_copy.h1(found.title),
                *(server_copy.p(each) for each in lines),
                (
                    server_copy.section(
                        server_copy.h2("Tracks"),
                        server_copy.ul(
                            *(
                                server_copy.link(
                                    f"{line['title']}{_clock(line['duration_ms'])}", line["path"]
                                )
                                for line in shown["tracks"]
                            )
                        ),
                    )
                    if shown["tracks"]
                    else server_copy.p("The tracklist is to come.")
                ),
                _credits(shown["credits"]),
                (
                    server_copy.section(
                        server_copy.h2("Listen on"),
                        server_copy.ul(
                            *(
                                server_copy.link(each["label"], each["url"])
                                for each in shown["links"]
                            )
                        ),
                    )
                    if shown["links"]
                    else ""
                ),
            ),
            data=(album,),
            image=shown["cover"]["url"] if shown["cover"] is not None else None,
            published=found.published_at,
            modified=found.updated_at,
        )

    async def _track(
        self, db: AsyncSession, site: server_copy.Identity, slug: str, track_slug: str
    ) -> server_copy.Page | server_copy.Moved | None:
        found = await service.live_track(db, slug, track_slug)
        if found is None:
            return None
        if isinstance(found, str):
            return server_copy.Moved(found)
        release, track, number = found
        shown = await service.track_shown(db, release, track, number)
        url = server_copy.absolute(shown["path"], site.url)
        recording: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": "MusicRecording",
            "name": track.title,
            "url": url,
            "position": number,
            "inAlbum": {
                "@type": "MusicAlbum",
                "name": release.title,
                "url": server_copy.absolute(service.release_path(release), site.url),
            },
        }
        if shown["duration_ms"]:
            recording["duration"] = iso_duration(shown["duration_ms"])
        if release.artist_line:
            recording["byArtist"] = {"@type": "MusicGroup", "name": release.artist_line}
        lyrics = shown["lyrics"]
        said = f"{track.title}, track {number} of {release.title}"
        description = f"{said}, by {release.artist_line}." if release.artist_line else f"{said}."
        return server_copy.Page(
            f"{track.title} · {release.title}",
            description,
            server_copy.article(
                server_copy.h1(track.title),
                server_copy.p(server_copy.link(release.title, service.release_path(release))),
                _credits(shown["credits"]),
                (
                    server_copy.section(
                        server_copy.h2("Lyrics"),
                        *(server_copy.p(each) for each in lyrics.split("\n\n")),
                    )
                    if lyrics
                    else ""
                ),
            ),
            data=(recording,),
            image=shown["cover"]["url"] if shown["cover"] is not None else None,
            published=release.published_at,
            modified=track.updated_at,
        )

    async def _music(self, db: AsyncSession, site: server_copy.Identity) -> server_copy.Page:
        releases = await service.newest(db, 100)
        cards = await service.cards(db, releases)
        description = f"Music from {site.name}." if site.name else "Music."
        items = [
            server_copy.section(
                server_copy.h2(server_copy.link(card["title"], card["path"])),
                server_copy.p(
                    ", ".join(
                        str(each)
                        for each in (KIND_WORDS[card["kind"]], card["year"], card["artist_line"])
                        if each
                    )
                ),
                server_copy.p(card["summary"]) if card["summary"] else "",
            )
            for card in cards
        ]
        return server_copy.Page(
            f"Music · {site.name}" if site.name else "Music",
            description,
            [server_copy.h1("Music"), *(items or [server_copy.p("No releases yet.")])],
            data=(
                {
                    "@context": "https://schema.org",
                    "@type": "ItemList",
                    "name": "Music",
                    "url": server_copy.absolute(MUSIC, site.url),
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": position,
                            "item": _album(
                                card, server_copy.absolute(card["path"], site.url), site.url
                            ),
                        }
                        for position, card in enumerate(cards, start=1)
                    ],
                },
            ),
            modified=releases[0].updated_at if releases else None,
        )

    async def sitemap(self, db: AsyncSession) -> Iterable[server_copy.Entry]:
        found = list(
            await db.scalars(
                select(Release)
                .where(lifecycle.visible(Release))
                .order_by(Release.published_at.desc(), Release.id.desc())
            )
        )
        tracks = await service.tracks_of(db, [release.id for release in found])
        entries = [
            server_copy.Entry(
                MUSIC,
                modified=max((release.updated_at for release in found), default=None),
                title="Music",
            )
        ]
        for release in found:
            entries.append(
                server_copy.Entry(
                    service.release_path(release), modified=release.updated_at, title=release.title
                )
            )
            entries.extend(
                server_copy.Entry(
                    service.track_path(release, track), modified=track.updated_at, title=track.title
                )
                for track in tracks[release.id]
                if service.plays_from(track)
            )
        return entries


PAGES: server_copy.Pages | None = Music()
