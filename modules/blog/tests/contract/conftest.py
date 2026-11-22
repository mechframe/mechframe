"""The blog over HTTP: the harness's test app (`harness.testing`,
HARNESS_TEST_SUPPORT=1) in process, the media library's files in a fake S3
(moto) for the covers, and a browser per test that signs people in as the
kernel's contract suite does. The kernel's contract client lists only
`docs/contracts/auth-api.md`'s routes, so blog's tests have this small one."""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import pyotp
import pytest_asyncio
from PIL import Image

SITE = "https://mechframe.test"
PASSWORD = "quiet orbit lantern 4471 marsh"
STORAGE = {
    "STORAGE_ENDPOINT_URL": "https://r2.mechframe.test",
    "STORAGE_ACCESS_KEY_ID": "blog-key-id-AKIA0000",
    "STORAGE_SECRET_ACCESS_KEY": "blog-secret-do-not-print",
    "STORAGE_BUCKET": "blog-private",
    "STORAGE_PUBLIC_BUCKET": "blog-public",
    "STORAGE_PUBLIC_URL": "https://files.mechframe.test",
}


@contextmanager
def _environment(values: dict[str, str]) -> Iterator[None]:
    from kernel import storage
    from kernel.config import reset_config

    before = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    reset_config()
    storage._client.cache_clear()
    try:
        yield
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        reset_config()
        storage._client.cache_clear()


@contextmanager
def _fake_s3() -> Iterator[None]:
    from moto import mock_aws

    from kernel import storage

    with _environment(STORAGE), mock_aws():
        client = storage._client(
            STORAGE["STORAGE_ENDPOINT_URL"],
            "auto",
            STORAGE["STORAGE_ACCESS_KEY_ID"],
            STORAGE["STORAGE_SECRET_ACCESS_KEY"],
        )
        for bucket in (STORAGE["STORAGE_BUCKET"], STORAGE["STORAGE_PUBLIC_BUCKET"]):
            client.create_bucket(
                Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "auto"}
            )
        yield


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def blog_server(migrated_url: str) -> AsyncIterator[httpx.AsyncBaseTransport]:
    from harness.testing import build_test_app

    with _environment({**STORAGE, "HARNESS_TEST_SUPPORT": "1"}):
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
        self.http = httpx.AsyncClient(
            transport=transport,
            base_url=SITE,
            headers={"Origin": SITE, "Sec-Fetch-Site": "same-origin"},
            follow_redirects=False,
        )

    async def person(self, *roles: str) -> Person:
        email = f"blog-{uuid.uuid4().hex[:10]}@site.test"
        staff = any(role != "member" for role in roles)
        response = await self.http.post(
            "/api/_test/users",
            json={
                "email": email,
                "password": PASSWORD,
                "verified": True,
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

    async def as_new(self, *roles: str) -> Person:
        person = await self.person(*roles)
        await self.sign_in(person)
        return person

    async def upload(self, data: bytes, name: str = "photo.png", **kwargs: Any) -> httpx.Response:
        return await self.http.post(
            "/api/media/admin/images", files={"file": (name, data, "image/png")}, **kwargs
        )

    def forget(self) -> None:
        """Signed out, as a stranger is: no cookies."""
        self.http.cookies.clear()

    async def advance(self, seconds: int) -> None:
        response = await self.http.post("/api/_test/clock", json={"advance": seconds})
        assert response.status_code == 204, response.text

    async def run_jobs(self) -> None:
        response = await self.http.post("/api/_test/jobs/run")
        assert response.status_code == 204, response.text


@pytest_asyncio.fixture(loop_scope="session")
async def browser(blog_server: httpx.AsyncBaseTransport) -> AsyncIterator[Browser]:
    with _fake_s3():
        client = Browser(blog_server)
        reset = await client.http.post("/api/_test/reset")
        assert reset.status_code == 204, reset.text
        yield client
        await client.http.aclose()


def unique_image(kind: str = "PNG", size: tuple[int, int] = (600, 360)) -> bytes:
    """An image no other test uploads, under the kernel's 1 MB body limit at this size."""
    noise = Image.effect_noise(size, 60).convert("L")
    tint = Image.new("L", size, uuid.uuid4().int % 256)
    out = io.BytesIO()
    Image.merge("RGB", (noise, tint, noise)).save(out, kind)
    return out.getvalue()


def slug() -> str:
    """A slug no other test uses."""
    return f"p-{uuid.uuid4().hex[:12]}"
