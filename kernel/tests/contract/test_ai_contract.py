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
    assert state.json() == {
        "source": "settings",
        "model": "claude-opus-5-5",
        "model_source": "environment",
        "unreadable": False,
    }
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


# --- the model (decision 0064, `dev plans/contracts/ai-model.md`) ------------------------

MODELS = "/api/kernel/admin/ai/models"
MODEL = "/api/kernel/admin/ai/model"
OFFERED = [
    {"id": "claude-opus-5-5", "name": "Claude Opus 5.5"},
    {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5"},
    {"id": "claude-haiku-5-5", "name": "Claude Haiku 5.5"},
]
NOT_OFFERED = "Anthropic doesn't offer that model to this key now. Choose one from the list."


async def _pick(admin: Api, model: str | None, version: int | None = None) -> Any:
    if version is None:
        version = (await admin.http.get(f"{SETTINGS}/kernel.ai")).json()["version"]
    return await admin.http.put(MODEL, json={"version": version, "model": model})


async def test_get_admin_ai_models(api: Api, admin: Api) -> None:
    off = await admin.http.get(MODELS)
    assert (off.status_code, off.json()["code"]) == (503, "kernel.ai_off")
    editor = await _staff(api, "editor")
    assert (await editor.http.get(MODELS)).status_code == 403
    assert await _asked(api) == []
    await _save(admin, "kernel.ai", {"api_key": KEY})
    try:
        listed = await admin.http.get(MODELS)
        assert listed.status_code == 200, listed.text
        assert listed.json() == {
            "models": OFFERED,
            "in_use": {
                "id": "claude-opus-5-5",
                "name": "Claude Opus 5.5",
                "source": "environment",
                "listed": True,
            },
        }
        assert KEY not in listed.text
        # Every page, with the key in use, each time it's asked: no cache.
        await admin.http.get(MODELS)
        assert [(call["path"].endswith("/models"), call["key"]) for call in await _asked(api)] == [
            (True, KEY)
        ] * 6
        queued = await api.http.post("/api/_test/ai", json={"answers": [{"status": 401}]})
        assert queued.status_code == 204
        refused = await admin.http.get(MODELS)
        assert (refused.status_code, refused.json()["code"]) == (502, "kernel.ai_failed")
        assert "didn't accept the key" in refused.json()["detail"]
    finally:
        await _save(admin, "kernel.ai", {"api_key": ""})


async def test_the_model_list_has_its_own_budget(api: Api, keyed: Api) -> None:
    for _ in range(60):
        assert (await keyed.http.get(MODELS)).status_code == 200
    spent = await keyed.http.get(MODELS)
    assert (spent.status_code, spent.json()["code"]) == (429, "kernel.rate_limited")
    # The writing help's budget is untouched.
    editor_state = await keyed.http.get(AI)
    assert editor_state.status_code == 200


async def test_put_admin_ai_model(api: Api, keyed: Api) -> None:
    try:
        saved = await _pick(keyed, "claude-sonnet-5-5")
        assert saved.status_code == 200, saved.text
        assert saved.json()["changed"] == ["model"]
        state = (await keyed.http.get("/api/kernel/admin/ai")).json()
        assert (state["model"], state["model_source"]) == ("claude-sonnet-5-5", "settings")
        history = (await keyed.http.get(f"{SETTINGS}/kernel.ai/history")).json()["items"][0]
        assert (history["changed"], history["via"]) == (["model"], "ai.model")

        # A task asks for it, with the fallbacks the host's would get.
        editor = await _staff(api, "editor")
        drafted = await editor.http.post(f"{AI}/draft", json={**TASK, "topic": "Spring"})
        assert drafted.status_code == 200, drafted.text
        sent = (await _asked(api))[-1]
        assert sent["body"]["model"] == "claude-sonnet-5-5"
        assert sent["body"]["fallbacks"] == "default"

        # Only what the dropdown offers: an older Opus, another kind, or none at all.
        for offered_not in ("claude-opus-5", "claude-fable-5-1", "claude-opus-9-9"):
            refused = await _pick(keyed, offered_not)
            assert (refused.status_code, refused.json()["errors"]) == (
                422,
                {"model": [NOT_OFFERED]},
            )
        # The settings form can't change it, only this route.
        form = (await keyed.http.get(f"{SETTINGS}/kernel.ai")).json()
        generic = await keyed.http.put(
            f"{SETTINGS}/kernel.ai",
            json={"version": form["version"], "changes": {"model": "claude-haiku-5-5"}},
        )
        assert (generic.status_code, generic.json()["errors"]) == (
            422,
            {"model": ["Choose the model from Anthropic's list, in Settings → AI."]},
        )

        # A crossed save that changed the model too is a conflict.
        assert (await _pick(keyed, "claude-haiku-5-5")).status_code == 200
        crossed = await _pick(keyed, "claude-opus-5-5", version=form["version"])
        assert (crossed.status_code, crossed.json()["code"]) == (409, "kernel.settings_conflict")

        # A list that can't be read saves nothing.
        await api.http.post("/api/_test/ai", json={"answers": [{"status": 500}]})
        failed = await _pick(keyed, "claude-opus-5-5")
        assert (failed.status_code, failed.json()["code"]) == (502, "kernel.ai_failed")
        assert (await keyed.http.get("/api/kernel/admin/ai")).json()["model"] == "claude-haiku-5-5"

        # Use the host's model: cleared, without asking Anthropic.
        before = len(await _asked(api))
        cleared = await _pick(keyed, None)
        assert cleared.status_code == 200, cleared.text
        assert len(await _asked(api)) == before
        state = (await keyed.http.get("/api/kernel/admin/ai")).json()
        assert (state["model"], state["model_source"]) == ("claude-opus-5-5", "environment")
    finally:
        await _pick(keyed, None)
