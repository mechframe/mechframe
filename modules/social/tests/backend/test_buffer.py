"""social's Buffer client against the harness's fake, with no database
(`dev plans/contracts/social.md` §7): what each answer and fault becomes, the
token in no message, a post's text and card, and the address check."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from harness.fake_buffer import REFUSED_TOKEN, FakeBuffer
from social import buffer

TOKEN = "buffer-token-for-the-client-tests-001"
CARD = buffer.LinkCard(
    url="https://site.test/blog/jazz", title="Jazz", description="Where.", thumbnail=None
)


@pytest.fixture
def fake() -> Iterator[FakeBuffer]:
    found = FakeBuffer()
    before = buffer.use_transport(found.transport)
    yield found
    buffer.use_transport(before)


def _answering(handler: object) -> Iterator[None]:
    before = buffer.use_transport(httpx.MockTransport(handler))  # type: ignore[arg-type]
    try:
        yield
    finally:
        buffer.use_transport(before)


async def test_the_channels_of_every_organization_in_buffers_order(fake: FakeBuffer) -> None:
    found = await buffer.Client(TOKEN).channels()
    assert [channel.id for channel in found][:2] == ["ch-linkedin", "ch-x"]
    assert found[-1].disconnected is True
    assert [asked.operation for asked in fake.asked] == ["account", "channels"]
    assert {asked.token for asked in fake.asked} == {TOKEN}


async def test_a_refused_token_says_what_to_do_and_never_repeats_it(fake: FakeBuffer) -> None:
    with pytest.raises(buffer.TokenRefused) as refused:
        await buffer.Client(REFUSED_TOKEN).channels()
    assert "Buffer didn't accept the token" in str(refused.value)
    assert REFUSED_TOKEN not in str(refused.value)


async def test_an_error_that_names_the_token_is_scrubbed_of_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errors": [{"message": f"bad {TOKEN} here"}]})

    for _ in _answering(handler):
        with pytest.raises(buffer.BufferError) as failed:
            await buffer.Client(TOKEN).channels()
    assert TOKEN not in str(failed.value)
    assert "the token" in str(failed.value)


async def test_x_gets_the_link_in_its_text_and_linkedin_a_card(fake: FakeBuffer) -> None:
    client = buffer.Client(TOKEN)
    queued = await client.create_post(channel_id="ch-x", service="twitter", text="Jazz", when="queue", card=CARD)
    assert queued.state == "queued"
    await client.create_post(channel_id="ch-linkedin", service="linkedin", text="Jazz", when="now", card=CARD)
    x, linkedin = (post["input"] for post in fake.made())
    assert x["text"] == "Jazz\n\nhttps://site.test/blog/jazz"
    assert x["mode"] == "addToQueue"
    assert linkedin["text"] == "Jazz"
    assert linkedin["mode"] == "shareNow"
    assert linkedin["metadata"]["linkedin"]["linkAttachment"] == {
        "url": CARD.url,
        "title": "Jazz",
        "description": "Where.",
    }


async def test_a_lost_answer_after_a_post_went_is_unanswered_and_elsewhere_slow(fake: FakeBuffer) -> None:
    fake.trouble.append("lose")
    with pytest.raises(buffer.Unanswered):
        await buffer.Client(TOKEN).create_post(
            channel_id="ch-x", service="twitter", text="Jazz", when="queue", card=CARD
        )

    def lost(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("no answer", request=request)

    for _ in _answering(lost):
        with pytest.raises(buffer.BufferError) as slow:
            await buffer.Client(TOKEN).channels()
    assert not isinstance(slow.value, buffer.Unanswered)
    assert str(slow.value) == buffer.SLOW


async def test_buffers_limit_says_how_long_to_wait(fake: FakeBuffer) -> None:
    fake.trouble.append("limit")
    with pytest.raises(buffer.BufferError) as limited:
        await buffer.Client(TOKEN).create_post(
            channel_id="ch-x", service="twitter", text="Jazz", when="queue", card=CARD
        )
    assert not isinstance(limited.value, buffer.Unanswered)
    assert "Try again in 2 minutes." in str(limited.value)


async def test_an_unreachable_buffer_made_nothing() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    for _ in _answering(down):
        with pytest.raises(buffer.BufferError) as failed:
            await buffer.Client(TOKEN).create_post(
                channel_id="ch-x", service="twitter", text="Jazz", when="queue", card=CARD
            )
    assert not isinstance(failed.value, buffer.Unanswered)
    assert str(failed.value) == buffer.UNREACHABLE


async def test_a_post_deleted_in_buffer_is_not_found(fake: FakeBuffer) -> None:
    with pytest.raises(buffer.NotFound):
        await buffer.Client(TOKEN).post_state("post-404")


async def test_the_address_must_answer_as_the_page(fake: FakeBuffer) -> None:
    assert await buffer.link_problem("https://site.test/blog/jazz") is None
    fake.down.add("https://site.test/blog/gone")
    said = await buffer.link_problem("https://site.test/blog/gone")
    assert said is not None
    assert "answered 404" in said


@pytest.mark.parametrize(
    ("value", "words"),
    [
        ("has a space in it here ok", "no spaces"),
        ("tiny0value", "too short"),
        ("x" * 401, "too long"),
    ],
)
def test_a_paste_that_couldnt_be_a_token(value: str, words: str) -> None:
    said = buffer.token_problem(value)
    assert said is not None
    assert words in said
    assert value not in said
    assert buffer.token_problem(TOKEN) is None


def test_each_networks_limit_counts_the_link() -> None:
    link = "https://site.test/blog/jazz"
    fits = "x" * (280 - len(link) - 2)
    assert buffer.text_problem(name="@t", descriptor="", service="twitter", text=fits, link=link) is None
    said = buffer.text_problem(name="@t", descriptor="", service="twitter", text=fits + "x", link=link)
    assert said is not None
    assert "280" in said
    assert buffer.text_for("twitter", f"See {link}", link) == f"See {link}"


def test_a_network_without_link_posts_has_a_problem() -> None:
    said = buffer.problem(name="t", descriptor="", service="instagram", disconnected=False, locked=False)
    assert "Instagram takes no link posts" in said
    assert buffer.problem(name="t", descriptor="", service="bluesky", disconnected=False, locked=False) == ""
