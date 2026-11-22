"""The players' one list (`providers.json`, VybeSite's `embeds.json` as it
was): which links are a YouTube, SoundCloud, Spotify or Bandcamp player, the
player's address and shape, and the words shown with it. The web reads its
twin, `web/providers.json`, held equal by the tests, and both sides answer
the same cases (`tests/providers.cases.json`), so what the site draws as a
player is what an email draws as a card.

Nothing here asks a provider anything: the player's address is built from the
link alone, and the words are the writer's. Bandcamp publishes no way to look
a link up, so its player's id rides in the link's fragment, which the editor
writes from Bandcamp's own embed code:
`https://artist.bandcamp.com/album/slug#bandcamp-album=1234567`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

LIST: dict[str, Any] = json.loads(
    Path(__file__).with_name("providers.json").read_text(encoding="utf-8")
)
_PROVIDERS: dict[str, dict[str, Any]] = {provider["id"]: provider for provider in LIST["providers"]}

#: Each player's one host, in the list's order: the CSP's `frame-src`.
FRAME_HOSTS: tuple[str, ...] = tuple(provider["frame_host"] for provider in LIST["providers"])

#: Each player's shape, a class on the site: a 16:9 video, a 9:16 Short, or a
#: strip that many pixels tall.
SHAPES = frozenset(
    {"video", "short", "strip-120", "strip-152", "strip-166", "strip-352", "strip-450"}
)


@dataclass(frozen=True)
class Embed:
    """A link as its provider's player."""

    provider: str
    name: str
    kind: str
    player: str
    shape: str
    verb: str
    default: str
    allow: str


# Every pattern is ASCII alone, as the web's are: Python's \d takes any
# script's digits and IGNORECASE folds the long s and the Kelvin sign to s and k, which JavaScript's
# never do, so the two would disagree.
_YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}", re.ASCII)
_YOUTUBE_LIST = re.compile(r"[A-Za-z0-9_-]{2,64}", re.ASCII)
# YouTube's start time as its links write it: 90, 90s, 1m30s, 1h2m3s.
_YOUTUBE_TIME = re.compile(r"(?:([0-9]{1,2})h)?(?:([0-9]{1,4})m)?(?:([0-9]{1,6})s?)?", re.ASCII)
_SLUG = re.compile(r"[A-Za-z0-9_-]{1,255}", re.ASCII)
_SPOTIFY_ID = re.compile(r"[A-Za-z0-9]{22}", re.ASCII)
_SPOTIFY_INTL = re.compile(r"intl-[a-z]{2}(?:-[a-z]{2})?", re.ASCII | re.IGNORECASE)
_BANDCAMP_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.bandcamp\.com", re.ASCII)
_BANDCAMP_FRAGMENT = re.compile(r"bandcamp-(album|track)=([0-9]{1,12})", re.ASCII)
# What JavaScript's \s and trim() take for space, the one set both sides use
# for the words: Python's own takes \x1c to \x1f and \x85 besides, and not
# the byte-order mark. Built from code points, not typed.
_SPACE = "".join(
    map(
        chr,
        (
            9,
            10,
            11,
            12,
            13,
            32,
            0xA0,
            0x1680,
            *range(0x2000, 0x200B),
            0x2028,
            0x2029,
            0x202F,
            0x205F,
            0x3000,
            0xFEFF,
        ),
    )
)
# Words that are the address itself: a bare link, as Markdown links one.
_AN_ADDRESS = re.compile(f"(?:https?://|www\\.)[^{re.escape(_SPACE)}]*", re.ASCII | re.IGNORECASE)


def _embed(provider_id: str, kind: str, ident: str, query: str = "") -> Embed:
    provider = _PROVIDERS[provider_id]
    spec = provider["kinds"][kind]
    return Embed(
        provider=provider_id,
        name=provider["name"],
        kind=kind,
        player=spec["player"].replace("{id}", ident) + query,
        shape=spec["shape"],
        verb=provider["verb"],
        default=spec["words"],
        allow=provider["allow"],
    )


def _segments(path: str) -> list[str]:
    """The path's parts, one trailing slash allowed."""
    parts = path.split("/")[1:]
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def _first(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name) or [""]
    return values[0]


