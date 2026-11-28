"""Reactions over HTTP only (`dev plans/contracts/reactions.md` §2, §7): who may
call each route, what each answers, the refusals, the palette through the
kernel's settings route, the limit, and blog's posts as the things reacted to.
Nothing here imports reactions."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text

from kernel import Database

from .conftest import Browser, unique

pytestmark = pytest.mark.db

API = "/api/reactions"
POSTS = "/api/blog/admin/posts"
NOBODY = "00000000-0000-0000-0000-000000000001"


async def _live(browser: Browser) -> tuple[str, Browser]:
    """A post an editor writes and publishes, in a browser of its own: its id, and the editor."""
    editor = browser.stranger()
    await editor.as_new("member", "editor")
    made = await editor.http.post(
        POSTS, json={"title": "Catalyst is out", "slug": unique("p"), "body": "Some words."}
    )
    assert made.status_code == 201, made.text
    post: dict[str, Any] = made.json()
    published = await editor.http.post(f"{POSTS}/{post['id']}/publish", json={})
    assert published.status_code == 200, published.text
    return str(post["id"]), editor


async def _live_post(browser: Browser) -> str:
    return (await _live(browser))[0]


async def _read(browser: Browser, *ids: str, type: str = "blog.post") -> dict[str, Any]:
    answer = await browser.http.get(API, params=[("type", type), *[("id", each) for each in ids]])
    assert answer.status_code == 200, answer.text
    assert answer.headers["cache-control"] == "no-store"
    found: dict[str, Any] = answer.json()
    return found


def _press(post: str, key: str = "fire") -> str:
    return f"{API}/blog.post/{post}/{key}"


# --- who may call each route ---------------------------------------------------------------


async def test_anyone_reads_the_counts_and_only_a_member_presses(browser: Browser) -> None:
    post = await _live_post(browser)
    found = await _read(browser, post)
    assert found == {
        "palette": [
            {"key": "fire", "label": "Fire"},
            {"key": "love", "label": "Love"},
            {"key": "mind_blown", "label": "Mind blown"},
        ],
        "items": [{"id": post, "counts": {"fire": 0, "love": 0, "mind_blown": 0}, "mine": []}],
    }
    for method in ("PUT", "DELETE"):
        refused = await browser.http.request(method, _press(post))
        assert refused.status_code == 401, refused.text


async def test_a_member_presses_and_takes_back(browser: Browser) -> None:
    post = await _live_post(browser)
    await browser.as_new()
    pressed = await browser.http.put(_press(post))
    assert pressed.status_code == 200, pressed.text
    assert pressed.json() == {
        "id": post,
        "counts": {"fire": 1, "love": 0, "mind_blown": 0},
        "mine": ["fire"],
    }
    again = await browser.http.put(_press(post))
    assert again.json()["counts"]["fire"] == 1

    reader = browser.stranger()
    seen = await _read(reader, post)
    assert seen["items"][0] == {
        "id": post,
        "counts": {"fire": 1, "love": 0, "mind_blown": 0},
        "mine": [],
    }

    taken = await browser.http.delete(_press(post))
    assert taken.status_code == 200, taken.text
    assert taken.json()["counts"]["fire"] == 0
    twice = await browser.http.delete(_press(post))
    assert (twice.status_code, twice.json()["mine"]) == (200, [])


async def test_an_unverified_member_cant_react(browser: Browser) -> None:
    post = await _live_post(browser)
    await browser.as_new(verified=False)
    refused = await browser.http.put(_press(post))
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "reactions.email_unverified"


async def test_a_timed_out_member_cant_react_but_can_take_back(
    browser: Browser, migrated_url: str
) -> None:
    post = await _live_post(browser)
    member = await browser.as_new()
    assert (await browser.http.put(_press(post))).status_code == 200
    # The time-out set in the database: the kernel's own tests cover the route that sets one.
    database = Database(migrated_url, pool_size=1, max_overflow=0)
    try:
        async with database.sessions() as db:
            await db.execute(
                text(
                    "UPDATE auth_user SET timed_out_until = now() + interval '1 hour' WHERE id = :id"
                ),
                {"id": uuid.UUID(member.id)},
            )
            await db.commit()
    finally:
        await database.dispose()
    refused = await browser.http.put(_press(post, "love"))
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "kernel.timed_out"
    taken = await browser.http.delete(_press(post))
    assert taken.status_code == 200, taken.text


# --- the refusals ----------------------------------------------------------------------------


async def test_a_draft_or_a_gone_post_takes_no_reaction_and_isnt_answered(
    browser: Browser,
) -> None:
    post, editor = await _live(browser)
    await browser.as_new()
    assert (await browser.http.put(_press(post))).status_code == 200
    unpublished = await editor.http.post(f"{POSTS}/{post}/unpublish")
    assert unpublished.status_code == 200, unpublished.text

    for method in ("PUT", "DELETE"):
        refused = await browser.http.request(method, _press(post))
        assert refused.status_code == 404, refused.text
        assert refused.json()["code"] == "reactions.not_found"
    assert (await _read(browser, post))["items"] == []
    gone = await browser.http.put(_press(NOBODY))
    assert (gone.status_code, gone.json()["code"]) == (404, "reactions.not_found")


async def test_a_type_no_module_gives_and_a_key_thats_no_reaction_are_refused(
    browser: Browser,
) -> None:
    post = await _live_post(browser)
    await browser.as_new()
    unknown = await browser.http.get(API, params={"type": "shop.product", "id": post})
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["code"] == "reactions.unknown_type"
    pressed = await browser.http.put(f"{API}/shop.product/{post}/fire")
    assert (pressed.status_code, pressed.json()["code"]) == (404, "reactions.unknown_type")

    for key in ("clap", "Fire"):
        refused = await browser.http.put(_press(post, key))
        assert refused.status_code == 422, refused.text
    clap = await browser.http.put(_press(post, "clap"))
    assert (clap.status_code, clap.json()["code"]) == (422, "reactions.unknown_key")


async def test_a_read_takes_one_to_fifty_things(browser: Browser) -> None:
    post = await _live_post(browser)
    many = [post] + [str(uuid.uuid4()) for _ in range(49)]
    assert [each["id"] for each in (await _read(browser, *many))["items"]] == [post]
    too_many = await browser.http.get(
        API, params=[("type", "blog.post"), *[("id", each) for each in [*many, post]]]
    )
    assert too_many.status_code == 422, too_many.text
    none = await browser.http.get(API, params={"type": "blog.post"})
    assert none.status_code == 422, none.text


# --- the palette and the limit ---------------------------------------------------------------


async def test_the_palette_is_saved_through_the_kernels_settings(browser: Browser) -> None:
    post = await _live_post(browser)
    admin = browser.stranger()
    await admin.as_new("member", "admin")
    current = await admin.http.get("/api/kernel/admin/settings/reactions")
    assert current.status_code == 200, current.text
    version = current.json()["version"]
    try:
        wrong = await admin.http.put(
            "/api/kernel/admin/settings/reactions",
            json={"version": version, "changes": {"palette": ["fire", "clap"]}},
        )
        assert wrong.status_code == 422, wrong.text
        saved = await admin.http.put(
            "/api/kernel/admin/settings/reactions",
            json={"version": version, "changes": {"palette": ["love", "fire"]}},
        )
        assert saved.status_code == 200, saved.text
        version = saved.json()["version"]

        found = await _read(browser, post)
        assert [each["key"] for each in found["palette"]] == ["love", "fire"]
        await browser.as_new()
        refused = await browser.http.put(_press(post, "mind_blown"))
        assert (refused.status_code, refused.json()["code"]) == (422, "reactions.unknown_key")
        taken = await browser.http.delete(_press(post, "mind_blown"))
        assert taken.status_code == 200, taken.text
    finally:
        back = await admin.http.put(
            "/api/kernel/admin/settings/reactions",
            json={"version": version, "changes": {"palette": ["fire", "love", "mind_blown"]}},
        )
        assert back.status_code == 200, back.text


async def test_pressing_spends_the_limit(browser: Browser, monkeypatch: pytest.MonkeyPatch) -> None:
    post = await _live_post(browser)
    await browser.as_new()
    monkeypatch.setenv("REACTIONS_RATE_LIMIT", "3/1m")
    for path, method in (
        (_press(post), "PUT"),
        (_press(post), "DELETE"),
        (_press(post, "love"), "PUT"),
    ):
        answer = await browser.http.request(method, path)
        assert answer.status_code == 200, answer.text
    limited = await browser.http.put(_press(post, "mind_blown"))
    assert limited.status_code == 429, limited.text
    # The budget is the account's: another member still presses (cubic on #170).
    other = browser.stranger()
    await other.as_new()
    pressed = await other.http.put(_press(post))
    assert pressed.status_code == 200, pressed.text
