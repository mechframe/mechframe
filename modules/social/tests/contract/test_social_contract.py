"""Social posting over HTTP only (`dev plans/contracts/social.md` §2, §7): who
may call each route, the token's order, a live post shared to two channels,
each refusal before anything leaves, a share that may have gone, a second
press, Refresh and Take back, and the Dashboard's item and setup step.
Nothing here imports social: Buffer is the harness's fake."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from .conftest import SITE, Browser, unique

pytestmark = pytest.mark.db

STATE = "/api/social/admin/state"
CHANNELS = "/api/social/admin/channels"
SHARES = "/api/social/admin/shares"
SETTINGS = "/api/kernel/admin/settings/social"
TOKEN = "buffer-token-for-the-contract-tests-0001"
REFUSED = "refused-buffer-token-for-the-tests-0001"
NOBODY = "00000000-0000-0000-0000-000000000001"


@contextmanager
def _host(name: str, value: str | None) -> Iterator[None]:
    before = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if before is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = before


async def _save_token(browser: Browser, token: str) -> None:
    form = await browser.http.get(SETTINGS)
    assert form.status_code == 200, form.text
    saved = await browser.http.put(
        SETTINGS, json={"version": form.json()["version"], "changes": {"buffer_token": token}}
    )
    assert saved.status_code == 200, saved.text
    await browser.run_jobs()  # the change's event: the old token's channels are forgotten


async def _ready(browser: Browser) -> list[dict[str, Any]]:
    """An admin signed in, a token saved and Buffer's channels listed."""
    await browser.as_new("member", "admin")
    await _save_token(browser, TOKEN)
    listed = await browser.http.post(CHANNELS)
    assert listed.status_code == 200, listed.text
    channels: list[dict[str, Any]] = listed.json()["channels"]
    return channels


async def _live_post(browser: Browser, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        "/api/blog/admin/posts",
        json={
            "title": "Jazz at noon",
            "slug": unique("jazz"),
            "body": "Words.",
            "summary": "Where to hear it.",
            **fields,
        },
    )
    assert made.status_code == 201, made.text
    post: dict[str, Any] = made.json()
    published = await browser.http.post(f"/api/blog/admin/posts/{post['id']}/publish", json={})
    assert published.status_code == 200, published.text
    return post


def _send(post: dict[str, Any], *channels: str, **given: Any) -> dict[str, Any]:
    return {
        "type": "blog.post",
        "id": post["id"],
        "admin_path": f"/admin/blog/{post['id']}",
        "channel_ids": list(channels),
        "text": "Jazz at noon\n\nWhere to hear it.",
        **given,
    }


# --- who may call each route ---------------------------------------------------------------


