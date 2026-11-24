"""Blog's generated covers over HTTP only (decision 0065;
`dev plans/contracts/blog-covers.md` §7): who may draw one and keep one, what
each route answers, the AI's shared budget, and a kept cover as a PNG in the
media library that a post then shows. The harness sends every AI call to its
fake Anthropic. Nothing here imports blog."""

from __future__ import annotations

import base64
import struct
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from .conftest import Browser, slug

pytestmark = pytest.mark.db

COVERS = "/api/blog/admin/covers"
DRAW = f"{COVERS}/draw"
SETTINGS = "/api/kernel/admin/settings/kernel.ai"
KEY = "sk-ant-covers-contract-" + "c" * 40
ASK = {"title": "Ten years of Catalyst", "summary": "", "body": "Words.", "style": "editorial"}
COLOURS = {"ground": "#0D1224", "ink": "#c8cedd", "accent": "#ff7a1f"}
NOTHING = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


async def _key(admin: Browser, key: str) -> None:
    form = await admin.http.get(SETTINGS)
    assert form.status_code == 200, form.text
    saved = await admin.http.put(
        SETTINGS, json={"version": form.json()["version"], "changes": {"api_key": key}}
    )
    assert saved.status_code == 200, saved.text


async def _role(admin: Browser, *permissions: str) -> str:
    role = f"covers-{uuid.uuid4().hex[:8]}"
    made = await admin.http.post(
        "/api/auth/admin/roles",
        json={"id": role, "name": f"Covers {role[-8:]}", "permissions": list(permissions)},
    )
    assert made.status_code == 201, made.text
    return role


async def _queue(browser: Browser, *answers: dict[str, Any]) -> None:
    queued = await browser.http.post("/api/_test/ai", json={"answers": list(answers)})
    assert queued.status_code == 204, queued.text


async def _asked(browser: Browser) -> list[dict[str, Any]]:
    found = await browser.http.get("/api/_test/ai")
    assert found.status_code == 200, found.text
    asked: list[dict[str, Any]] = found.json()["asked"]
    return asked


@pytest_asyncio.fixture(loop_scope="session")
async def keyed(browser: Browser) -> AsyncIterator[Browser]:
    """An admin, with a key saved in Settings → AI for the test, taken off after it."""
    await browser.as_new("admin")
    await _key(browser, KEY)
    try:
        yield browser
    finally:
        await _key(browser, "")


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [("GET", COVERS, None), ("POST", DRAW, ASK), ("POST", COVERS, {"svg": "<svg/>", "alt": ""})],
)
async def test_signed_out_is_401_and_a_member_is_403(
    browser: Browser, method: str, path: str, body: Any
) -> None:
    signed_out = await browser.http.request(method, path, json=body)
    assert signed_out.status_code == 401, signed_out.text
    await browser.as_new("member")
    member = await browser.http.request(method, path, json=body)
    assert member.status_code == 403, member.text


async def test_get_covers_says_whether_a_cover_could_be_kept(browser: Browser) -> None:
    await browser.as_new("editor")
    state = await browser.http.get(COVERS)
    assert (state.status_code, state.json()) == (200, {"storage": True})


async def test_post_covers_draw(keyed: Browser) -> None:
    editor = keyed.stranger()
    await editor.as_new("editor")

    drawn = await editor.http.post(DRAW, json={**ASK, "colours": COLOURS, "wordmark": True})

    assert drawn.status_code == 200, drawn.text
    answer = drawn.json()
    assert set(answer) == {"svg", "alt", "preview"}
    # The preview is the kernel's own render, Inter and all, as the PNG kept will be (Codex on #147).
    head = "data:image/png;base64,"
    assert answer["preview"].startswith(head)
    png = base64.b64decode(answer["preview"][len(head) :])
    assert png[1:4] == b"PNG"
    assert struct.unpack(">II", png[16:24]) == (1200, 630)
    assert answer["svg"].startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert 'id="cover-wordmark"' in answer["svg"]
    assert answer["alt"] == "Words for the test."
    asked = await _asked(editor)
    assert len(asked) == 1
    assert asked[0]["key"] == KEY
    assert "#0D1224" in asked[0]["body"]["messages"][0]["content"]

    # A revision sends the cover shown back without its wordmark.
    revised = await editor.http.post(
        DRAW, json={**ASK, "wordmark": True, "current": answer["svg"], "changes": "Warmer."}
    )
    assert revised.status_code == 200, revised.text
    sent = (await _asked(editor))[-1]["body"]["messages"][0]["content"]
    assert "Warmer." in sent
    assert "cover-wordmark" not in sent

    # A refused drawing gets one repair try, then a plain 502.
    await _queue(
        editor, {"answer": {"svg": NOTHING, "alt": ""}}, {"answer": {"svg": NOTHING, "alt": ""}}
    )
    failed = await editor.http.post(DRAW, json=ASK)
    assert (failed.status_code, failed.json()["code"]) == (502, "kernel.ai_failed")
    assert failed.json()["detail"] == (
        "The AI couldn't draw a cover this time. Try again, or change what you asked for."
    )


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({**ASK, "style": "custom", "description": "  "}, "description"),
        ({**ASK, "title": "", "body": ""}, "title"),
        ({**ASK, "changes": "Warmer."}, "current"),
        ({**ASK, "style": "baroque"}, "style"),
        ({**ASK, "colours": {**COLOURS, "accent": "orange"}}, "colours"),
        ({**ASK, "description": "x" * 601}, "description"),
        ({**ASK, "current": "<svg/>" + "x" * 100_000, "changes": "x"}, "current"),
    ],
)
async def test_a_draw_refuses_what_it_cant_take(
    keyed: Browser, body: dict[str, Any], field: str
) -> None:
    refused = await keyed.http.post(DRAW, json=body)
    assert (refused.status_code, refused.json()["code"]) == (422, "kernel.invalid_request")
    assert any(field in name for name in refused.json()["errors"]), refused.json()
    assert await _asked(keyed) == []


