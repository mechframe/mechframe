"""Hook 7, export and erase (decision 0052; `dev plans/contracts/hooks.md` §7,
test 7), over HTTP only: an account asks for a copy of its data, the job
makes it and mails a link, and the link sends the account's own owner to a
5-minute download of a ZIP holding the kernel's file and `probe`'s, never
`probe-addon`'s; another account gets 404; the copy goes after 7 days.
`/api/_test/files` reads the stored ZIP back, since the suite can't reach the
store a signed link points at."""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from .conftest import Api

pytestmark = pytest.mark.db

ASK = "/api/auth/account/export"
LINK = re.compile(r"https?://[^\s]+/api/auth/account/exports/([0-9a-f-]{36})")


async def _signed_in(api: Api) -> tuple[Api, Any]:
    person = await api.make_user()
    browser = api.another_browser()
    await browser.signed_in_as(person)
    return browser, person


async def _note(browser: Api) -> str:
    made = await browser.http.post(
        "/api/probe/notes",
        json={"slug": f"note-{uuid.uuid4().hex[:12]}", "title": "Mine", "body": "Words."},
    )
    assert made.status_code == 201, made.text
    note: str = made.json()["id"]
    return note


async def _asked(api: Api, browser: Api, email: str) -> str:
    asked = await browser.http.post(ASK)
    assert asked.status_code == 202, asked.text
    assert asked.json()["status"] == "queued"
    await api.run_jobs()
    found = LINK.search((await api.last_mail(email))["text"])
    assert found, "no export link mailed"
    assert found.group(1) == asked.json()["id"]
    return f"/api/auth/account/exports/{found.group(1)}"


async def _zip(api: Api, location: str) -> zipfile.ZipFile:
    key = urlsplit(location).path.split("/", 2)[2]  # /<bucket>/<key>
    stored = await api.http.get("/api/_test/files", params={"key": key})
    assert stored.status_code == 200, stored.text
    return zipfile.ZipFile(io.BytesIO(stored.content))


async def test_the_copy_holds_the_kernels_file_and_the_probes_only(api: Api) -> None:
    browser, person = await _signed_in(api)
    note = await _note(browser)
    link = await _asked(api, browser, person.email)

    sent = await browser.http.get(link, follow_redirects=False)
    assert sent.status_code == 303, sent.text
    location = sent.headers["location"]
    assert parse_qs(urlsplit(location).query)["X-Amz-Expires"] == ["300"]

    found = await _zip(api, location)
    assert found.namelist() == ["kernel.json", "probe.json"]  # never probe-addon's
    kernel = json.loads(found.read("kernel.json"))
    assert kernel["account"][0]["email"] == person.email
    assert kernel["activity"][0]["action"] == "auth.data_export_requested"  # newest first
    probe = json.loads(found.read("probe.json"))
    assert [item["id"] for item in probe["notes"]] == [note]


async def test_another_account_gets_404_and_a_visitor_401(api: Api) -> None:
    browser, person = await _signed_in(api)
    link = await _asked(api, browser, person.email)

    stranger, _ = await _signed_in(api)
    other = await stranger.http.get(link, follow_redirects=False)
    assert other.status_code == 404
    assert other.json()["code"] == "auth.export_not_found"
    assert (await api.another_browser().http.get(link, follow_redirects=False)).status_code == 401


async def test_asking_needs_a_recent_sign_in_and_waits_an_hour(api: Api) -> None:
    browser, person = await _signed_in(api)
    await api.advance(11 * 60)
    stale = await browser.http.post(ASK)
    assert stale.status_code == 403
    assert stale.json()["code"] == "auth.step_up_required"

    fresh = api.another_browser()
    await fresh.signed_in_as(person)
    assert (await fresh.http.post(ASK)).status_code == 202
    again = await fresh.http.post(ASK)
    assert again.status_code == 429
    assert again.json()["code"] == "kernel.rate_limited"


async def test_the_copy_goes_after_seven_days(api: Api) -> None:
    browser, person = await _signed_in(api)
    link = await _asked(api, browser, person.email)
    sent = await browser.http.get(link, follow_redirects=False)
    assert sent.status_code == 303
    key = urlsplit(sent.headers["location"]).path.split("/", 2)[2]

    await api.advance(7 * 24 * 3600 + 3600)
    # The hourly prune, now: the suite's jobs/run doesn't tick the scheduler.
    pruned = await api.http.post("/api/_test/jobs", json={"name": "kernel.prune_exports"})
    assert pruned.status_code == 201, pruned.text
    await api.run_jobs()
    again = api.another_browser()
    await again.signed_in_as(person)
    gone = await again.http.get(link, follow_redirects=False)
    assert gone.status_code == 404
    assert (await api.http.get("/api/_test/files", params={"key": key})).status_code == 404
