"""The newsletter's routes over HTTP only (`dev plans/contracts/campaigns.md`
§2 and §7): who may call each, signing up and confirming, the links, a send's
audience, pace and headers, schedules and cancels, tests, Resend's webhook,
the events from contact and blog, the attention items and the server copy.
Nothing here imports campaigns.

Every send test starts from an empty list (`_fresh`): the suite shares one
database, and a send goes to everyone subscribed."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from .conftest import Browser, unique

pytestmark = pytest.mark.db

API = "/api/campaigns"
ADMIN = f"{API}/admin"
SETTINGS = "/api/kernel/admin/settings/campaigns"
NOBODY = "00000000-0000-0000-0000-000000000001"
#: What the kit's useBotProof() sends for a person who took their time.
PERSON = {"website": "", "elapsed_ms": 5_000}
ADDRESS = "P.O. Box 12\nBoston, MA 02101"
KEY = b"thirty-two bytes of signing key!"
SECRET = "whsec_" + base64.b64encode(KEY).decode()


def _address(name: str = "fan") -> str:
    return f"{unique(name)}@example.org"


async def _owner(browser: Browser) -> None:
    await browser.as_new("member", "owner")


async def _settings(browser: Browser, **changes: Any) -> None:
    form = await browser.http.get(SETTINGS)
    assert form.status_code == 200, form.text
    saved = await browser.http.put(
        SETTINGS, json={"version": form.json()["version"], "changes": changes}
    )
    assert saved.status_code == 200, saved.text


async def _pages(browser: Browser, path: str, **query: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    cursor = None
    while True:
        params = {**query, **({"cursor": cursor} if cursor else {})}
        page = await browser.http.get(path, params=params)
        assert page.status_code == 200, page.text
        body = page.json()
        found += body["items"]
        cursor = body["next_cursor"]
        if cursor is None:
            return found


async def _fresh(browser: Browser, **settings: Any) -> None:
    """Signed in as an owner, with nobody on the list, nothing scheduled or
    sending, a postal address and the default pace (unless told otherwise)."""
    await _owner(browser)
    await _settings(
        browser,
        postal_address=settings.get("postal_address", ADDRESS),
        send_per_hour=settings.get("send_per_hour", 6000),
        signups_open=settings.get("signups_open", True),
    )
    for row in await _pages(browser, f"{ADMIN}/subscribers"):
        gone = await browser.http.delete(f"{ADMIN}/subscribers/{row['id']}")
        assert gone.status_code == 204, gone.text
    for row in await _pages(browser, f"{ADMIN}/emails"):
        if row["status"] in ("scheduled", "sending"):
            stopped = await browser.http.post(f"{ADMIN}/emails/{row['id']}/cancel")
            assert stopped.status_code == 200, stopped.text


async def _subscribe(browser: Browser, address: str, **fields: Any) -> None:
    sent = await browser.stranger().http.post(
        f"{API}/subscribe", json={"email": address, "bot": PERSON, **fields}
    )
    assert (sent.status_code, sent.json()) == (202, {"received": True}), sent.text


def _confirm_token(message: dict[str, Any]) -> str:
    found = re.search(r"/newsletter/confirm\?token=(\S+)", message["text"])
    assert found, message["text"]
    return found.group(1)


async def _confirmations(browser: Browser, address: str) -> list[dict[str, Any]]:
    return [each for each in await browser.mail(address) if each["subject"].startswith("Confirm")]


async def _subscribed(browser: Browser, *addresses: str) -> dict[str, str]:
    """Each address signed up and confirmed: its confirmation token."""
    tokens = {}
    for address in addresses:
        await _subscribe(browser, address)
        [message] = await _confirmations(browser, address)
        token = _confirm_token(message)
        confirmed = await browser.stranger().http.post(f"{API}/confirm", json={"token": token})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["subscribed"] is True
        tokens[address] = token
    return tokens


async def _draft(browser: Browser, subject: str | None = None, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        f"{ADMIN}/emails",
        json={
            "subject": subject or unique("News"),
            "body": "Three nights in **December**.",
            **fields,
        },
    )
    assert made.status_code == 201, made.text
    found: dict[str, Any] = made.json()
    return found


async def _send(browser: Browser, email_id: str, at: str | None = None) -> dict[str, Any]:
    sent = await browser.http.post(
        f"{ADMIN}/emails/{email_id}/send", json={} if at is None else {"at": at}
    )
    assert sent.status_code == 200, sent.text
    found: dict[str, Any] = sent.json()
    return found


async def _newsletters(browser: Browser, address: str, subject: str) -> list[dict[str, Any]]:
    return [each for each in await browser.mail(address) if each["subject"] == subject]


# --- who may call each route ---------------------------------------------------------------


ADMIN_ROUTES = [
    ("GET", f"{ADMIN}/emails", None),
    ("POST", f"{ADMIN}/emails", {"subject": "x"}),
    ("GET", f"{ADMIN}/emails/{NOBODY}", None),
    ("PATCH", f"{ADMIN}/emails/{NOBODY}", {"version": 1}),
    ("POST", f"{ADMIN}/emails/{NOBODY}/preview", {"body": ""}),
    ("POST", f"{ADMIN}/emails/{NOBODY}/test", None),
    ("POST", f"{ADMIN}/emails/{NOBODY}/send", {}),
    ("POST", f"{ADMIN}/emails/{NOBODY}/cancel", None),
    ("DELETE", f"{ADMIN}/emails/{NOBODY}", None),
    ("GET", f"{ADMIN}/subscribers", None),
    ("POST", f"{ADMIN}/subscribers/{NOBODY}/set-aside", {"why": "bounced"}),
    ("DELETE", f"{ADMIN}/subscribers/{NOBODY}", None),
    ("GET", f"{ADMIN}/set-aside", None),
]


async def test_every_admin_route_needs_its_permission(browser: Browser) -> None:
    stranger = browser.stranger()
    for method, path, body in ADMIN_ROUTES:
        answer = await stranger.http.request(method, path, json=body)
        assert answer.status_code == 401, (method, path, answer.text)
    await browser.as_new("member")
    for method, path, body in ADMIN_ROUTES:
        answer = await browser.http.request(method, path, json=body)
        assert answer.status_code == 403, (method, path, answer.text)
    browser.forget()
    await browser.as_new("member", "admin")
    for method, path, body in ADMIN_ROUTES:
        answer = await browser.http.request(method, path, json=body)
        assert answer.status_code not in (401, 403), (method, path, answer.text)


async def test_the_module_switched_off_is_404_everywhere(browser: Browser) -> None:
    await _owner(browser)
    off = await browser.http.put("/api/kernel/admin/modules/campaigns", json={"on": False})
    assert off.status_code == 200, off.text
    try:
        for method, path, body in [
            ("GET", f"{API}/signup", None),
            ("POST", f"{API}/subscribe", {"email": _address(), "bot": PERSON}),
            ("GET", f"{API}/unsubscribe?token=x", None),
            ("GET", f"{ADMIN}/emails", None),
        ]:
            answer = await browser.http.request(method, path, json=body)
            assert answer.status_code == 404, (method, path, answer.text)
    finally:
        back = await browser.http.put("/api/kernel/admin/modules/campaigns", json={"on": True})
        assert back.status_code == 200, back.text


# --- signing up -------------------------------------------------------------------------------


async def test_a_new_and_a_pending_address_each_get_a_confirmation(browser: Browser) -> None:
    """At most five sign-ups an hour from one address: each test here keeps under it."""
    await _fresh(browser)
    new, pending = _address("new"), _address("pend")
    await _subscribe(browser, pending)
    await browser.advance(601)  # past the wait before a pending address is asked again
    for address in (new, pending):
        await _subscribe(browser, address)
    assert len(await _confirmations(browser, new)) == 1
    assert len(await _confirmations(browser, pending)) == 2


async def test_a_subscribed_and_a_set_aside_address_get_the_same_answer_and_nothing_more(
    browser: Browser,
) -> None:
    await _fresh(browser)
    subscribed, aside = _address("sub"), _address("aside")
    await _subscribed(browser, subscribed, aside)
    [row] = [
        each for each in await _pages(browser, f"{ADMIN}/subscribers") if each["email"] == aside
    ]
    put = await browser.http.post(
        f"{ADMIN}/subscribers/{row['id']}/set-aside", json={"why": "bounced"}
    )
    assert put.status_code == 204, put.text
    await browser.advance(601)
    for address in (subscribed, aside):
        await _subscribe(browser, address)  # 202 {received}, as for a new one
    assert len(await _confirmations(browser, subscribed)) == 1  # its first, from signing up
    assert len(await _confirmations(browser, aside)) == 1


async def test_a_set_aside_address_never_gets_a_confirmation(browser: Browser) -> None:
    await _fresh(browser)
    address = _address()
    tokens = await _subscribed(browser, address)
    left = await browser.stranger().http.post(
        f"{API}/unsubscribe", params={"token": tokens[address]}
    )
    assert left.status_code == 200, left.text
    await _subscribe(browser, address.upper())
    assert len(await _confirmations(browser, address)) == 1


async def test_a_sign_up_the_bot_check_holds_answers_the_same_and_mails_nobody(
    browser: Browser,
) -> None:
    await _fresh(browser)
    address = _address("bot")
    sent = await browser.stranger().http.post(
        f"{API}/subscribe",
        json={"email": address, "bot": {"website": "spam.example", "elapsed_ms": 5000}},
    )
    assert (sent.status_code, sent.json()) == (202, {"received": True})
    assert await _confirmations(browser, address) == []


async def test_sign_ups_closed_is_409_and_the_state_says_so(browser: Browser) -> None:
    await _fresh(browser, signups_open=False)
    try:
        state = await browser.stranger().http.get(f"{API}/signup")
        assert state.json() == {"open": False}
        closed = await browser.stranger().http.post(
            f"{API}/subscribe", json={"email": _address(), "bot": PERSON}
        )
        assert (closed.status_code, closed.json()["code"]) == (409, "campaigns.closed")
    finally:
        await _settings(browser, signups_open=True)
    assert (await browser.stranger().http.get(f"{API}/signup")).json() == {"open": True}


async def test_a_field_s_error_is_422(browser: Browser) -> None:
    refused = await browser.stranger().http.post(
        f"{API}/subscribe", json={"email": "two@a.test, three@b.test", "bot": PERSON}
    )
    assert refused.status_code == 422, refused.text
    assert "body.email" in refused.json()["errors"]


# --- the links --------------------------------------------------------------------------------


async def test_confirm_and_unsubscribe_work_by_token(browser: Browser) -> None:
    await _fresh(browser)
    address = _address()
    tokens = await _subscribed(browser, address)
    token = tokens[address]
    visitor = browser.stranger()
    looked = await visitor.http.get(f"{API}/unsubscribe", params={"token": token})
    assert looked.status_code == 200
    assert looked.json() == {"email_hint": f"{address[0]}…@example.org", "subscribed": True}
    # Opening it changed nothing.
    again = await visitor.http.get(f"{API}/unsubscribe", params={"token": token})
    assert again.json()["subscribed"] is True
    done = await visitor.http.post(f"{API}/unsubscribe", params={"token": token})
    assert done.json() == {"email_hint": looked.json()["email_hint"], "subscribed": False}
    twice = await visitor.http.post(f"{API}/unsubscribe", params={"token": token})
    assert (twice.status_code, twice.json()) == (200, done.json())
    aside = await _pages(browser, f"{ADMIN}/set-aside")
    assert {"email": address, "why": "unsubscribed"} in [
        {"email": row["email"], "why": row["why"]} for row in aside
    ]
    unknown = await visitor.http.get(f"{API}/unsubscribe", params={"token": "not-a-token"})
    assert (unknown.status_code, unknown.json()["code"]) == (404, "campaigns.unknown_link")
    unknown = await visitor.http.post(f"{API}/confirm", json={"token": "not-a-token"})
    assert unknown.status_code == 404


async def test_the_one_click_post_is_taken_from_a_mail_app(browser: Browser) -> None:
    await _fresh(browser)
    address = _address()
    tokens = await _subscribed(browser, address)
    # As Gmail posts it: a form body, no cookie, no Origin and no Sec-Fetch-Site.
    mail_app = browser.stranger()
    mail_app.http.headers.pop("Origin")
    mail_app.http.headers.pop("Sec-Fetch-Site")
    clicked = await mail_app.http.post(
        f"{API}/unsubscribe",
        params={"token": tokens[address]},
        content=b"List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert clicked.status_code == 200, clicked.text
    assert clicked.json()["subscribed"] is False


# --- sending ----------------------------------------------------------------------------------


async def test_a_send_reaches_the_subscribed_once_each_with_their_own_link_and_headers(
    browser: Browser,
) -> None:
    await _fresh(browser)
    one, two, pending, aside = (_address(name) for name in ("one", "two", "pend", "aside"))
    await _subscribed(browser, one, two, aside)
    await _subscribe(browser, pending)
    [row] = [
        each for each in await _pages(browser, f"{ADMIN}/subscribers") if each["email"] == aside
    ]
    await browser.http.post(
        f"{ADMIN}/subscribers/{row['id']}/set-aside", json={"why": "complained"}
    )
    draft = await _draft(browser, preview="Three nights")
    sent = await _send(browser, draft["id"])
    assert sent["status"] in ("sending", "sent")
    await browser.run_job("campaigns.send")
    await browser.run_job("campaigns.send")  # a job run twice sends nobody twice
    links = set()
    for address in (one, two):
        [message] = await _newsletters(browser, address, draft["subject"])
        found = re.search(
            r"Unsubscribe: (\S+/newsletter/unsubscribe\?token=(\S+))", message["text"]
        )
        assert found, message["text"]
        token = found.group(2)
        assert message["headers"] == {
            "List-Unsubscribe": f"<https://mechframe.test/api/campaigns/unsubscribe?token={token}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        assert found.group(1) in message["html"]
        assert "P.O. Box 12, Boston, MA 02101" in message["html"]
        links.add(token)
        visitor = browser.stranger()
        named = await visitor.http.get(f"{API}/unsubscribe", params={"token": token})
        assert named.json()["email_hint"] == f"{address[0]}…@example.org"
    assert len(links) == 2
    assert await _newsletters(browser, aside, draft["subject"]) == []
    assert await _newsletters(browser, pending, draft["subject"]) == []
    shown = await browser.http.get(f"{ADMIN}/emails/{draft['id']}")
    assert (shown.json()["status"], shown.json()["sent_to"]) == ("sent", 2)


async def test_an_address_set_aside_or_unsubscribed_mid_send_is_skipped(browser: Browser) -> None:
    await _fresh(browser, send_per_hour=60)  # one a minute
    people = [_address(f"m{each}") for each in range(3)]
    tokens = await _subscribed(browser, *people)
    draft = await _draft(browser)
    await _send(browser, draft["id"])
    await browser.advance(120)  # the copies other tests queued fall out of the pace's minute
    await browser.run_job("campaigns.send")
    got = [address for address in people if await _newsletters(browser, address, draft["subject"])]
    assert len(got) == 1
    first, second = [address for address in people if address not in got]
    await browser.stranger().http.post(f"{API}/unsubscribe", params={"token": tokens[first]})
    [row] = [
        each for each in await _pages(browser, f"{ADMIN}/subscribers") if each["email"] == second
    ]
    await browser.http.post(f"{ADMIN}/subscribers/{row['id']}/set-aside", json={"why": "bounced"})
    for _ in range(3):
        await browser.advance(61)
        await browser.run_job("campaigns.send")
    assert await _newsletters(browser, first, draft["subject"]) == []
    assert await _newsletters(browser, second, draft["subject"]) == []
    shown = await browser.http.get(f"{ADMIN}/emails/{draft['id']}")
    assert (shown.json()["status"], shown.json()["sent_to"]) == ("sent", 1)
    await _settings(browser, send_per_hour=6000)


async def test_a_scheduled_email_starts_at_its_time_and_cancel_stops_it(browser: Browser) -> None:
    await _fresh(browser)
    address = _address()
    await _subscribed(browser, address)
    soon, later = await _draft(browser), await _draft(browser)
    at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    for draft in (soon, later):
        scheduled = await _send(browser, draft["id"], at)
        assert (scheduled["status"], scheduled["send_at"] is not None) == ("scheduled", True)
    listed = await browser.http.get(f"{ADMIN}/emails")
    assert listed.json()["counts"]["scheduled"] == 2
    assert listed.json()["scheduled"]["id"] in (soon["id"], later["id"])
    back = await browser.http.post(f"{ADMIN}/emails/{later['id']}/cancel")
    assert back.json()["status"] == "draft"
    await browser.run_job("campaigns.send")
    assert await _newsletters(browser, address, soon["subject"]) == []
    await browser.advance(3601)
    await browser.run_jobs()
    await browser.run_job("campaigns.send")
    assert len(await _newsletters(browser, address, soon["subject"])) == 1
    assert await _newsletters(browser, address, later["subject"]) == []


async def test_a_test_goes_only_to_the_person_asking(browser: Browser) -> None:
    await _fresh(browser)
    subscriber = _address()
    await _subscribed(browser, subscriber)
    browser.forget()
    asker = await browser.as_new("member", "admin")
    draft = await _draft(browser)
    tested = await browser.http.post(f"{ADMIN}/emails/{draft['id']}/test")
    assert (tested.status_code, tested.json()) == (200, {"to": asker.email})
    [message] = [
        each for each in await browser.mail(asker.email) if each["subject"].startswith("[Test]")
    ]
    assert message["subject"] == f"[Test] {draft['subject']}"
    assert message["headers"] == {}
    await browser.run_job("campaigns.send")
    assert await _newsletters(browser, subscriber, draft["subject"]) == []
    assert await _newsletters(browser, subscriber, message["subject"]) == []
    shown = await browser.http.get(f"{ADMIN}/emails/{draft['id']}")
    assert (shown.json()["status"], shown.json()["sent_to"]) == ("draft", 0)


async def test_no_postal_address_is_409_before_anything_is_queued(browser: Browser) -> None:
    await _fresh(browser, postal_address="")
    try:
        address = _address()
        await _subscribed(browser, address)
        draft = await _draft(browser)
        refused = await browser.http.post(f"{ADMIN}/emails/{draft['id']}/send", json={})
        assert (refused.status_code, refused.json()["code"]) == (409, "campaigns.no_address")
        await browser.run_job("campaigns.send")
        assert await _newsletters(browser, address, draft["subject"]) == []
        shown = await browser.http.get(f"{ADMIN}/emails/{draft['id']}")
        assert shown.json()["status"] == "draft"
        attention = await browser.http.get("/api/kernel/admin/attention")
        keys = [item["key"] for item in attention.json()["items"]]
        assert "campaigns.no_address" in keys
        listed = await browser.http.get(f"{ADMIN}/emails")
        assert listed.json()["setup"]["has_address"] is False
    finally:
        await _settings(browser, postal_address=ADDRESS)


async def test_with_nobody_subscribed_a_send_is_409(browser: Browser) -> None:
    await _fresh(browser)
    draft = await _draft(browser)
    refused = await browser.http.post(f"{ADMIN}/emails/{draft['id']}/send", json={})
    assert (refused.status_code, refused.json()["code"]) == (409, "campaigns.nobody")


async def test_a_crossed_save_is_409_with_the_email_now_and_a_sent_one_can_t_change(
    browser: Browser,
) -> None:
    await _fresh(browser)
    draft = await _draft(browser)
    first = await browser.http.patch(
        f"{ADMIN}/emails/{draft['id']}", json={"version": draft["version"], "subject": "Mine"}
    )
    assert first.status_code == 200
    assert first.json()["version"] == draft["version"] + 1
    crossed = await browser.http.patch(
        f"{ADMIN}/emails/{draft['id']}", json={"version": draft["version"], "subject": "Theirs"}
    )
    assert (crossed.status_code, crossed.json()["code"]) == (409, "campaigns.changed")
    assert crossed.json()["email"]["subject"] == "Mine"
    await _subscribed(browser, _address())
    await _send(browser, draft["id"])
    await browser.run_job("campaigns.send")
    late = await browser.http.patch(
        f"{ADMIN}/emails/{draft['id']}", json={"version": 99, "subject": "Late"}
    )
    assert (late.status_code, late.json()["code"]) == (409, "campaigns.sent")
    gone = await browser.http.delete(f"{ADMIN}/emails/{draft['id']}")
    assert (gone.status_code, gone.json()["code"]) == (409, "campaigns.not_draft")


async def test_the_preview_is_the_words_and_the_footer(browser: Browser) -> None:
    await _fresh(browser)
    draft = await _draft(browser)
    shown = await browser.http.post(
        f"{ADMIN}/emails/{draft['id']}/preview", json={"body": "Unsaved **words**"}
    )
    assert shown.status_code == 200, shown.text
    html = shown.json()["html"]
    assert "<strong>words</strong>" in html
    assert "Unsubscribe" in html
    assert "P.O. Box 12, Boston, MA 02101" in html


# --- Resend's webhook -------------------------------------------------------------------------


def _signed(body: bytes, delivery: str | None = None, key: bytes = KEY) -> dict[str, str]:
    delivery = delivery or f"msg_{uuid.uuid4().hex}"
    stamp = str(int(time.time()))
    digest = hmac.new(key, f"{delivery}.{stamp}.".encode() + body, hashlib.sha256).digest()
    return {
        "svix-id": delivery,
        "svix-timestamp": stamp,
        "svix-signature": "v1," + base64.b64encode(digest).decode(),
        "Content-Type": "application/json",
    }


def _event(kind: str, address: str, **bounce: str) -> bytes:
    data: dict[str, Any] = {"email_id": str(uuid.uuid4()), "to": [address]}
    if bounce:
        data["bounce"] = bounce
    return json.dumps({"type": kind, "created_at": "2026-11-23T10:00:00Z", "data": data}).encode()


async def _aside_reason(browser: Browser, address: str) -> str | None:
    for row in await _pages(browser, f"{ADMIN}/set-aside"):
        if row["email"] == address:
            return str(row["why"])
    return None


async def test_the_webhook_fails_closed_and_refuses_a_bad_signature_and_a_replay(
    browser: Browser, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _fresh(browser)
    address = _address()
    await _subscribed(browser, address)
    body = _event(
        "email.bounced",
        address,
        type="Permanent",
        subType="General",
        message="550 5.1.1 no such user",
    )
    resend = browser.stranger()
    hook = f"{API}/webhooks/resend"
    unconfigured = await resend.http.post(hook, content=body, headers=_signed(body))
    assert (unconfigured.status_code, unconfigured.json()["code"]) == (
        401,
        "campaigns.bad_signature",
    )
    monkeypatch.setenv("CAMPAIGNS_RESEND_WEBHOOK_SECRET", SECRET)
    for headers in (
        _signed(body, key=b"not the key at all, 32 bytes!!!!"),
        {"Content-Type": "application/json"},
    ):
        refused = await resend.http.post(hook, content=body, headers=headers)
        assert refused.status_code == 401, refused.text
    assert await _aside_reason(browser, address) is None
    good = _signed(body)
    taken = await resend.http.post(hook, content=body, headers=good)
    assert (taken.status_code, taken.json()) == (200, {"received": True})
    assert await _aside_reason(browser, address) == "bounced"
    replayed = await resend.http.post(hook, content=body, headers=good)
    assert (replayed.status_code, replayed.json()["code"]) == (409, "campaigns.replayed")


async def test_a_complaint_sets_aside_and_a_soft_bounce_doesn_t(
    browser: Browser, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _fresh(browser)
    monkeypatch.setenv("CAMPAIGNS_RESEND_WEBHOOK_SECRET", SECRET)
    soft, complained = _address("soft"), _address("spam")
    await _subscribed(browser, soft, complained)
    resend = browser.stranger()
    for body in (
        _event(
            "email.bounced", soft, type="Transient", subType="MailboxFull", message="452 4.2.2 full"
        ),
        _event("email.complained", complained),
    ):
        taken = await resend.http.post(
            f"{API}/webhooks/resend", content=body, headers=_signed(body)
        )
        assert taken.status_code == 200, taken.text
    assert await _aside_reason(browser, soft) is None
    assert await _aside_reason(browser, complained) == "complained"


# --- events from contact and blog -------------------------------------------------------------


async def test_contact_s_news_request_makes_a_pending_subscriber_and_one_confirmation(
    browser: Browser,
) -> None:
    await _fresh(browser)
    address = _address("contact")
    for _ in range(2):
        sent = await browser.stranger().http.post(
            "/api/contact/messages",
            json={
                "name": "Rae",
                "email": address,
                "topic": "question",
                "message": "Could you play a night in March?",
                "wants_news": True,
                "bot": PERSON,
            },
        )
        assert sent.status_code == 202, sent.text
        await browser.run_jobs()
    assert len(await _confirmations(browser, address)) == 1
    [row] = [
        each for each in await _pages(browser, f"{ADMIN}/subscribers") if each["email"] == address
    ]
    assert (row["status"], row["source"], row["name"]) == ("pending", "contact", "Rae")


async def _post(browser: Browser, email_subscribers: bool) -> dict[str, Any]:
    made = await browser.http.post(
        "/api/blog/admin/posts",
        json={
            "title": unique("New song"),
            "summary": "A first listen.",
            "body": "The words.",
            "email_subscribers": email_subscribers,
        },
    )
    assert made.status_code == 201, made.text
    post: dict[str, Any] = made.json()
    live = await browser.http.post(f"/api/blog/admin/posts/{post['id']}/publish", json={})
    assert live.status_code == 200, live.text
    await browser.run_jobs()
    return post


async def test_a_post_published_with_email_subscribers_goes_once_and_one_without_doesn_t(
    browser: Browser,
) -> None:
    await _fresh(browser)
    address = _address("reader")
    await _subscribed(browser, address)
    mailed = await _post(browser, True)
    quiet = await _post(browser, False)
    await browser.run_job("campaigns.send")
    [message] = await _newsletters(browser, address, mailed["title"])
    assert f"https://mechframe.test/blog/{mailed['slug']}" in message["text"]
    assert await _newsletters(browser, address, quiet["title"]) == []
    emails = [row["subject"] for row in await _pages(browser, f"{ADMIN}/emails")]
    assert emails.count(mailed["title"]) == 1
    assert quiet["title"] not in emails


# --- the admin's lists, the attention items and the server copy -------------------------------


async def test_the_lists_count_and_remove_keeps_the_address_set_aside(browser: Browser) -> None:
    await _fresh(browser)
    address = _address()
    await _subscribed(browser, address)
    listed = await browser.http.get(f"{ADMIN}/subscribers", params={"status": "subscribed"})
    [row] = listed.json()["items"]
    assert (row["email"], row["source"], row["status"]) == (address, "form", "subscribed")
    assert listed.json()["counts"]["subscribed"] == 1
    gone = await browser.http.delete(f"{ADMIN}/subscribers/{row['id']}")
    assert gone.status_code == 204
    assert await _aside_reason(browser, address) == "unsubscribed"
    await _subscribe(browser, address)
    assert len(await _confirmations(browser, address)) == 1


async def test_a_bounce_shows_as_the_attention_card(
    browser: Browser, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _fresh(browser)
    monkeypatch.setenv("CAMPAIGNS_RESEND_WEBHOOK_SECRET", SECRET)
    address = _address("dead")
    await _subscribed(browser, address)
    body = _event("email.bounced", address, type="Permanent", subType="NoEmail")
    await browser.stranger().http.post(
        f"{API}/webhooks/resend", content=body, headers=_signed(body)
    )
    listed = await browser.http.get(f"{ADMIN}/emails")
    waiting = listed.json()["waiting"]
    assert waiting["to"] == "/admin/campaigns?tab=set-aside"
    assert "bounced" in waiting["what"]
    attention = await browser.http.get("/api/kernel/admin/attention")
    assert "campaigns.set_aside" in [item["key"] for item in attention.json()["items"]]


@pytest.mark.parametrize("path", ["/newsletter/confirm", "/newsletter/unsubscribe"])
async def test_the_link_pages_answer_noindex_without_their_token(
    browser: Browser, path: str
) -> None:
    page = await browser.stranger().http.get(path, params={"token": "anything"})
    assert page.status_code == 200, page.text
    assert 'name="robots" content="noindex' in page.text
    assert "anything" not in page.text