async def test_a_draw_needs_the_ai_and_a_key(browser: Browser) -> None:
    await browser.as_new("admin")
    no_key = await browser.http.post(DRAW, json=ASK)
    assert (no_key.status_code, no_key.json()["code"]) == (503, "kernel.ai_off")

    writer = browser.stranger()
    await writer.as_new("member", await _role(browser, "blog.post.write"))
    no_ai = await writer.http.post(DRAW, json=ASK)
    assert no_ai.status_code == 403, no_ai.text


async def test_each_draw_spends_the_ais_budget_its_repair_included(keyed: Browser) -> None:
    editor = keyed.stranger()
    await editor.as_new("editor")
    await _queue(editor, {"answer": {"svg": NOTHING, "alt": ""}})
    for n in range(20):
        drawn = await editor.http.post(DRAW, json=ASK)
        assert drawn.status_code == 200, (n, drawn.text)
    assert len(await _asked(editor)) == 21  # the first press repaired once, in its one call
    over = await editor.http.post(DRAW, json=ASK)
    assert (over.status_code, over.json()["code"]) == (429, "kernel.rate_limited")
    # The kernel's own tasks share it.
    task = await editor.http.post("/api/kernel/ai/titles", json={"what": "Post", "topic": "x"})
    assert task.status_code == 429, task.text


async def test_post_covers(keyed: Browser) -> None:
    drawn = (await keyed.http.post(DRAW, json={**ASK, "colours": COLOURS})).json()

    kept = await keyed.http.post(COVERS, json={"svg": drawn["svg"], "alt": "  A gold ring.  "})

    assert kept.status_code == 201, kept.text
    cover = kept.json()["cover"]
    assert (cover["width"], cover["height"], cover["alt"]) == (2400, 1260, "A gold ring.")
    image = (await keyed.http.get(f"/api/media/admin/images/{cover['id']}")).json()
    assert (image["content_type"], image["alt"]) == ("image/png", "A gold ring.")
    assert len(await _asked(keyed)) == 1  # keeping it called no AI

    # The post saved with it shows it.
    made = await keyed.http.post(
        "/api/blog/admin/posts", json={"title": "Covered", "slug": slug(), "cover_id": cover["id"]}
    )
    assert made.status_code == 201, made.text
    assert made.json()["cover"]["id"] == cover["id"]


async def test_a_kept_cover_is_cleaned_again_never_trusted(keyed: Browser) -> None:
    sent = (
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        '<script>alert(2)</script><rect width="1200" height="630" fill="#123456"/>'
        '<image href="https://elsewhere.test/x.png"/></svg>'
    )
    kept = await keyed.http.post(COVERS, json={"svg": sent, "alt": ""})
    assert kept.status_code == 201, kept.text
    url = kept.json()["cover"]["url"]
    assert url.endswith(".png")

    refused = await keyed.http.post(COVERS, json={"svg": NOTHING, "alt": ""})
    assert (refused.status_code, refused.json()["code"]) == (422, "blog.cover_refused")
    assert list(refused.json()["errors"]) == ["svg"]


async def test_keeping_a_cover_needs_uploads(keyed: Browser) -> None:
    writer = keyed.stranger()
    await writer.as_new("member", await _role(keyed, "blog.post.write", "kernel.ai.write"))
    drawn = await writer.http.post(DRAW, json=ASK)
    assert drawn.status_code == 200, drawn.text
    refused = await writer.http.post(COVERS, json={"svg": drawn.json()["svg"], "alt": ""})
    assert refused.status_code == 403, refused.text
