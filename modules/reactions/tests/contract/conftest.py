"""Reactions over HTTP: the harness's test app (`harness.testing`,
HARNESS_TEST_SUPPORT=1) in process, and a browser per test that signs people
in as the kernel's contract suite does (social's small client). A person may
be made unverified, and blog's routes give the posts to react to.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import pyotp
import pytest_asyncio

SITE = "https://mechframe.test"
PASSWORD = "quiet orbit lantern 4471 marsh"


@contextmanager
def _environment(values: dict[str, str]) -> Iterator[None]:
    from kernel.config import reset_config

    before = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    reset_config()
    try:
        yield
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        reset_config()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def reactions_server(migrated_url: str) -> AsyncIterator[httpx.AsyncBaseTransport]:
    from harness.testing import build_test_app

    with _environment({"HARNESS_TEST_SUPPORT": "1"}):
        app = build_test_app(migrated_url)
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
        self._transport = transport
        self._others: list[Browser] = []
        self.http = httpx.AsyncClient(
            transport=transport,
            base_url=SITE,
            headers={"Origin": SITE, "Sec-Fetch-Site": "same-origin"},
            follow_redirects=False,
        )

    async def person(self, *roles: str, verified: bool = True) -> Person:
        email = f"reactions-{uuid.uuid4().hex[:10]}@site.test"
        staff = any(role != "member" for role in roles)
        response = await self.http.post(
            "/api/_test/users",
            json={
                "email": email,
                "password": PASSWORD,
                "verified": verified,
                "roles": list(roles) or ["member"],
                "totp": staff,
            },
        )
        assert response.status_code == 201, response.text
        made = response.json()
        return Person(id=made["id"], email=email, totp_secret=made.get("totp_secret"))

    async def sign_in(self, person: Person) -> None:
        response = await self.http.post(
            "/api/auth/sign-in", json={"email": person.email, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        if body["status"] == "second_factor":
            assert person.totp_secret
            response = await self.http.post(
                "/api/auth/sign-in/second-factor",
                json={"challenge": body["challenge"], "totp": pyotp.TOTP(person.totp_secret).now()},
            )
            assert response.status_code == 200, response.text
            body = response.json()
        assert body["status"] == "signed_in", body

    async def as_new(self, *roles: str, verified: bool = True) -> Person:
        person = await self.person(*roles, verified=verified)
        await self.sign_in(person)
        return person

    def stranger(self) -> Browser:
        """Another visitor to the same site, signed out, with no cookies of this one's."""
        other = Browser(self._transport)
        self._others.append(other)
        return other

    async def close(self) -> None:
        for other in self._others:
            await other.http.aclose()
        await self.http.aclose()

    def forget(self) -> None:
        """Signed out, as a stranger is: no cookies."""
        self.http.cookies.clear()

    async def advance(self, seconds: int) -> None:
        response = await self.http.post("/api/_test/clock", json={"advance": seconds})
        assert response.status_code == 204, response.text

    async def run_job(self, name: str) -> None:
        """A job queued now by name (a scheduled one's run), then every due job."""
        response = await self.http.post("/api/_test/jobs", json={"name": name})
        assert response.status_code in (201, 409), response.text
        await self.run_jobs()

    async def run_jobs(self) -> None:
        response = await self.http.post("/api/_test/jobs/run")
        assert response.status_code == 204, response.text


@pytest_asyncio.fixture(loop_scope="session")
async def browser(reactions_server: httpx.AsyncBaseTransport) -> AsyncIterator[Browser]:
    client = Browser(reactions_server)
    reset = await client.http.post("/api/_test/reset")
    assert reset.status_code == 204, reset.text
    yield client
    await client.close()


def unique(prefix: str = "c") -> str:
    """A name no other test uses."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"
