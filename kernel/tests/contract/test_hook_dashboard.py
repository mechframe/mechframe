"""Hook 8, dashboard cards (decision 0052; `dev plans/contracts/hooks.md` §7,
test 8), over HTTP only, on the probe: its setup step, "Set the probe's
count", flips to done the moment the setting is saved; its "Needs you" item
shows only to those who hold `kernel.settings.manage` (an admin, not an
editor); and a module switched off lists neither."""

from __future__ import annotations

from typing import Any

import pytest

from .conftest import Api

pytestmark = pytest.mark.db

SETUP = "/api/kernel/admin/setup"
NEEDS = "/api/kernel/admin/attention"
PROBE_SETTINGS = "/api/kernel/admin/settings/probe"
STEP = "probe.count"
ITEM = "probe.waiting"


async def _staff(api: Api, role: str) -> Api:
    person = await api.make_user(roles=[role], totp=True)
    browser = api.another_browser()
    await browser.signed_in_as(person)
    return browser


async def _count(admin: Api, count: int) -> None:
    form = await admin.http.get(PROBE_SETTINGS)
    assert form.status_code == 200, form.text
    saved = await admin.http.put(
        PROBE_SETTINGS, json={"version": form.json()["version"], "changes": {"count": count}}
    )
    assert saved.status_code == 200, saved.text


async def _steps(browser: Api) -> dict[str, dict[str, Any]]:
    found = await browser.http.get(SETUP)
    assert found.status_code == 200, found.text
    return {step["key"]: step for step in found.json()["items"]}


async def _needs(browser: Api) -> list[str]:
    found = await browser.http.get(NEEDS)
    assert found.status_code == 200, found.text
    return [item["key"] for item in found.json()["items"]]


async def test_a_setup_step_flips_to_done_as_soon_as_it_is(api: Api) -> None:
    admin = await _staff(api, "admin")
    await _count(admin, 1)
    step = (await _steps(admin))[STEP]
    assert step == {
        "key": STEP,
        "title": "Set the probe's count",
        "why": step["why"],
        "link": "/admin/settings/probe",
        "done": False,
    }
    await _count(admin, 2)
    assert (await _steps(admin))[STEP]["done"] is True
    await _count(admin, 1)
    assert (await _steps(admin))[STEP]["done"] is False


async def test_steps_and_items_show_only_to_their_permissions_holders(api: Api) -> None:
    admin = await _staff(api, "admin")
    editor = await _staff(api, "editor")
    assert ITEM in await _needs(admin)
    assert STEP in await _steps(admin)
    assert ITEM not in await _needs(editor)
    # None of the kernel's or the probe's: a real module's step (media's) may name a permission an editor holds.
    assert [key for key in await _steps(editor) if key.startswith(("kernel.", "probe."))] == []


async def test_a_module_switched_off_lists_neither(api: Api) -> None:
    owner = await _staff(api, "owner")
    assert STEP in await _steps(owner)
    off = await owner.http.put("/api/kernel/admin/modules/probe", json={"on": False})
    assert off.status_code == 200, off.text
    try:
        assert STEP not in await _steps(owner)
        assert ITEM not in await _needs(owner)
    finally:
        back = await owner.http.put("/api/kernel/admin/modules/probe", json={"on": True})
        assert back.status_code == 200, back.text
    assert ITEM in await _needs(owner)
