"""Hook 6, consent categories (decision 0052; `dev plans/contracts/hooks.md` §7,
test 6), over HTTP only: `GET /api/kernel/site` lists `media` while any module
with a `media` host is on (the probe's embed, `embeds`' players and
`audio-player`'s SoundCloud widget), and none once they're all off;
`probe-addon` names none. Its Vitest half,
`<ConsentGate>` holding its child until `grant()`, is
`kernel/web/src/consent/consent.test.tsx`."""

from __future__ import annotations

from typing import Any

import pytest

from .conftest import Api

pytestmark = pytest.mark.db

SITE = "/api/kernel/site"
#: The modules in the app with a host in `media`.
MEDIA = ("probe", "embeds", "audio-player")


async def _consent(api: Api) -> dict[str, Any]:
    site = await api.http.get(SITE)
    assert site.status_code == 200, site.text
    found: dict[str, Any] = site.json()["consent"]
    return found


def _directive(policy: str, name: str) -> list[str]:
    """The sources of one of the policy's directives."""
    for directive in policy.split(";"):
        words = directive.split()
        if words and words[0] == name:
            return words[1:]
    return []


async def test_the_site_lists_media_while_a_module_with_a_media_host_is_on(api: Api) -> None:
    assert await _consent(api) == {"mode": "ask", "categories": ["media"]}

    person = await api.make_user(roles=["owner"], totp=True)
    owner = api.another_browser()
    await owner.signed_in_as(person)

    async def switch(module: str, on: bool) -> None:
        answer = await owner.http.put(f"/api/kernel/admin/modules/{module}", json={"on": on})
        assert answer.status_code == 200, answer.text

    try:
        await switch("probe", False)
        # embeds' players still wait for media.
        assert await _consent(api) == {"mode": "ask", "categories": ["media"]}
        await switch("embeds", False)
        # audio-player's SoundCloud widget still waits for media.
        assert await _consent(api) == {"mode": "ask", "categories": ["media"]}
        await switch("audio-player", False)
        # probe-addon needs the probe, so it's off too; it named no category anyway.
        assert await _consent(api) == {"mode": "ask", "categories": []}
        await switch("embeds", True)
        # embeds' players alone still wait for media (CodeRabbit on #149).
        assert await _consent(api) == {"mode": "ask", "categories": ["media"]}
    finally:
        for module in MEDIA:
            await switch(module, True)
    assert await _consent(api) == {"mode": "ask", "categories": ["media"]}


async def test_the_embeds_host_stays_in_the_policy_whatever_was_chosen(api: Api) -> None:
    """The CSP doesn't change with consent: the probe's player host is in it
    while the probe is on, with or without the visitor's choice."""
    api.http.cookies.set("__Host-mf_consent", "media", domain=api.http.base_url.host, path="/")
    chosen = (await api.http.get(SITE)).headers["content-security-policy"]
    api.http.cookies.clear()
    plain = (await api.http.get(SITE)).headers["content-security-policy"]
    assert chosen == plain
    assert "https://www.youtube-nocookie.com" in _directive(plain, "frame-src")
