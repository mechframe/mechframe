"""The AI's writing help over HTTP (decision 0058; `dev plans/contracts/kernel-ai.md`
§7): who may use it, a key saved in Settings → AI and never answered, each
task's answer, the shared budget, the writing rules reaching every task, and
the writing styles. The harness sends every call to its fake Anthropic."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from .conftest import Api

pytestmark = pytest.mark.db

KEY = "sk-ant-contract-" + "c" * 40
AI = "/api/kernel/ai"
SETTINGS = "/api/kernel/admin/settings"
STYLES = "/api/kernel/admin/writing/styles"
TASK = {"what": "Post body"}


async def _staff(api: Api, role: str) -> Api:
    person = await api.make_user(roles=[role], totp=True)
    staff = api.another_browser()
    await staff.signed_in_as(person)
    return staff


async def _save(admin: Api, section: str, changes: dict[str, Any]) -> None:
    form = await admin.http.get(f"{SETTINGS}/{section}")
    assert form.status_code == 200, form.text
    saved = await admin.http.put(
        f"{SETTINGS}/{section}", json={"version": form.json()["version"], "changes": changes}
    )
    assert saved.status_code == 200, saved.text


@pytest_asyncio.fixture(loop_scope="session")
async def admin(api: Api) -> Api:
    return await _staff(api, "admin")


@pytest_asyncio.fixture(loop_scope="session")
async def keyed(admin: Api) -> AsyncIterator[Api]:
    """A key saved in Settings → AI for the test, removed after it."""
    await _save(admin, "kernel.ai", {"api_key": KEY})
    try:
        yield admin
    finally:
        await _save(admin, "kernel.ai", {"api_key": ""})


async def _asked(api: Api) -> list[dict[str, Any]]:
    found = await api.http.get("/api/_test/ai")
    assert found.status_code == 200, found.text
    asked: list[dict[str, Any]] = found.json()["asked"]
    return asked


async def test_without_a_key_no_ai_shows_and_a_task_is_off(api: Api, admin: Api) -> None:
    editor = await _staff(api, "editor")
    state = await editor.http.get(AI)
    assert state.json() == {"ready": False, "unreadable": False, "styles": []}
    off = await editor.http.post(f"{AI}/draft", json={**TASK, "topic": "Spring"})
    assert (off.status_code, off.json()["code"]) == (503, "kernel.ai_off")
    assert (await admin.http.get("/api/kernel/admin/ai")).json()["source"] == "none"
    assert (await admin.http.post("/api/kernel/admin/ai/check")).status_code == 503
    assert await _asked(api) == []


async def test_a_member_may_not_use_the_ai_nor_an_editor_the_key(api: Api, keyed: Api) -> None:
    member = await _staff(api, "member")
    assert (await member.http.get(AI)).status_code == 403
    assert (await member.http.post(f"{AI}/draft", json={**TASK, "topic": "x"})).status_code == 403
    assert (await member.http.get(STYLES)).status_code == 403
    editor = await _staff(api, "editor")
    assert (await editor.http.get("/api/kernel/admin/ai")).status_code == 403
    assert (await editor.http.post("/api/kernel/admin/ai/check")).status_code == 403
    assert (await editor.http.get("/api/kernel/admin/writing/rules")).status_code == 403
    assert await _asked(api) == []


async def test_a_saved_key_is_used_and_never_answered(api: Api, keyed: Api) -> None:
    form = await keyed.http.get(f"{SETTINGS}/kernel.ai")
    assert form.json()["values"]["api_key"]["kept"] is True
    state = await keyed.http.get("/api/kernel/admin/ai")
    assert state.json() == {"source": "settings", "model": "claude-opus-5-5", "unreadable": False}
    checked = await keyed.http.post("/api/kernel/admin/ai/check")
    assert checked.json() == {"works": True, "source": "settings"}
    for answer in (form, state, checked):
        assert KEY not in answer.text
    asked = await _asked(api)
    assert [(call["method"], call["key"]) for call in asked] == [("GET", KEY)]


async def test_a_refused_key_is_a_502_never_a_401(api: Api, keyed: Api) -> None:
    queued = await api.http.post("/api/_test/ai", json={"answers": [{"status": 401}]})
    assert queued.status_code == 204
    refused = await keyed.http.post("/api/kernel/admin/ai/check")
    assert (refused.status_code, refused.json()["code"]) == (502, "kernel.ai_failed")
    assert "didn't accept the key" in refused.json()["detail"]


async def test_each_task_answers_in_its_shape_by_the_sites_rules(api: Api, keyed: Api) -> None:
    editor = await _staff(api, "editor")
    word = f"marker{uuid.uuid4().hex[:8]}"
    await _save(keyed, "kernel.writing", {"about": f"A label called {word}."})
    try:
        state = await editor.http.get(AI)
        assert state.json()["ready"] is True
        drafted = await editor.http.post(
            f"{AI}/draft", json={**TASK, "topic": "Spring", "length": "short"}
        )
        assert drafted.json() == {"markdown": "Words for the test."}
        titled = await editor.http.post(f"{AI}/titles", json={**TASK, "body": "The text."})
        assert titled.json() == {"titles": ["Words for the test."]}
        summed = await editor.http.post(
            f"{AI}/summary", json={**TASK, "body": "The text.", "max": 300}
        )
        assert summed.json() == {"summary": "Words for the test."}
        found = await editor.http.post(
            f"{AI}/search", json={**TASK, "title": "T", "body": "The text."}
        )
        assert found.json() == {
            "title": "Words for the test.",
            "description": "Words for the test.",
        }
        await api.http.post("/api/_test/ai", json={"answers": [{"words": "The text, rewritten."}]})
        rewritten = await editor.http.post(f"{AI}/rewrite", json={**TASK, "markdown": "The text."})
        assert rewritten.json() == {"markdown": "The text, rewritten."}
    finally:
        await _save(keyed, "kernel.writing", {"about": ""})
    asked = await _asked(api)
    assert len(asked) == 5
    assert all(call["key"] == KEY for call in asked)
    for call in asked:
        first = call["body"]["system"][0]["text"]
        assert first.startswith("This is the writing constitution")
        assert word in first


async def test_a_rewrite_that_drops_a_link_is_a_502(api: Api, keyed: Api) -> None:
    editor = await _staff(api, "editor")
    await api.http.post("/api/_test/ai", json={"answers": [{"words": "The album is out."}]})
    lost = await editor.http.post(
        f"{AI}/rewrite", json={**TASK, "markdown": "[The album](/music/album) is out."}
    )
    assert (lost.status_code, lost.json()["code"]) == (502, "kernel.ai_rewrite_lost")


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("draft", {"topic": "   "}),
        ("titles", {"topic": "", "body": "  "}),
        ("summary", {"body": "x", "max": 10}),
        ("draft", {"what": "", "topic": "x"}),
        ("rewrite", {"markdown": "x" * 20_001}),
    ],
)
async def test_a_task_refuses_what_it_cant_take(
    api: Api, keyed: Api, path: str, body: dict[str, Any]
) -> None:
    editor = await _staff(api, "editor")
    refused = await editor.http.post(f"{AI}/{path}", json={**TASK, **body})
    assert (refused.status_code, refused.json()["code"]) == (422, "kernel.invalid_request")


async def test_every_task_shares_one_budget(api: Api, keyed: Api) -> None:
    editor = await _staff(api, "editor")
    for n in range(20):
        path, body = ("titles", {"topic": "x"}) if n % 2 else ("summary", {"body": "x", "max": 100})
        answered = await editor.http.post(f"{AI}/{path}", json={**TASK, **body})
        assert answered.status_code == 200, (n, answered.text)
    over = await editor.http.post(f"{AI}/draft", json={**TASK, "topic": "x"})
    assert (over.status_code, over.json()["code"]) == (429, "kernel.rate_limited")


async def test_styles_are_kept_by_editors_and_picked_by_tasks(api: Api, keyed: Api) -> None:
    editor = await _staff(api, "editor")
    name = f"Warm {uuid.uuid4().hex[:8]}"
    made = await editor.http.post(
        STYLES,
        json={
            "name": name,
            "voice_rules": "- Short.",
            "avoid": "delve\nDelve",
            "samples": ["We play."],
        },
    )
    assert made.status_code == 201, made.text
    style = made.json()
    assert (style["version"], style["avoid"], style["samples"]) == (1, "delve", ["We play."])
    taken = await editor.http.post(STYLES, json={"name": name.upper()})
    assert (taken.status_code, taken.json()["code"]) == (409, "kernel.writing_style_name_taken")

    listed = await editor.http.get(AI)
    assert {"id": style["id"], "name": name, "description": ""} in listed.json()["styles"]
    drafted = await editor.http.post(
        f"{AI}/draft", json={**TASK, "topic": "x", "style_id": style["id"]}
    )
    assert drafted.status_code == 200
    system = (await _asked(api))[-1]["body"]["system"]
    assert len(system) == 2
    assert f"<name>{name}</name>" in system[1]["text"]

    changed = await editor.http.patch(
        f"{STYLES}/{style['id']}", json={"version": 1, "description": "Kind."}
    )
    assert changed.json()["version"] == 2
    stale = await editor.http.patch(
        f"{STYLES}/{style['id']}", json={"version": 1, "description": "Old."}
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "kernel.writing_style_changed")
    assert (await editor.http.get(f"{STYLES}/{style['id']}")).json()["description"] == "Kind."

    assert (await editor.http.delete(f"{STYLES}/{style['id']}")).status_code == 204
    gone = await editor.http.post(
        f"{AI}/draft", json={**TASK, "topic": "x", "style_id": style["id"]}
    )
    assert (gone.status_code, gone.json()["code"]) == (404, "kernel.writing_style_not_found")
    assert (await editor.http.get(f"{STYLES}/{style['id']}")).status_code == 404


async def test_style_rules_are_drafted_from_samples(api: Api, keyed: Api) -> None:
    editor = await _staff(api, "editor")
    await api.http.post(
        "/api/_test/ai",
        json={"answers": [{"answer": {"voice_rules": "- Short.", "avoid": ["delve", "Delve"]}}]},
    )
    drafted = await editor.http.post(f"{AI}/style-rules", json={"samples": ["We play.", "  "]})
    assert drafted.json() == {"voice_rules": "- Short.", "avoid": "delve"}
    empty = await editor.http.post(f"{AI}/style-rules", json={"samples": ["  "]})
    assert empty.status_code == 422


async def test_the_writing_rules_are_offered_to_admins(admin: Api) -> None:
    rules = await admin.http.get("/api/kernel/admin/writing/rules")
    body = rules.json()
    assert [rule["id"] for rule in body["rules"]] == [
        "verified_only",
        "no_fabrication",
        "illustrations",
        "plain_words",
        "ai_tells",
        "em_dash",
    ]
    assert "16 CFR Part 465" in body["rules"][1]["warning"]
    assert body["mechanics"].startswith("This is the writing constitution")
    assert body["default_text"].startswith("- Claim nothing")
    refused = await admin.http.put(
        f"{SETTINGS}/kernel.writing",
        json={
            "version": (await admin.http.get(f"{SETTINGS}/kernel.writing")).json()["version"],
            "changes": {"rules_off": ["made_up"]},
        },
    )
    assert refused.status_code == 422
