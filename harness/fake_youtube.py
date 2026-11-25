"""A stand-in for YouTube's oEmbed (decision 0073), so no test asks YouTube:
featured's unit tests, its contract suite and the end-to-end server send its
title lookups through `FakeYouTube.transport`.

It answers `GET https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<id>&format=json`
with `{"title": ...}`: the title set for the id in `titles`, else "A video
<id>". An id in `down` answers 404, as YouTube does for a video that's
private or gone, and an id in `slow` answers only after `SLOW_SECONDS`, past
featured's second. Every request is kept in `asked`, so a test sees what was
asked, and that nothing else was.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import httpx

OEMBED = "https://www.youtube.com/oembed"
WATCH = "https://www.youtube.com/watch?v="
#: Longer than featured waits.
SLOW_SECONDS = 1.5


@dataclass
class FakeYouTube:
    titles: dict[str, str] = field(default_factory=dict)
    down: set[str] = field(default_factory=set)
    slow: set[str] = field(default_factory=set)
    asked: list[str] = field(default_factory=list)

    def forget(self) -> None:
        """As new: nothing asked, no titles set, every video up."""
        self.titles.clear()
        self.down.clear()
        self.slow.clear()
        self.asked.clear()

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.asked.append(str(request.url))
        address = str(request.url.copy_with(query=None))
        if request.method != "GET" or address != OEMBED:
            return httpx.Response(404, json={"error": "Not YouTube's oEmbed."})
        query = parse_qs(urlsplit(str(request.url)).query)
        url = (query.get("url") or [""])[0]
        if not url.startswith(WATCH) or (query.get("format") or [""])[0] != "json":
            return httpx.Response(400, text="Bad Request")
        ident = url.removeprefix(WATCH)
        if ident in self.slow:
            await asyncio.sleep(SLOW_SECONDS)
        if ident in self.down:
            return httpx.Response(404, text="Not Found")
        return httpx.Response(
            200,
            json={
                "title": self.titles.get(ident, f"A video {ident}"),
                "author_name": "Vibrant Mindz",
                "type": "video",
                "provider_name": "YouTube",
                "thumbnail_url": f"https://i.ytimg.com/vi/{ident}/hqdefault.jpg",
            },
        )

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)
