"""The contact module's routes over HTTP only (`dev plans/contracts/contact.md`
§2, §7): who may call each, what a message that passes and one that's held
each come to, the Inbox's tabs, its notices and the site's server copy of
/contact. Nothing here imports contact."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from .conftest import Browser, Person, unique

pytestmark = pytest.mark.db

API = "/api/contact"
ADMIN = f"{API}/admin/messages"
NOBODY = "00000000-0000-0000-0000-000000000001"
UNCHECKED = {"mechframe_unchecked": True}
#: What the kit's useBotProof() sends for a person who took their time.
PERSON = {"website": "", "elapsed_ms": 5_000}


def _body(**fields: Any) -> dict[str, Any]:
    return {
        "name": unique("Rae"),
        "email": f"{unique('rae')}@example.com",
        "topic": "question",
        "message": "Could you play a night in March?",
        "wants_news": False,
        "bot": PERSON,
        **fields,
    }


async def _send(browser: Browser, **fields: Any) -> dict[str, Any]:
    body = _body(**fields)
    sent = await browser.http.post(f"{API}/messages", json=body)
    assert (sent.status_code, sent.json()) == (202, {"received": True}), sent.text
    return body


async def _find(browser: Browser, name: str, tab: str = "all") -> dict[str, Any] | None:
    cursor = None
    while True:
        params = {"status": tab, **({"cursor": cursor} if cursor else {})}
        page = await browser.http.get(ADMIN, params=params)
        assert page.status_code == 200, page.text
        found: dict[str, Any] = page.json()
        for item in found["items"]:
            if item["name"] == name:
                return dict(item)
        cursor = found["next_cursor"]
        if cursor is None:
            return None


async def _as_reader(browser: Browser) -> Person:
    return await browser.as_new("member", "admin")


async def _notices_for(browser: Browser, message_id: str) -> list[dict[str, Any]]:
    found = await browser.http.get("/api/kernel/notifications", params={"limit": 100})
    assert found.status_code == 200, found.text
    return [
        notice
        for notice in found.json()["items"]
        if notice["link"] == f"/admin/contact/{message_id}"
    ]


# --- who may call each route ---------------------------------------------------------------


async def test_the_form_is_open_to_anyone(browser: Browser) -> None:
    form = await browser.http.get(f"{API}/form")
    assert form.status_code == 200, form.text
    body = form.json()
    assert body["intro"]
    assert [topic["key"] for topic in body["topics"]] == ["question", "work", "press", "other"]
    assert set(body["topics"][0]) == {"key", "label"}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", ADMIN, None),
        ("GET", f"{ADMIN}/export", None),
        ("GET", f"{ADMIN}/{NOBODY}", None),
        ("POST", f"{ADMIN}/{NOBODY}/status", {"status": "replied"}),
        ("DELETE", f"{ADMIN}/{NOBODY}", None),
    ],
)
async def test_signed_out_is_401_and_a_member_or_an_editor_is_403(
    browser: Browser, method: str, path: str, body: Any
) -> None:
    signed_out = await browser.http.request(method, path, json=body)
    assert signed_out.status_code == 401, signed_out.text

    for roles in (("member",), ("member", "editor")):
        browser.forget()
        await browser.as_new(*roles)
        refused = await browser.http.request(method, path, json=body)
        assert refused.status_code == 403, refused.text
        assert refused.json()["code"] == "kernel.forbidden"


# --- a message arrives ---------------------------------------------------------------------


async def test_a_message_that_passes_is_new_and_the_inbox_s_readers_are_told(
    browser: Browser,
) -> None:
    reader = await _as_reader(browser)
    sent = await _send(browser.stranger(), topic="work")

    listed = await _find(browser, sent["name"], "new")
    assert listed is not None
    assert (listed["status"], listed["topic_label"], listed["first"]) == (
        "new",
        "Working together",
        True,
    )
    assert listed["first_line"] == "Could you play a night in March?"
    opened = await browser.http.get(f"{ADMIN}/{listed['id']}")
    assert opened.status_code == 200, opened.text
    message = opened.json()
    assert (message["email"], message["message"], message["held_reason"]) == (
        sent["email"],
        sent["message"],
        None,
    )

    [notice] = await _notices_for(browser, listed["id"])
    assert (notice["key"], notice["title"]) == (
        "contact.message_received",
        "New message: Working together",
    )
    mail = [m for m in await browser.mail(reader.email) if m["subject"] == notice["title"]]
    assert len(mail) == 1
    assert sent["name"] in mail[0]["text"]
    assert f"/admin/contact/{listed['id']}" in mail[0]["text"]
    assert sent["message"] not in mail[0]["text"]

    page = (await browser.http.get(ADMIN, params={"status": "new"})).json()
    assert page["waiting"]["what"].endswith("waiting")
    assert page["counts"]["new"] >= 1
    attention = await browser.http.get("/api/kernel/admin/attention")
    assert "contact.waiting" in {item["key"] for item in attention.json()["items"]}


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"bot": {"website": "https://bots.example", "elapsed_ms": 5_000}}, "honeypot"),
        ({"bot": {"website": "", "elapsed_ms": 200}}, "too_fast"),
        ({"bot": None}, "not_from_form"),
        (
            {"message": "See https://a.example https://b.example https://c.example now"},
            "links",
        ),
    ],
)
async def test_a_held_message_gets_the_same_thanks_and_is_set_apart_as_spam(
    browser: Browser, fields: dict[str, Any], reason: str
) -> None:
    await _as_reader(browser)
    sent = await _send(browser.stranger(), wants_news=True, **fields)

    assert await _find(browser, sent["name"], "all") is None
    held = await _find(browser, sent["name"], "spam")
    assert held is not None
    assert held["status"] == "spam"
    opened = (await browser.http.get(f"{ADMIN}/{held['id']}")).json()
    assert opened["held_reason"] == reason
    assert await _notices_for(browser, held["id"]) == []


async def test_the_form_s_fields_are_checked(browser: Browser) -> None:
    for fields, field in (
        ({"email": "not an address"}, "email"),
        ({"name": "  "}, "name"),
        ({"message": ""}, "message"),
        ({"topic": "nothing-like-it"}, "topic"),
    ):
        refused = await browser.http.post(f"{API}/messages", json=_body(**fields))
        assert refused.status_code == 422, refused.text
        assert field in json.dumps(refused.json()), refused.text


async def test_the_sixth_message_in_an_hour_from_one_address_is_429(browser: Browser) -> None:
    for _ in range(5):
        await _send(browser)
    sixth = await browser.http.post(f"{API}/messages", json=_body())
    assert sixth.status_code == 429, sixth.text
    assert sixth.json()["code"] == "kernel.rate_limited"


# --- the Inbox -----------------------------------------------------------------------------


async def test_a_reader_marks_archives_sets_apart_lets_out_and_deletes(browser: Browser) -> None:
    await _as_reader(browser)
    held = await _send(browser.stranger(), bot={"website": "", "elapsed_ms": 100})
    found = await _find(browser, held["name"], "spam")
    assert found is not None
    path = f"{ADMIN}/{found['id']}"

    for status in ("new", "spam", "new", "replied", "archived"):
        moved = await browser.http.post(f"{path}/status", json={"status": status})
        assert moved.status_code == 200, moved.text
        assert moved.json()["status"] == status
    # Let out of spam twice, told once.
    assert len(await _notices_for(browser, found["id"])) == 1
    assert (await _find(browser, held["name"], "archived")) is not None

    wrong = await browser.http.post(f"{path}/status", json={"status": "read"})
    assert wrong.status_code == 422

    gone = await browser.http.delete(path)
    assert gone.status_code == 204
    missing = await browser.http.get(path)
    assert (missing.status_code, missing.json()["code"]) == (404, "contact.message_not_found")
    again = await browser.http.delete(path)
    assert again.status_code == 404


async def test_status_changes_and_exports_are_in_the_audit_log(browser: Browser) -> None:
    owner = await browser.as_new("member", "owner")
    sent = await _send(browser.stranger())
    found = await _find(browser, sent["name"], "new")
    assert found is not None
    await browser.http.post(f"{ADMIN}/{found['id']}/status", json={"status": "replied"})

    exported = await browser.http.get(f"{ADMIN}/export", params={"status": "replied"})
    assert exported.status_code == 200, exported.text
    [row] = [item for item in exported.json()["items"] if item["id"] == found["id"]]
    assert (row["email"], row["message"], row["status"]) == (
        sent["email"],
        sent["message"],
        "replied",
    )

    log = await browser.http.get(
        "/api/kernel/admin/audit", params={"action": "contact.", "actor": owner.id}
    )
    assert log.status_code == 200, log.text
    actions = [entry["action"] for entry in log.json()["items"]]
    assert "contact.message.status" in actions
    assert "contact.messages.exported" in actions
    assert sent["email"] not in log.text


async def test_a_cursor_pages_on_and_a_bad_one_is_422(browser: Browser) -> None:
    await _as_reader(browser)
    wrong = await browser.http.get(ADMIN, params={"cursor": "not-a-cursor"})
    assert wrong.status_code == 422, wrong.text
    tab = await browser.http.get(ADMIN, params={"status": "everything"})
    assert tab.status_code == 422


# --- the site's page -----------------------------------------------------------------------


def _json_ld(html: str) -> list[dict[str, Any]]:
    found = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    return [json.loads(each) for each in found]


async def test_the_server_copy_of_the_contact_page(browser: Browser) -> None:
    served = await browser.http.get("/contact", extensions=UNCHECKED)
    assert served.status_code == 200, served.text
    html = served.text
    assert "<title>Contact · " in html
    assert "<h1>Contact</h1>" in html
    assert "<li>Working together</li>" in html
    (data,) = [each for each in _json_ld(html) if each.get("@type") == "ContactPage"]
    assert (data["name"], data["url"].endswith("/contact")) == ("Contact", True)
    sitemap = await browser.http.get("/sitemap.xml", extensions=UNCHECKED)
    assert "/contact</loc>" in sitemap.text