def _start(value: str) -> str:
    """`?start=N` for YouTube's time, or nothing for none, zero or one it can't read."""
    found = _YOUTUBE_TIME.fullmatch(value) if value else None
    if found is None:
        return ""
    hours, minutes, seconds = (int(part or 0) for part in found.groups())
    total = hours * 3600 + minutes * 60 + seconds
    return f"?start={total}" if total > 0 else ""


def _youtube(host: str, parts: list[str], query: dict[str, list[str]]) -> Embed | None:
    if host == "youtu.be":
        if len(parts) == 1 and _YOUTUBE_ID.fullmatch(parts[0]):
            return _embed("youtube", "video", parts[0], _start(_first(query, "t")))
        return None
    if parts == ["watch"]:
        video = _first(query, "v")
        return (
            _embed("youtube", "video", video, _start(_first(query, "t")))
            if _YOUTUBE_ID.fullmatch(video)
            else None
        )
    if parts in (["playlist"], ["embed", "videoseries"]):
        listed = _first(query, "list")
        return _embed("youtube", "playlist", listed) if _YOUTUBE_LIST.fullmatch(listed) else None
    if len(parts) == 2 and _YOUTUBE_ID.fullmatch(parts[1]):
        if parts[0] == "shorts":
            return _embed("youtube", "short", parts[1])
        if parts[0] == "live":
            return _embed("youtube", "video", parts[1])
        if parts[0] == "embed":
            return _embed("youtube", "video", parts[1], _start(_first(query, "start")))
    return None


def _soundcloud(parts: list[str]) -> Embed | None:
    provider = _PROVIDERS["soundcloud"]
    if (
        not parts
        or not all(_SLUG.fullmatch(part) for part in parts)
        or parts[0] in provider["not_profiles"]
    ):
        return None
    if len(parts) == 2 and parts[1] not in provider["profile_tabs"]:
        kind = "track"
    elif len(parts) == 3 and parts[1] == "sets":
        kind = "set"
    else:
        return None
    return _embed("soundcloud", kind, quote("https://soundcloud.com/" + "/".join(parts), safe=""))


def _spotify(parts: list[str]) -> Embed | None:
    if parts and _SPOTIFY_INTL.fullmatch(parts[0]):
        parts = parts[1:]
    if (
        len(parts) == 2
        and parts[0] in _PROVIDERS["spotify"]["kinds"]
        and _SPOTIFY_ID.fullmatch(parts[1])
    ):
        return _embed("spotify", parts[0], parts[1])
    return None


def _bandcamp(parts: list[str], fragment: str) -> Embed | None:
    found = _BANDCAMP_FRAGMENT.fullmatch(fragment)
    if found is None or len(parts) != 2 or parts[0] != found[1] or not _SLUG.fullmatch(parts[1]):
        return None
    return _embed("bandcamp", found[1], found[2])


def recognise(href: str) -> Embed | None:
    """The player `href` is, or None for a link that stays a link."""
    try:
        address = urlsplit(href or "")
        host = (address.hostname or "").lower()
    except ValueError:
        return None
    # A host alone, as every provider's links are: no port, no user, and no
    # brackets, which urlsplit reads a host from inside.
    if (
        address.scheme.lower() not in ("http", "https")
        or not host
        or address.netloc.lower() != host
    ):
        return None
    parts = _segments(address.path)
    query = parse_qs(address.query, keep_blank_values=True)
    if host in _PROVIDERS["youtube"]["hosts"]:
        return _youtube(host, parts, query)
    if host in _PROVIDERS["soundcloud"]["hosts"]:
        return _soundcloud(parts)
    if host in _PROVIDERS["spotify"]["hosts"]:
        return _spotify(parts)
    if _BANDCAMP_HOST.fullmatch(host) and host != "www.bandcamp.com":
        return _bandcamp(parts, address.fragment)
    return None


def words_for(embed: Embed, text: str) -> str:
    """The words shown with the player: the writer's link text, or the kind's
    own ("A video on YouTube") when it's blank or the address itself."""
    # str.strip, not a regex: a long run of spaces inside costs no quadratic scan (CodeRabbit on #127).
    words = (text or "").strip(_SPACE)
    return embed.default if not words or _AN_ADDRESS.fullmatch(words) else words