ROUTES = [
    ("GET", STATE, None),
    ("POST", CHANNELS, None),
    ("GET", f"{SHARES}?type=blog.post&id={NOBODY}", None),
    (
        "POST",
        SHARES,
        {
            "type": "blog.post",
            "id": NOBODY,
            "admin_path": "/admin/blog",
            "channel_ids": ["x"],
            "text": "t",
        },
    ),
    ("POST", f"{SHARES}/refresh", {"type": "blog.post", "id": NOBODY}),
    ("DELETE", f"{SHARES}/{NOBODY}", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_signed_out_and_members_are_refused(
    browser: Browser, method: str, path: str, body: Any
) -> None:
    answer = await browser.http.request(method, path, json=body)
    assert answer.status_code == 401, answer.text
    await browser.as_new("member")
    answer = await browser.http.request(method, path, json=body)
    assert answer.status_code == 403, answer.text


async def test_an_editor_shares_but_cant_read_the_token(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    assert (await browser.http.get(STATE)).status_code == 403
    view = await browser.http.get(SHARES, params={"type": "blog.post", "id": NOBODY})
    assert view.status_code == 200, view.text
    assert view.json()["live"] is False


# --- the token -----------------------------------------------------------------------------


async def test_a_saved_token_wins_over_the_hosts_and_neither_is_answered(browser: Browser) -> None:
    await browser.as_new("member", "admin")
    form = await browser.http.get(SETTINGS)
    if form.json()["values"]["buffer_token"]["kept"]:
        cleared = await browser.http.put(
            SETTINGS, json={"version": form.json()["version"], "changes": {"buffer_token": ""}}
        )
        assert cleared.status_code == 200, cleared.text
    with _host("BUFFER_ACCESS_TOKEN", None):
        state = (await browser.http.get(STATE)).json()
        assert state == {"source": "none", "unreadable": False, "channels": [], "listed_at": None}
        refused = await browser.http.post(CHANNELS)
        assert refused.status_code == 503
        assert refused.json()["code"] == "social.no_token"
    with _host("BUFFER_ACCESS_TOKEN", "short"):
        assert (await browser.http.get(STATE)).json()["source"] == "none"
    with _host("BUFFER_ACCESS_TOKEN", "host-buffer-token-for-the-contract-0001"):
        assert (await browser.http.get(STATE)).json()["source"] == "host"
        await _save_token(browser, TOKEN)
        assert (await browser.http.get(STATE)).json()["source"] == "saved"
        listed = await browser.http.post(CHANNELS)
        assert listed.status_code == 200, listed.text
    asked = await browser.http.get(SETTINGS)
    assert TOKEN not in asked.text
    assert TOKEN not in (await browser.http.get(STATE)).text


async def test_a_value_that_couldnt_be_a_token_is_refused_without_repeating_it(
    browser: Browser,
) -> None:
    await browser.as_new("member", "admin")
    form = await browser.http.get(SETTINGS)
    refused = await browser.http.put(
        SETTINGS,
        json={
            "version": form.json()["version"],
            "changes": {"buffer_token": "has a space in it ok"},
        },
    )
    assert refused.status_code == 422
    assert "has a space" not in refused.text


async def test_a_token_buffer_refuses_says_so_and_never_shows_it(browser: Browser) -> None:
    await browser.as_new("member", "admin")
    await _save_token(browser, REFUSED)
    answer = await browser.http.post(CHANNELS)
    assert answer.status_code == 422
    assert answer.json()["code"] == "social.token_refused"
    assert REFUSED not in answer.text


async def test_the_channels_are_listed_with_what_each_can_take(browser: Browser) -> None:
    channels = await _ready(browser)
    by_id = {channel["id"]: channel for channel in channels}
    assert [channel["id"] for channel in channels] == [
        "ch-linkedin",
        "ch-x",
        "ch-bluesky",
        "ch-instagram",
        "ch-gone",
    ]
    assert by_id["ch-x"]["network"] == "X"
    assert by_id["ch-x"]["limit"] == 280
    assert by_id["ch-linkedin"]["usable"] is True
    assert by_id["ch-instagram"]["usable"] is False
    assert "takes no link posts" in by_id["ch-instagram"]["problem"]
    assert "isn't connected in Buffer" in by_id["ch-gone"]["problem"]
    state = (await browser.http.get(STATE)).json()
    assert state["source"] == "saved"
    assert len(state["channels"]) == 5
    assert state["listed_at"]


async def test_a_new_token_forgets_the_old_ones_channels(browser: Browser) -> None:
    await _ready(browser)
    await _save_token(browser, "another-buffer-token-for-the-tests-02")
    state = (await browser.http.get(STATE)).json()
    assert state["channels"] == []
    post = await _live_post(browser)
    view = (await browser.http.get(SHARES, params={"type": "blog.post", "id": post["id"]})).json()
    assert view["ready"] is False
    refused = await browser.http.post(SHARES, json=_send(post, "ch-x"))
    assert refused.status_code == 409
    assert refused.json()["code"] == "social.channels_unlisted"


# --- sharing ---------------------------------------------------------------------------------


async def test_a_live_post_is_shared_to_two_channels(browser: Browser) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    view = await browser.http.get(SHARES, params={"type": "blog.post", "id": post["id"]})
    assert view.status_code == 200, view.text
    opened = view.json()
    link = f"{SITE}/blog/{post['slug']}"
    assert opened["ready"] is True
    assert opened["live"] is True
    assert opened["card"]["url"] == link
    assert opened["card"]["title"] == "Jazz at noon"
    assert opened["text"] == "Jazz at noon\n\nWhere to hear it."
    assert opened["history"] == []

    shared = await browser.http.post(SHARES, json=_send(post, "ch-linkedin", "ch-x"))
    assert shared.status_code == 200, shared.text
    results = shared.json()["results"]
    assert [result["channel_id"] for result in results] == ["ch-linkedin", "ch-x"]
    assert {result["state"] for result in results} == {"queued"}
    assert len(shared.json()["history"]) == 2
    made = {post["input"]["channelId"]: post["input"] for post in await browser.buffer_posts()}
    assert made["ch-x"]["text"].endswith(f"\n\n{link}")
    assert link not in made["ch-linkedin"]["text"]
    attachment = made["ch-linkedin"]["metadata"]["linkedin"]["linkAttachment"]
    assert attachment["url"] == link
    assert attachment["title"] == "Jazz at noon"


async def test_a_draft_in_buffer_and_now_and_at_a_time(browser: Browser) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    later = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    for when, extra, state in (
        ("draft", {}, "draft"),
        ("now", {"again": True}, "sent"),
        ("at", {"again": True, "due_at": later}, "queued"),
    ):
        shared = await browser.http.post(SHARES, json=_send(post, "ch-bluesky", when=when, **extra))
        assert shared.status_code == 200, shared.text
        assert shared.json()["results"][0]["state"] == state
    sent = [one for one in shared.json()["history"] if one["state"] == "sent"]
    assert sent[0]["external_link"].startswith("https://network.test/")


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ({"channel_ids": ["ch-instagram"]}, 422, "social.channel_unusable"),
        ({"channel_ids": ["ch-gone"]}, 422, "social.channel_unusable"),
        ({"channel_ids": ["ch-nowhere"]}, 422, "social.channel_unknown"),
        ({"channel_ids": ["ch-x"], "text": "x" * 260}, 422, "social.text_too_long"),
        ({"channel_ids": ["ch-x"], "text": "   "}, 422, "social.text_needed"),
        (
            {"channel_ids": ["ch-x"], "when": "at", "due_at": "2020-01-01T00:00:00+00:00"},
            422,
            "social.time_passed",
        ),
        ({"channel_ids": ["ch-x"], "when": "at"}, 422, "social.time_needed"),
        (
            {"channel_ids": ["ch-x"], "admin_path": "https://elsewhere.test/admin"},
            422,
            "kernel.invalid_request",
        ),
    ],
)
async def test_each_refusal_comes_before_anything_leaves(
    browser: Browser, change: dict[str, Any], status: int, code: str
) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    answer = await browser.http.post(SHARES, json={**_send(post, "ch-x"), **change})
    assert answer.status_code == status, answer.text
    assert answer.json()["code"] == code
    assert await browser.buffer_posts() == []


async def test_a_draft_post_isnt_shared(browser: Browser) -> None:
    await _ready(browser)
    made = await browser.http.post(
        "/api/blog/admin/posts",
        json={"title": "Not yet", "slug": unique("draft"), "body": "Words."},
    )
    post = made.json()
    view = (await browser.http.get(SHARES, params={"type": "blog.post", "id": post["id"]})).json()
    assert view["live"] is False
    assert view["card"] is None
    answer = await browser.http.post(SHARES, json=_send(post, "ch-x"))
    assert answer.status_code == 409
    assert answer.json()["code"] == "social.not_live"


async def test_an_address_that_doesnt_answer_waits_but_a_buffer_draft_doesnt(
    browser: Browser,
) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    await browser.buffer(down=[f"{SITE}/blog/{post['slug']}"])
    answer = await browser.http.post(SHARES, json=_send(post, "ch-x"))
    assert answer.status_code == 409
    assert answer.json()["code"] == "social.address_not_answering"
    drafted = await browser.http.post(SHARES, json=_send(post, "ch-x", when="draft"))
    assert drafted.status_code == 200, drafted.text


async def test_a_second_share_to_a_channel_waits_for_again(browser: Browser) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    assert (await browser.http.post(SHARES, json=_send(post, "ch-x"))).status_code == 200
    again = await browser.http.post(SHARES, json=_send(post, "ch-x", "ch-bluesky"))
    assert again.status_code == 409
    assert again.json()["code"] == "social.shared_before"
    assert "@testsite" in again.json()["detail"]
    assert len(await browser.buffer_posts()) == 1
    meant = await browser.http.post(SHARES, json=_send(post, "ch-x", "ch-bluesky", again=True))
    assert meant.status_code == 200, meant.text


async def test_one_buffer_refused_doesnt_count_but_one_unanswered_does(browser: Browser) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    await browser.buffer(trouble=["refuse"])
    refused = (await browser.http.post(SHARES, json=_send(post, "ch-x"))).json()["results"][0]
    assert refused["state"] == "refused"
    assert "Buffer didn't take it" in refused["error"]
    await browser.buffer(trouble=["lose"])
    lost = (await browser.http.post(SHARES, json=_send(post, "ch-x"))).json()["results"][0]
    assert lost["state"] == "unknown"
    assert "may or may not have gone" in lost["error"]
    again = await browser.http.post(SHARES, json=_send(post, "ch-x"))
    assert again.status_code == 409


async def test_a_fault_after_the_post_went_is_unknown_and_a_limit_is_refused(
    browser: Browser,
) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    await browser.buffer(trouble=["fault", "limit"])
    shared = await browser.http.post(SHARES, json=_send(post, "ch-x", "ch-bluesky"))
    states = {result["channel_id"]: result for result in shared.json()["results"]}
    found = sorted(result["state"] for result in states.values())
    assert found == ["refused", "unknown"]
    limited = next(result for result in states.values() if result["state"] == "refused")
    assert "Try again in 2 minutes" in limited["error"]


async def test_refresh_reads_buffer_again_and_a_waiting_post_can_be_taken_back(
    browser: Browser,
) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    shared = (
        await browser.http.post(SHARES, json=_send(post, "ch-x", "ch-bluesky", "ch-linkedin"))
    ).json()
    made = [one["id"] for one in await browser.buffer_posts()]
    await browser.buffer(sent=[made[0]], deleted=[made[1]])
    thing = {"type": "blog.post", "id": post["id"]}
    refreshed = await browser.http.post(f"{SHARES}/refresh", json=thing)
    assert refreshed.status_code == 200, refreshed.text
    by_channel = {one["channel_id"]: one for one in refreshed.json()["history"]}
    assert by_channel["ch-x"]["state"] == "sent"
    assert by_channel["ch-x"]["external_link"] == f"https://network.test/{made[0]}"
    assert by_channel["ch-bluesky"]["state"] == "removed"
    waiting = by_channel["ch-linkedin"]
    assert waiting["state"] == "queued"
    taken = await browser.http.delete(f"{SHARES}/{waiting['id']}")
    assert taken.status_code == 200, taken.text
    assert {one["channel_id"]: one["state"] for one in taken.json()["history"]}[
        "ch-linkedin"
    ] == "removed"
    assert made[2] not in [one["id"] for one in await browser.buffer_posts()]
    sent = await browser.http.delete(f"{SHARES}/{by_channel['ch-x']['id']}")
    assert sent.status_code == 409
    assert sent.json()["code"] == "social.not_waiting"
    assert shared["results"]
    missing = await browser.http.delete(f"{SHARES}/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_a_person_may_share_only_so_often(browser: Browser) -> None:
    await _ready(browser)
    post = await _live_post(browser)
    with _host("SOCIAL_RATE_LIMIT", "2/1h"):
        assert (await browser.http.post(CHANNELS)).status_code == 200
        assert (await browser.http.post(SHARES, json=_send(post, "ch-x"))).status_code == 200
        limited = await browser.http.post(SHARES, json=_send(post, "ch-bluesky"))
        assert limited.status_code == 429


# --- the Dashboard ---------------------------------------------------------------------------


async def test_a_share_that_may_not_have_gone_is_on_the_dashboard(browser: Browser) -> None:
    await _ready(browser)
    setup = (await browser.http.get("/api/kernel/admin/setup")).json()
    step = next(one for one in setup["items"] if one["key"] == "social.connect_buffer")
    assert step["done"] is True
    post = await _live_post(browser)
    await browser.buffer(trouble=["lose"])
    assert (await browser.http.post(SHARES, json=_send(post, "ch-x"))).status_code == 200
    items = (await browser.http.get("/api/kernel/admin/attention")).json()["items"]
    item = next(one for one in items if one["key"] == "social.troubled")
    assert item["action"]["to"] == f"/admin/blog/{post['id']}"
