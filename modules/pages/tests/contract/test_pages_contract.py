"""The pages' routes over HTTP only (`dev plans/contracts/pages.md` §2, §7):
who may call each, what each answers, and what the site's server copy says of
a page. Nothing here imports pages."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from .conftest import Browser, address

pytestmark = pytest.mark.db

ADMIN = "/api/pages/admin/pages"
NOBODY = "00000000-0000-0000-0000-000000000001"
UNCHECKED = {"mechframe_unchecked": True}


async def _page(browser: Browser, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        ADMIN, json={"title": "A page", "address": address(), "body": "Some words.", **fields}
    )
    assert made.status_code == 201, made.text
    page: dict[str, Any] = made.json()
    return page


async def _publish(browser: Browser, page_id: str, **body: Any) -> dict[str, Any]:
    published = await browser.http.post(f"{ADMIN}/{page_id}/publish", json=body)
    assert published.status_code == 200, published.text
    page: dict[str, Any] = published.json()
    return page


async def _read(browser: Browser, at: str) -> tuple[int, dict[str, Any]]:
    answer = await browser.http.get("/api/pages/page", params={"address": at})
    return answer.status_code, answer.json()


# --- who may call each route ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", ADMIN, None),
        ("POST", ADMIN, {"title": "x", "address": "/x"}),
        ("GET", f"{ADMIN}/{NOBODY}", None),
        ("PATCH", f"{ADMIN}/{NOBODY}", {"version": 1}),
        ("POST", "/api/pages/admin/preview", {"body": "Hi"}),
        ("POST", f"{ADMIN}/{NOBODY}/publish", {}),
        ("POST", f"{ADMIN}/{NOBODY}/unpublish", None),
        ("DELETE", f"{ADMIN}/{NOBODY}", None),
    ],
)
async def test_signed_out_is_401_and_a_member_is_403(
    browser: Browser, method: str, path: str, body: Any
) -> None:
    signed_out = await browser.http.request(method, path, json=body)
    assert signed_out.status_code == 401, signed_out.text

    await browser.as_new("member")
    member = await browser.http.request(method, path, json=body)
    assert member.status_code == 403, member.text
    assert member.json()["code"] == "kernel.forbidden"


async def test_the_live_page_and_the_menus_are_open_to_anyone(browser: Browser) -> None:
    missing = await browser.http.get("/api/pages/page", params={"address": address()})
    assert (missing.status_code, missing.json()["code"]) == (404, "pages.page_not_found")
    for place in ("header", "footer"):
        menu = await browser.http.get("/api/pages/menu", params={"place": place})
        assert menu.status_code == 200, menu.text
    wrong = await browser.http.get("/api/pages/menu", params={"place": "sidebar"})
    assert wrong.status_code == 422


# --- writing, saving and publishing ------------------------------------------------------------


async def test_an_editor_writes_saves_publishes_unpublishes_and_deletes(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    page = await _page(browser, body="Hello **there**.")
    assert set(page) == {
        "id",
        "title",
        "address",
        "status",
        "in_header",
        "in_footer",
        "menu_order",
        "publish_at",
        "updated_at",
        "updated_by",
        "body",
        "search_title",
        "search_description",
        "published_at",
        "version",
        "moves",
    }
    assert (page["status"], page["version"], page["moves"]) == ("draft", 1, [])
    assert (await _read(browser, page["address"]))[0] == 404  # a draft isn't on the site

    preview = await browser.http.post("/api/pages/admin/preview", json={"body": "# Hi\n\n**Bold**"})
    assert preview.status_code == 200, preview.text
    assert preview.json()["html"] == "<h2>Hi</h2>\n<p><strong>Bold</strong></p>"

    saved = await browser.http.patch(
        f"{ADMIN}/{page['id']}", json={"version": 1, "title": "Hello", "search_title": "Hi there"}
    )
    assert saved.status_code == 200, saved.text
    assert (saved.json()["title"], saved.json()["version"]) == ("Hello", 2)

    live = await _publish(browser, page["id"])
    assert live["status"] == "published"
    status, shown = await _read(browser, page["address"])
    assert status == 200
    assert shown == {
        "title": "Hello",
        "address": page["address"],
        "html": "<p>Hello <strong>there</strong>.</p>",
        "search_title": "Hi there",
        "search_description": "Hello there.",
        "updated_at": shown["updated_at"],
    }

    listed = await browser.http.get(ADMIN)
    assert listed.status_code == 200
    assert page["id"] in [each["id"] for each in listed.json()]

    down = await browser.http.post(f"{ADMIN}/{page['id']}/unpublish")
    assert (down.status_code, down.json()["status"]) == (200, "draft")
    assert (await _read(browser, page["address"]))[0] == 404

    deleted = await browser.http.delete(f"{ADMIN}/{page['id']}")
    assert deleted.status_code == 204
    assert (await browser.http.get(f"{ADMIN}/{page['id']}")).status_code == 404


async def test_a_taken_address_is_409_naming_who_answers_it(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    first = await _page(browser, title="First")

    again = await browser.http.post(ADMIN, json={"title": "Again", "address": first["address"]})
    assert (again.status_code, again.json()["code"]) == (409, "pages.address_taken")
    assert again.json()["page"] == {"id": first["id"], "title": "First"}

    kernel = await browser.http.post(ADMIN, json={"title": "Sign in", "address": "/sign-in"})
    assert (kernel.status_code, kernel.json()["owner"]) == (409, "the kernel")

    moved_onto = await browser.http.patch(
        f"{ADMIN}/{first['id']}", json={"version": 1, "address": "/account"}
    )
    assert (moved_onto.status_code, moved_onto.json()["code"]) == (409, "pages.address_taken")


async def test_an_address_out_of_the_rule_is_refused(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    for wrong in ("/About", "/a/b", "about", "/press--kit"):
        made = await browser.http.post(ADMIN, json={"title": "x", "address": wrong})
        assert made.status_code == 422, (wrong, made.text)


async def test_a_stale_version_is_409_with_the_page_now(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    page = await _page(browser)
    first = await browser.http.patch(f"{ADMIN}/{page['id']}", json={"version": 1, "body": "Theirs"})
    assert first.status_code == 200

    stale = await browser.http.patch(f"{ADMIN}/{page['id']}", json={"version": 1, "body": "Mine"})
    assert (stale.status_code, stale.json()["code"]) == (409, "pages.changed")
    assert (stale.json()["page"]["body"], stale.json()["page"]["version"]) == ("Theirs", 2)


async def test_an_address_change_leaves_a_move_that_never_chains(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    page = await _page(browser)
    first, second, third = page["address"], address(), address()
    await _publish(browser, page["id"])
    for version, to in ((1, second), (2, third)):
        moved = await browser.http.patch(
            f"{ADMIN}/{page['id']}", json={"version": version, "address": to}
        )
        assert moved.status_code == 200, moved.text
    assert sorted(moved.json()["moves"]) == sorted([first, second])

    for old in (first, second):
        assert await _read(browser, old) == (200, {"moved": third})
        site = await browser.http.get(old, extensions=UNCHECKED)
        assert (site.status_code, site.headers["location"]) == (301, third)


async def test_a_scheduled_page_is_live_once_publish_due_runs(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    page = await _page(browser)
    at = datetime.now(UTC) + timedelta(seconds=60)
    scheduled = await _publish(browser, page["id"], at=at.isoformat())
    assert (scheduled["status"], scheduled["publish_at"] is not None) == ("scheduled", True)
    assert (await _read(browser, page["address"]))[0] == 404

    await browser.advance(120)
    queued = await browser.http.post("/api/_test/jobs", json={"name": "kernel.publish_due"})
    assert queued.status_code == 201, queued.text
    await browser.run_jobs()
    assert (await _read(browser, page["address"]))[0] == 200


async def test_each_menu_lists_its_live_pages_in_order(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    second = await _page(browser, title="Second", in_footer=True, menu_order=2)
    first = await _page(browser, title="First", in_footer=True, in_header=True, menu_order=1)
    draft = await _page(browser, title="Draft", in_footer=True, menu_order=0)
    for each in (second, first):
        await _publish(browser, each["id"])
    browser.forget()

    footer = (await browser.http.get("/api/pages/menu", params={"place": "footer"})).json()
    header = (await browser.http.get("/api/pages/menu", params={"place": "header"})).json()
    ours = {first["address"], second["address"], draft["address"]}

    assert [link for link in footer if link["address"] in ours] == [
        {"title": "First", "address": first["address"]},
        {"title": "Second", "address": second["address"]},
    ]
    assert [link["address"] for link in header if link["address"] in ours] == [first["address"]]


# --- the server's copy ---------------------------------------------------------------------------


def _json_ld(html: str) -> list[dict[str, Any]]:
    found = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    return [json.loads(each) for each in found]


async def test_the_server_copy_of_a_live_page_its_moves_and_a_draft(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    page = await _page(browser, title="About us", body="## Who\n\nA crew from **Boston**.")
    draft = await _page(browser)
    await _publish(browser, page["id"])

    served = await browser.http.get(page["address"], extensions=UNCHECKED)
    assert served.status_code == 200, served.text
    html = served.text
    assert "<title>About us · " in html
    assert '<meta name="description" content="Who A crew from Boston." />' in html
    assert "<h1>About us</h1>" in html
    assert "<h2>Who</h2>" in html
    assert "<p>A crew from <strong>Boston</strong>.</p>" in html
    (data,) = [each for each in _json_ld(html) if each.get("@type") == "WebPage"]
    assert (data["name"], data["url"].endswith(page["address"])) == ("About us", True)

    assert (await browser.http.get(draft["address"], extensions=UNCHECKED)).status_code == 404

    sitemap = await browser.http.get("/sitemap.xml", extensions=UNCHECKED)
    assert f"{page['address']}</loc>" in sitemap.text
    assert f"{draft['address']}</loc>" not in sitemap.text
    llms = await browser.http.get("/llms.txt", extensions=UNCHECKED)
    assert "[About us](" in llms.text
