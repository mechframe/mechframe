"""audio-player's one route over HTTP only (`dev plans/contracts/audio-player.md`
§2 and §7): the player's settings are public and cached a minute, follow a save
in Settings, refuse a value out of range, and answer 404 while the module is
off. Nothing here imports audio-player."""

from __future__ import annotations

from typing import Any

import pytest

from .conftest import Browser

pytestmark = pytest.mark.db

READ = "/api/audio-player/settings"
SETTINGS = "/api/kernel/admin/settings/audio-player"
SWITCH = "/api/kernel/admin/modules/audio-player"


async def _save(browser: Browser, **changes: Any) -> int:
    form = await browser.http.get(SETTINGS)
    assert form.status_code == 200, form.text
    saved = await browser.http.put(
        SETTINGS, json={"version": form.json()["version"], "changes": changes}
    )
    return saved.status_code


async def test_the_settings_are_anyones_and_cached_a_minute(browser: Browser) -> None:
    answer = await browser.http.get(READ)
    assert answer.status_code == 200, answer.text
    assert answer.json() == {"autoplay_next": True, "count_after_seconds": 30}
    assert answer.headers["cache-control"] == "public, max-age=60"


async def test_a_save_in_settings_is_what_the_player_reads(browser: Browser) -> None:
    await browser.as_new("member", "owner")
    try:
        assert await _save(browser, autoplay_next=False, count_after_seconds=45) == 200
        browser.forget()
        answer = await browser.http.get(READ)
        assert answer.json() == {"autoplay_next": False, "count_after_seconds": 45}
    finally:
        await browser.as_new("member", "owner")
        assert await _save(browser, autoplay_next=True, count_after_seconds=30) == 200


@pytest.mark.parametrize("seconds", [4, 121])
async def test_a_count_out_of_range_is_refused(browser: Browser, seconds: int) -> None:
    await browser.as_new("member", "owner")
    assert await _save(browser, count_after_seconds=seconds) == 422
    assert (await browser.http.get(READ)).json()["count_after_seconds"] == 30


async def test_the_module_switched_off_is_404(browser: Browser) -> None:
    await browser.as_new("member", "owner")
    off = await browser.http.put(SWITCH, json={"on": False})
    assert off.status_code == 200, off.text
    try:
        assert (await browser.http.get(READ)).status_code == 404
    finally:
        back = await browser.http.put(SWITCH, json={"on": True})
        assert back.status_code == 200, back.text
    assert (await browser.http.get(READ)).status_code == 200
