"""The players' one list (`providers.json`): which links are a YouTube,
SoundCloud, Spotify or Bandcamp player, the player's address and shape, and
the words shown with it. The web's twin is held equal here, and both read the
same cases (`tests/providers.cases.json`), so what the site draws as a player
is what an email draws as a card. Lifted with VybeSite's `test_embeds.py`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import embeds
import pytest
from embeds import providers, public

HOME = Path(__file__).resolve().parents[2]
SOURCE = HOME / "backend" / "embeds" / "providers.json"
TWIN = HOME / "web" / "providers.json"
CASES: dict[str, Any] = json.loads(
    (HOME / "tests" / "providers.cases.json").read_text(encoding="utf-8")
)


def _list() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(SOURCE.read_text(encoding="utf-8"))
    return loaded


def test_the_webs_twin_is_the_backends_list() -> None:
    """Copy `backend/embeds/providers.json` over `web/providers.json` after a change."""
    assert json.loads(TWIN.read_text(encoding="utf-8")) == _list()


def test_the_frames_the_policy_allows_are_the_four_players_hosts() -> None:
    assert providers.FRAME_HOSTS == (
        "https://www.youtube-nocookie.com",
        "https://w.soundcloud.com",
        "https://open.spotify.com",
        "https://bandcamp.com",
    )


def test_every_host_waits_for_media_consent() -> None:
    """Nothing loads from a provider before a visitor plays something (hook 6)."""
    assert embeds.CSP == [
        ("frame-src", "https://www.youtube-nocookie.com", "media"),
        ("frame-src", "https://w.soundcloud.com", "media"),
        ("frame-src", "https://open.spotify.com", "media"),
        ("frame-src", "https://bandcamp.com", "media"),
        ("script-src", "https://www.youtube.com", "media"),
        ("img-src", "https://i.ytimg.com", "media"),
    ]


@pytest.mark.parametrize("case", CASES["recognised"], ids=lambda c: c["href"])
def test_a_supported_link_is_its_providers_player(case: dict[str, str]) -> None:
    embed = providers.recognise(case["href"])

    assert embed is not None
    assert (embed.provider, embed.kind, embed.player, embed.shape) == (
        case["provider"],
        case["kind"],
        case["player"],
        case["shape"],
    )


@pytest.mark.parametrize("href", CASES["refused"])
def test_anything_else_stays_a_link(href: str) -> None:
    assert providers.recognise(href) is None


@pytest.mark.parametrize("case", CASES["words"], ids=lambda c: f"{c['href']} {c['text']!r}")
def test_the_words_are_the_writers_or_the_kinds_own(case: dict[str, str]) -> None:
    embed = providers.recognise(case["href"])
    assert embed is not None
    assert providers.words_for(embed, case["text"]) == case["words"]


def test_each_player_says_its_provider_its_verb_and_what_it_may_do() -> None:
    youtube = providers.recognise("https://youtu.be/aBcDeFgHiJk")
    spotify = providers.recognise("https://open.spotify.com/track/0aBcDeFgHiJkLmNoPqRsTu")

    assert youtube is not None
    assert spotify is not None
    assert (youtube.name, youtube.verb, youtube.default) == (
        "YouTube",
        "Watch",
        "A video on YouTube",
    )
    assert (spotify.name, spotify.verb, spotify.default) == (
        "Spotify",
        "Listen",
        "A track on Spotify",
    )
    assert "fullscreen" in youtube.allow


def test_every_player_is_on_its_providers_own_frame_host() -> None:
    """The CSP allows the four hosts and nothing else, so a player built on any
    other would be refused: every case's player starts with its host."""
    hosts = {p["id"]: p["frame_host"] for p in _list()["providers"]}
    for case in CASES["recognised"]:
        assert case["player"].startswith(hosts[case["provider"]] + "/"), case["href"]


def test_every_kind_has_its_shape_words_and_player() -> None:
    for provider in _list()["providers"]:
        assert provider["verb"] in {"Watch", "Listen"}
        for kind, spec in provider["kinds"].items():
            assert spec["shape"] in providers.SHAPES, (provider["id"], kind)
            assert spec["words"].endswith(f" on {provider['name']}"), (provider["id"], kind)
            assert spec["player"].startswith(provider["frame_host"] + "/")
            assert "{id}" in spec["player"]


@pytest.mark.parametrize("case", CASES["bandcamp_codes"], ids=lambda c: c["name"])
def test_bandcamps_own_code_reads_as_the_web_reads_it(case: dict[str, str | None]) -> None:
    """0.1.2: the twin of the web's `fromBandcampCode`, held to the same cases."""
    found = providers.from_bandcamp_code(str(case["code"]))
    assert found == ((case["href"], case["words"]) if case["href"] else None)


def test_a_paste_longer_than_any_code_is_not_read() -> None:
    """Counted as the web counts: a character past U+FFFF is two."""
    [album] = [c for c in CASES["bandcamp_codes"] if c["name"] == "an album's code"]
    code = str(album["code"])
    assert providers.from_bandcamp_code(code + " " * (providers.MOST_CODE - len(code))) is not None
    assert providers.from_bandcamp_code(code + " " * (providers.MOST_CODE - len(code) + 1)) is None
    astral = chr(0x1F3B5) * ((providers.MOST_CODE - len(code)) // 2 + 1)
    assert providers.from_bandcamp_code(code + astral) is None
    started = time.perf_counter()
    assert providers.from_bandcamp_code(code + " " * 5_000_000) is None
    assert time.perf_counter() - started < 0.2


def test_public_reads_bandcamps_code() -> None:
    """`discography` reads a pasted player through `embeds.public` alone (SPEC 7)."""
    [album] = [c for c in CASES["bandcamp_codes"] if c["name"] == "an album's code"]
    assert public.from_bandcamp_code(str(album["code"])) == (album["href"], album["words"])


def test_long_words_are_trimmed_in_linear_time() -> None:
    """A long run of spaces inside the words is kept, and costs no quadratic scan (CodeRabbit on #127)."""
    embed = providers.recognise("https://youtu.be/aBcDeFgHiJk")
    assert embed is not None
    words = "A" + " " * 20000 + "B"
    started = time.perf_counter()
    assert providers.words_for(embed, f"  {words}﻿") == words
    assert time.perf_counter() - started < 0.2


def test_public_reads_links_as_the_site_does() -> None:
    """`campaigns`' emails read a link through `embeds.public` alone (SPEC 7)."""
    found = public.recognise("https://www.youtube.com/watch?v=aBcDeFgHiJk")
    assert found is not None
    assert public.words_for(found, "") == "A video on YouTube"
    assert public.recognise("https://example.net/") is None
