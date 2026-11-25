"""YouTube's links and titles (`dev plans/contracts/featured.md` §2, "YouTube's
titles"), on a fake transport: only oEmbed's address is asked, about the
video's watch address built from its id; a lookup that fails, answers
nothing usable or takes past its second leaves the title None; and several
are looked up at once, so a paste answers within about a second."""

from __future__ import annotations

import time
from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from featured import youtube

from harness.fake_youtube import FakeYouTube


@pytest.fixture
def fake() -> Iterator[FakeYouTube]:
    found = FakeYouTube()
    before = youtube.use_transport(found.transport)
    yield found
    youtube.use_transport(before)


@pytest.mark.parametrize(
    ("url", "ident"),
    [
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?t=42", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL1&index=2", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abcdefghijk", "abcdefghijk"),
        ("https://www.youtube.com/live/abcdefghijk", "abcdefghijk"),
        ("https://www.youtube-nocookie.com/embed/abcdefghijk?start=5", "abcdefghijk"),
        ("https://www.youtube.com/playlist?list=PL590L5WQmH8fJ54F369BLDSqIwcs-TCfs", None),
        ("https://vimeo.com/76979871", None),
        ("https://youtube.com.attacker.test/watch?v=dQw4w9WgXcQ", None),
        ("https://user@www.youtube.com/watch?v=dQw4w9WgXcQ", None),
        ("http://localhost:8000/watch?v=dQw4w9WgXcQ", None),
        ("not a link", None),
    ],
)
def test_a_link_is_a_video_or_not(url: str, ident: str | None) -> None:
    assert youtube.video_id(url) == ident


def test_the_watch_address_is_built_from_an_id_alone() -> None:
    assert youtube.watch("dQw4w9WgXcQ") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    with pytest.raises(ValueError, match="isn't a YouTube video's id"):
        youtube.watch("dQw4w9WgXcQ&x=1")


async def test_only_oembed_is_asked_about_the_watch_address(fake: FakeYouTube) -> None:
    fake.titles["dQw4w9WgXcQ"] = "  Hook   It Up  "
    found = await youtube.titles(["dQw4w9WgXcQ", "abcdefghijk", "dQw4w9WgXcQ"])
    assert found == {"dQw4w9WgXcQ": "Hook It Up", "abcdefghijk": "A video abcdefghijk"}
    assert len(fake.asked) == 2
    for asked in fake.asked:
        address = urlsplit(asked)
        assert (address.scheme, address.netloc, address.path) == (
            "https",
            "www.youtube.com",
            "/oembed",
        )
        query = parse_qs(address.query)
        assert query["format"] == ["json"]
        assert query["url"][0].startswith("https://www.youtube.com/watch?v=")


async def test_a_failed_lookup_leaves_the_title_none(fake: FakeYouTube) -> None:
    fake.down.add("abcdefghijk")
    assert await youtube.titles(["abcdefghijk"]) == {"abcdefghijk": None}
    assert await youtube.titles([]) == {}


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json=["a list"]),
        httpx.Response(200, json={"title": 7}),
        httpx.Response(200, json={"title": "   "}),
        httpx.Response(200, content=b'{"title": "' + b"x" * (70 * 1024) + b'"}'),
        httpx.Response(302, headers={"Location": "https://attacker.test/"}),
        httpx.Response(500),
    ],
)
async def test_an_answer_with_no_title_in_it_leaves_none(answer: httpx.Response) -> None:
    before = youtube.use_transport(httpx.MockTransport(lambda request: answer))
    try:
        assert await youtube.titles(["dQw4w9WgXcQ"]) == {"dQw4w9WgXcQ": None}
    finally:
        youtube.use_transport(before)


async def test_a_long_title_is_cut_to_200() -> None:
    long = httpx.Response(200, json={"title": "y" * 300})
    before = youtube.use_transport(httpx.MockTransport(lambda request: long))
    try:
        assert await youtube.titles(["dQw4w9WgXcQ"]) == {"dQw4w9WgXcQ": "y" * 200}
    finally:
        youtube.use_transport(before)


async def test_a_network_failure_leaves_none() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    before = youtube.use_transport(httpx.MockTransport(refuse))
    try:
        assert await youtube.titles(["dQw4w9WgXcQ"]) == {"dQw4w9WgXcQ": None}
    finally:
        youtube.use_transport(before)


async def test_slow_lookups_run_at_once_and_stop_at_a_second(fake: FakeYouTube) -> None:
    ids = [f"slowvideo{n:02d}" for n in range(8)]
    fake.slow.update(ids)
    started = time.monotonic()
    found = await youtube.titles([*ids, "dQw4w9WgXcQ"])
    took = time.monotonic() - started
    assert found == {**dict.fromkeys(ids), "dQw4w9WgXcQ": "A video dQw4w9WgXcQ"}
    # Windows' clock ticks in about 15 ms, so the floor allows a tick.
    assert youtube.TIMEOUT_SECONDS - 0.05 <= took < youtube.TIMEOUT_SECONDS + 0.5
