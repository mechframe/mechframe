"""YouTube's links (`dev plans/contracts/featured.md` §2, "YouTube's titles").

A link is a video when `embeds.public.recognise` reads it as YouTube's video
or Short, and it's kept as the video's watch address, built from its id: so
what a link carried besides (a start time, a playlist, someone's tracking) is
dropped, and no address someone typed is ever fetched.

A title is YouTube's oEmbed answer for that watch address, asked of
`https://www.youtube.com/oembed` and nothing else. The links are looked up at
once, each given a second, so the route answers within about one (SPEC 7). A
lookup that fails or takes too long leaves the title None, for staff to type.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterable
from dataclasses import dataclass

import httpx
from embeds.public import recognise

OEMBED = "https://www.youtube.com/oembed"
WATCH = "https://www.youtube.com/watch?v="
TIMEOUT_SECONDS = 1.0
USER_AGENT = "mechframe (website admin)"
#: An oEmbed answer's largest body worth reading.
MAX_ANSWER_BYTES = 64 * 1024

_ID = re.compile(r"[A-Za-z0-9_-]{11}", re.ASCII)
_PLAYER = re.compile(r"/embed/([A-Za-z0-9_-]{11})(?:\?|$)", re.ASCII)
#: The kinds of embeds' YouTube that are one video.
_VIDEOS = frozenset({"video", "short"})


@dataclass
class _Installed:
    #: Tests and the harness hand in an httpx transport (`use_transport`); None is the real network.
    transport: httpx.AsyncBaseTransport | None = None


_installed = _Installed()


def use_transport(transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncBaseTransport | None:
    """Every lookup goes through `transport` from now on: a fake YouTube, for the
    tests and the harness. Answers the one it replaces."""
    before = _installed.transport
    _installed.transport = transport
    return before


def video_id(url: str) -> str | None:
    """The id of the one YouTube video `url` is, or None for any other link."""
    found = recognise(url)
    if found is None or found.provider != "youtube" or found.kind not in _VIDEOS:
        return None
    match = _PLAYER.search(found.player)
    return match.group(1) if match else None


def watch(ident: str) -> str:
    """The video's watch address: what featured keeps and asks YouTube about."""
    if not _ID.fullmatch(ident):
        raise ValueError(f"{ident!r} isn't a YouTube video's id.")
    return WATCH + ident


async def _title(client: httpx.AsyncClient, ident: str) -> str | None:
    try:
        # A second in all, not each of connect, write and read (httpx's timeout is per step).
        response = await asyncio.wait_for(
            client.get(OEMBED, params={"url": watch(ident), "format": "json"}), TIMEOUT_SECONDS
        )
        if response.status_code != 200 or len(response.content) > MAX_ANSWER_BYTES:
            return None
        body = response.json()
    except (httpx.HTTPError, TimeoutError, ValueError):
        return None
    title = body.get("title") if isinstance(body, dict) else None
    if not isinstance(title, str):
        return None
    words = " ".join(title.split())[:200].strip()
    return words or None


async def titles(ids: Iterable[str]) -> dict[str, str | None]:
    """YouTube's title for each video id, looked up at once: None where it
    didn't answer, or answered nothing a title can be made of."""
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return {}
    async with httpx.AsyncClient(
        transport=_installed.transport,
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
    ) as client:
        found = await asyncio.gather(*(_title(client, each) for each in wanted))
    return dict(zip(wanted, found, strict=True))
