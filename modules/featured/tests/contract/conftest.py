"""featured over HTTP: the harness's test app (`harness.testing`,
HARNESS_TEST_SUPPORT=1) in process, with the probe's notes as the things a
slot points at (`probe.note`, hook 11) and the fake YouTube for titles, and a
browser per test that signs people in as the kernel's contract suite does.
This suite reads only the running app: nothing here imports featured."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pyotp
import pytest_asyncio

SITE = "https://mechframe.test"
PASSWORD = "quiet orbit lantern 4471 marsh"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def featured_server(migrated_url: str) -> AsyncIterator[httpx.AsyncBaseTransport]:
    from harness.testing import build_test_app
    from kernel.config import reset_config

    before = os.environ.get("HARNESS_TEST_SUPPORT")
    os.environ["HARNESS_TEST_SUPPORT"] = "1"
    reset_config()
    try:
        app = build_test_app(migrated_url)
    finally:
        if before is None:
            os.environ.pop("HARNESS_TEST_SUPPORT", None)
        else:
            os.environ["HARNESS_TEST_SUPPORT"] = before
        reset_config()
    async with app.router.lifespan_context(app):
        yield httpx.ASGITransport(app=app, raise_app_exceptions=False)


@dataclass
class Person:
    id: str
    email: str
    totp_secret: str | None


class Browser:
    """One cookie jar, same-origin headers, and the test-support routes."""

    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        self.transport = transport
        self.http = httpx.AsyncClient(
            transport=transport,
            base_url=SITE,
            headers={"Origin": SITE, "Sec-Fetch-Site": "same-origin"},
            follow_redirects=False,
            timeout=60,
        )

    async def as_new(self, *roles: str) -> Person:
        email = f"players-{uuid.uuid4().hex[:10]}@site.test"
        staff = any(role != "member" for role in roles)
        made = await self.http.post(
            "/api/_test/users",
            json={
                "email": email,
                "password": PASSWORD,
                "verified": True,
                "roles": list(roles) or ["member"],
                "totp": staff,
            },
        )
        assert made.status_code == 201, made.text
        person = Person(made.json()["id"], email, made.json().get("totp_secret"))
        answer = await self.http.post(
            "/api/auth/sign-in", json={"email": email, "password": PASSWORD}
        )
        assert answer.status_code == 200, answer.text
        body: dict[str, Any] = answer.json()
        if body["status"] == "second_factor":
            assert person.totp_secret
            answer = await self.http.post(
                "/api/auth/sign-in/second-factor",
                json={"challenge": body["challenge"], "totp": pyotp.TOTP(person.totp_secret).now()},
            )
            assert answer.status_code == 200, answer.text
            body = answer.json()
        assert body["status"] == "signed_in", body
        return person

    def forget(self) -> None:
        """Signed out, as a stranger is: no cookies."""
        self.http.cookies.clear()

    async def note(self, title: str, *, published: bool = True) -> str:
        """A probe note, `probe.note`: what a slot points at here."""
        made = await self.http.post(
            "/api/probe/notes", json={"slug": f"n-{uuid.uuid4().hex[:12]}", "title": title}
        )
        assert made.status_code == 201, made.text
        ident: str = made.json()["id"]
        if published:
            done = await self.http.post(f"/api/probe/notes/{ident}/publish")
            assert done.status_code == 204, done.text
        return ident

    async def probe_on(self, on: bool) -> None:
        """The probe switched on or off, by an owner in a browser of their own."""
        owner = Browser(self.transport)
        await owner.as_new("owner")
        answer = await owner.http.put("/api/kernel/admin/modules/probe", json={"on": on})
        assert answer.status_code == 200, answer.text
        await owner.http.aclose()

    async def advance(self, seconds: int) -> None:
        answer = await self.http.post("/api/_test/clock", json={"advance": seconds})
        assert answer.status_code == 204, answer.text


@pytest_asyncio.fixture(loop_scope="session")
async def browser(featured_server: httpx.AsyncBaseTransport) -> AsyncIterator[Browser]:
    client = Browser(featured_server)
    reset = await client.http.post("/api/_test/reset")
    assert reset.status_code == 204, reset.text
    yield client
    await client.http.aclose()


def key() -> str:
    """A slot key no other test uses."""
    return f"s-{uuid.uuid4().hex[:12]}"
