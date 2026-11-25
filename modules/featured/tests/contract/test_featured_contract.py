"""featured's routes over HTTP only (`dev plans/contracts/featured.md` §2, §7):
who may call each, the public read's cache header and its 404, a list saved
and read back live, an item hidden, gone and its module off, the picker,
pasted links titled by the fake YouTube, and the conflict. Nothing here
imports featured."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from .conftest import Browser, key

pytestmark = pytest.mark.db

API = "/api/featured"
SLOTS = f"{API}/admin/slots"
SETTINGS = "/api/kernel/admin/settings/featured"
VIDEO = "dQw4w9WgXcQ"
KINDS = [{"key": "music-video", "label": "Music video"}, {"key": "poetry", "label": "Poetry"}]


async def _slot(browser: Browser, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        SLOTS,
        json={
            "key": key(),
            "label": "Spotlight",
            "accepts": ["probe.note", "youtube"],
            "kinds": KINDS,
            **fields,
        },
    )
    assert made.status_code == 201, made.text
    slot: dict[str, Any] = made.json()
    return slot


async def _put(browser: Browser, slot: dict[str, Any], *items: dict[str, Any]) -> Any:
    return await browser.http.put(
        f"{SLOTS}/{slot['key']}/placements", json={"version": slot["version"], "items": list(items)}
    )


async def _saved(browser: Browser, slot: dict[str, Any], *items: dict[str, Any]) -> dict[str, Any]:
    answer = await _put(browser, slot, *items)
    assert answer.status_code == 200, answer.text
    saved: dict[str, Any] = answer.json()
    return saved


def _note(ident: str, **more: Any) -> dict[str, Any]:
    return {"ref": {"type": "probe.note", "id": ident}, **more}


def _link(title: str = "Hook It Up", **more: Any) -> dict[str, Any]:
    return {"link": {"url": f"https://youtu.be/{VIDEO}", "title": title, **more}}


async def _live(browser: Browser, slot_key: str) -> list[str]:
    answer = await browser.http.get(f"{API}/slots/{slot_key}")
    assert answer.status_code == 200, answer.text
    return [
        (each["ref"] or {}).get("title") or each["link"]["title"] for each in answer.json()["items"]
    ]


# --- who may call each route ---------------------------------------------------------------


PLACE_ROUTES = [
    ("GET", SLOTS),
    ("GET", f"{SLOTS}/{{key}}"),
    ("PUT", f"{SLOTS}/{{key}}/placements"),
    ("GET", f"{SLOTS}/{{key}}/pick?type=probe.note"),
    ("POST", f"{API}/admin/youtube"),
]
SLOT_ROUTES = [
    ("POST", SLOTS),
    ("PATCH", f"{SLOTS}/{{key}}"),
    ("DELETE", f"{SLOTS}/{{key}}"),
]
BODIES = {
    "PUT": {"version": 1, "items": []},
    "POST": {"urls": [f"https://youtu.be/{VIDEO}"]},
    "PATCH": {"version": 1, "label": "Renamed"},
}


async def _call(browser: Browser, method: str, path: str, slot_key: str) -> int:
    body = BODIES.get(method)
    if path == SLOTS and method == "POST":
        body = {"key": key(), "label": "New", "accepts": ["youtube"]}
    answer = await browser.http.request(method, path.format(key=slot_key), json=body)
    return answer.status_code


async def test_who_may_call_each_route(browser: Browser) -> None:
    await browser.as_new("admin")
    slot = await _slot(browser)
    browser.forget()
    for method, path in PLACE_ROUTES + SLOT_ROUTES:
        assert await _call(browser, method, path, slot["key"]) == 401, (method, path)
    await browser.as_new("member")
    for method, path in PLACE_ROUTES + SLOT_ROUTES:
        assert await _call(browser, method, path, slot["key"]) == 403, (method, path)
    browser.forget()
    await browser.as_new("editor")
    for method, path in PLACE_ROUTES:
        assert await _call(browser, method, path, slot["key"]) == 200, (method, path)
    for method, path in SLOT_ROUTES:
        assert await _call(browser, method, path, slot["key"]) == 403, (method, path)
    browser.forget()
    await browser.as_new("admin")
    fresh = await _slot(browser)
    assert await _call(browser, "PATCH", SLOT_ROUTES[1][1], fresh["key"]) == 200
    assert await _call(browser, "DELETE", SLOT_ROUTES[2][1], fresh["key"]) == 204
    assert await _call(browser, "POST", SLOTS, "") == 201


async def test_the_public_read_is_cached_a_minute_and_a_missing_key_is_404(
    browser: Browser,
) -> None:
    await browser.as_new("admin")
    slot = await _slot(browser)
    browser.forget()
    answer = await browser.http.get(f"{API}/slots/{slot['key']}")
    assert answer.status_code == 200
    assert answer.headers["cache-control"] == "public, max-age=60"
    assert answer.json() == {"key": slot["key"], "label": "Spotlight", "kinds": KINDS, "items": []}
    missing = await browser.http.get(f"{API}/slots/{key()}")
    assert (missing.status_code, missing.json()["code"]) == (404, "featured.slot_not_found")


# --- a list, saved and read --------------------------------------------------------------------


async def test_a_list_saved_is_live_at_once_in_order(browser: Browser) -> None:
    await browser.as_new("admin")
    slot = await _slot(browser)
    first, draft, later = (
        await browser.note("Catalyst (full album)"),
        await browser.note("A draft", published=False),
        await browser.note("Gather Around"),
    )
    starts = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    saved = await _saved(
        browser,
        slot,
        _note(first),
        _note(draft),
        _note(later, starts_at=starts),
        _link(kind="poetry"),
    )
    assert [each["state"] for each in saved["items"]] == ["live", "hidden", "next", "live"]
    assert saved["counts"] == {"live": 2, "scheduled": 1}
    assert saved["now"]["title"] == "Catalyst (full album)"
    assert saved["items"][3]["link"] == {
        "url": f"https://www.youtube.com/watch?v={VIDEO}",
        "video_id": VIDEO,
        "title": "Hook It Up",
        "kind": "poetry",
    }
    browser.forget()
    answer = await browser.http.get(f"{API}/slots/{slot['key']}")
    items = answer.json()["items"]
    assert [each["ref"]["title"] if each["ref"] else each["link"]["title"] for each in items] == [
        "Catalyst (full album)",
        "Hook It Up",
    ]
    assert items[0]["ref"]["path"].startswith("/probe/notes/")
    await browser.advance(3 * 24 * 3600)
    assert await _live(browser, slot["key"]) == [
        "Catalyst (full album)",
        "Gather Around",
        "Hook It Up",
    ]


async def test_an_item_unpublished_gone_or_its_module_off(browser: Browser) -> None:
    await browser.as_new("admin")
    slot = await _slot(browser)
    unpublished, gone, off = (
        await browser.note("Unpublished"),
        await browser.note("Gone"),
        await browser.note("Off"),
    )
    saved = await _saved(browser, slot, _note(unpublished), _note(gone), _note(off))
    assert (await browser.http.post(f"/api/probe/notes/{unpublished}/unpublish")).status_code == 204
    assert (await browser.http.delete(f"/api/probe/notes/{gone}")).status_code == 204
    read = (await browser.http.get(f"{SLOTS}/{slot['key']}")).json()
    assert [each["state"] for each in read["items"]] == ["hidden", "removed", "live"]
    assert read["items"][1]["ref"] is None
    assert read["items"][1]["removed"] is True
    assert await _live(browser, slot["key"]) == ["Off"]
    await browser.probe_on(False)
    try:
        read = (await browser.http.get(f"{SLOTS}/{slot['key']}")).json()
        assert [each["state"] for each in read["items"]] == ["hidden", "hidden", "hidden"]
        assert await _live(browser, slot["key"]) == []
        # A save keeps what its module's off holds; a new one can't be added.
        kept = [{"id": each["id"], "ref": each["item"]} for each in read["items"]]
        again = await _saved(browser, read, *kept)
        assert len(again["items"]) == 3
        refused = await _put(browser, again, *kept, _note(str(uuid.uuid4())))
        assert (refused.status_code, refused.json()["code"]) == (422, "featured.not_accepted")
        picked = await browser.http.get(
            f"{SLOTS}/{slot['key']}/pick", params={"type": "probe.note"}
        )
        assert (picked.status_code, picked.json()["code"]) == (422, "featured.not_accepted")
        listed = (await browser.http.get(SLOTS)).json()
        assert "probe.note" not in {each["type"] for each in listed["types"]}
    finally:
        await browser.probe_on(True)
    read = (await browser.http.get(f"{SLOTS}/{slot['key']}")).json()
    # Back on, the gone one is left out at the next save.
    kept = [{"id": each["id"], "ref": each["item"]} for each in read["items"]]
    after = await _saved(browser, read, *kept)
    assert [each["ref"]["title"] for each in after["items"]] == ["Unpublished", "Off"]
    assert saved["items"][2]["id"] == after["items"][1]["id"]


async def test_the_refusals_and_the_conflict(browser: Browser) -> None:
    await browser.as_new("editor")
    admin = Browser(browser.transport)
    await admin.as_new("admin")
    slot = await _slot(admin)
    note = await browser.note("A note")
    cases = [
        (_note(str(uuid.uuid4())), "featured.not_found"),
        ({"ref": {"type": "blog.post", "id": note}}, "featured.not_accepted"),
        ({"link": {"url": "https://vimeo.com/1", "title": "A video"}}, "featured.not_youtube"),
        (_link(title=" "), "featured.no_title"),
        (_link(title="x" * 201), "featured.no_title"),
        (_link(kind="rap-battle"), "featured.unknown_kind"),
        (
            _note(note, starts_at="2026-12-02T00:00:00Z", ends_at="2026-12-01T00:00:00Z"),
            "featured.bad_dates",
        ),
        (
            _note(note, starts_at="2026-12-01T00:00:00Z", ends_at="2026-12-01T00:00:00Z"),
            "featured.bad_dates",
        ),
    ]
    for body, code in cases:
        answer = await _put(browser, slot, body)
        assert (answer.status_code, answer.json()["code"]) == (422, code), answer.text
        assert answer.json()["errors"]
    many = await _put(browser, slot, *[_note(note)] * 101)
    assert (many.status_code, many.json()["code"]) == (422, "featured.too_many")
    saved = await _saved(browser, slot, _note(note))
    stale = await _put(browser, slot, _note(note))
    assert (stale.status_code, stale.json()["code"]) == (409, "featured.changed")
    assert stale.json()["slot"]["version"] == saved["version"]
    assert [each["ref"]["title"] for each in stale.json()["slot"]["items"]] == ["A note"]
    await admin.http.aclose()


# --- slots -------------------------------------------------------------------------------------


async def test_slots_their_settings_and_whats_in_use(browser: Browser) -> None:
    await browser.as_new("admin")
    slot = await _slot(browser)
    taken = await browser.http.post(
        SLOTS, json={"key": slot["key"], "label": "Again", "accepts": ["youtube"]}
    )
    assert (taken.status_code, taken.json()["code"]) == (409, "featured.key_taken")
    unknown = await browser.http.post(
        SLOTS, json={"key": key(), "label": "Shop", "accepts": ["shop.product"]}
    )
    assert (unknown.status_code, unknown.json()["code"]) == (422, "featured.unknown_type")
    saved = await _saved(browser, slot, _link(kind="poetry"))
    in_use = await browser.http.patch(
        f"{SLOTS}/{slot['key']}", json={"version": saved["version"], "accepts": ["probe.note"]}
    )
    assert (in_use.status_code, in_use.json()["code"]) == (409, "featured.in_use")
    changed = await browser.http.patch(
        f"{SLOTS}/{slot['key']}",
        json={
            "version": saved["version"],
            "label": "Videos",
            "kinds": KINDS[1:],
            "on_dashboard": True,
        },
    )
    assert changed.status_code == 200, changed.text
    assert (changed.json()["label"], changed.json()["kinds"], changed.json()["on_dashboard"]) == (
        "Videos",
        KINDS[1:],
        True,
    )
    listed = (await browser.http.get(SLOTS)).json()
    mine = next(each for each in listed["items"] if each["key"] == slot["key"])
    assert mine["counts"] == {"live": 1, "scheduled": 0}
    assert {"type": "probe.note", "label": "Notes"} in listed["types"]
    assert (await browser.http.delete(f"{SLOTS}/{slot['key']}")).status_code == 204
    assert (await browser.http.get(f"{API}/slots/{slot['key']}")).status_code == 404


# --- the picker and the links --------------------------------------------------------------------


async def test_the_picker_finds_drafts_too_newest_edit_first(browser: Browser) -> None:
    await browser.as_new("editor")
    admin = Browser(browser.transport)
    await admin.as_new("admin")
    slot = await _slot(admin)
    word = uuid.uuid4().hex[:8]
    await browser.note(f"Draft {word}", published=False)
    await browser.advance(5)
    await browser.note(f"Live {word}")
    page = await browser.http.get(
        f"{SLOTS}/{slot['key']}/pick", params={"type": "probe.note", "q": word}
    )
    assert page.status_code == 200, page.text
    assert [(each["title"], each["live"]) for each in page.json()["items"]] == [
        (f"Live {word}", True),
        (f"Draft {word}", False),
    ]
    wrong = await browser.http.get(f"{SLOTS}/{slot['key']}/pick", params={"type": "youtube"})
    assert (wrong.status_code, wrong.json()["code"]) == (422, "featured.not_accepted")
    await admin.http.aclose()


async def test_pasted_links_are_titled_by_youtube_while_the_setting_is_on(browser: Browser) -> None:
    await browser.as_new("admin")
    told = await browser.http.post(
        "/api/_test/youtube",
        json={"titles": {VIDEO: "Hook It Up (Official Video)"}, "down": ["abcdefghijk"]},
    )
    assert told.status_code == 204
    urls = [
        f"https://youtu.be/{VIDEO}?t=5",
        "https://www.youtube.com/shorts/abcdefghijk",
        "https://vimeo.com/2",
    ]
    answer = await browser.http.post(f"{API}/admin/youtube", json={"urls": urls})
    assert answer.status_code == 200, answer.text
    assert answer.json() == {
        "items": [
            {
                "url": f"https://www.youtube.com/watch?v={VIDEO}",
                "video_id": VIDEO,
                "title": "Hook It Up (Official Video)",
            },
            {
                "url": "https://www.youtube.com/watch?v=abcdefghijk",
                "video_id": "abcdefghijk",
                "title": None,
            },
        ],
        "refused": [{"url": "https://vimeo.com/2", "reason": "featured.not_youtube"}],
    }
    asked = (await browser.http.get("/api/_test/youtube")).json()["asked"]
    assert len(asked) == 2
    assert all(each.startswith("https://www.youtube.com/oembed?") for each in asked)
    form = (await browser.http.get(SETTINGS)).json()
    off = await browser.http.put(
        SETTINGS, json={"version": form["version"], "changes": {"oembed_titles": False}}
    )
    assert off.status_code == 200, off.text
    quiet = await browser.http.post(f"{API}/admin/youtube", json={"urls": urls[:1]})
    assert quiet.json()["items"][0]["title"] is None
    assert len((await browser.http.get("/api/_test/youtube")).json()["asked"]) == 2
    form = (await browser.http.get(SETTINGS)).json()
    back = await browser.http.put(
        SETTINGS, json={"version": form["version"], "changes": {"oembed_titles": True}}
    )
    assert back.status_code == 200, back.text
    too_many = await browser.http.post(f"{API}/admin/youtube", json={"urls": urls[:1] * 21})
    assert too_many.status_code == 422
