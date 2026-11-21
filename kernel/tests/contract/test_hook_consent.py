"""Hook 6, consent categories (decision 0052; `dev plans/contracts/hooks.md` §7,
test 6), over HTTP only: `GET /api/kernel/site` lists `media`, the probe's
embed's category, only while the probe is on; `probe-addon` names none. Its
Vitest half, `<ConsentGate>` holding its child until `grant()`, is
`kernel/web/src/consent/consent.test.tsx`."""

from __future__ import annotations

from typing import Any

import pytest

from .conftest import Api

pytestmark = pytest.mark.db

SITE = "/api/kernel/site"


async def _consent(api: Api) -> dict[str, Any]:
    site = await api.http.get(SITE)
    assert site.status_code == 200, site.text
    found: dict[str, Any] = site.json()["consent"]
    return found


async def test_the_site_lists_media_only_while_the_probe_is_on(api: Api) -> None:
    assert await _consent(api) == {"mode": "ask", "categories": ["media"]}

    person = await api.make_user(roles=["owner"], totp=True)
    owner = api.another_browser()
    await owner.signed_in_as(person)
    off = await owner.http.put("/api/kernel/admin/modules/probe", json={"on": False})
    assert off.status_code == 200, off.text
    try:
        # probe-addon needs the probe, so it's off too; it named no category anyway.
        assert await _consent(api) == {"mode": "ask", "categories": []}
    finally:
        back = await owner.http.put("/api/kernel/admin/modules/probe", json={"on": True})
        assert back.status_code == 200, back.text
    assert await _consent(api) == {"mode": "ask", "categories": ["media"]}


async def test_the_embeds_host_stays_in_the_policy_whatever_was_chosen(api: Api) -> None:
    """The CSP doesn't change with consent: the probe's player host is in it
    while the probe is on, with or without the visitor's choice."""
    api.http.cookies.set("__Host-mf_consent", "media", domain=api.http.base_url.host, path="/")
    chosen = (await api.http.get(SITE)).headers["content-security-policy"]
    api.http.cookies.clear()
    plain = (await api.http.get(SITE)).headers["content-security-policy"]
    assert chosen == plain
    assert "frame-src 'self' https://www.youtube-nocookie.com;" in plain
