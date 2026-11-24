"""discography over HTTP: the harness's test app (`harness.testing`,
HARNESS_TEST_SUPPORT=1) in process, the site's two buckets in a fake S3
(moto) for the masters, the stream files and the covers, and a browser per
test that signs people in as the kernel's contract suite does. As blog's
contract suite, this one reads only the running app."""

from __future__ import annotations

import io
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import numpy as np
import pyotp
import pytest_asyncio
import soundfile as sf
from PIL import Image

SITE = "https://mechframe.test"
PASSWORD = "quiet orbit lantern 4471 marsh"
FILES = "https://files.mechframe.test"
STORAGE = {
    "STORAGE_ENDPOINT_URL": "https://r2.mechframe.test",
    "STORAGE_ACCESS_KEY_ID": "music-key-id-AKIA0000",
    "STORAGE_SECRET_ACCESS_KEY": "music-secret-do-not-print",
    "STORAGE_BUCKET": "music-private",
    "STORAGE_PUBLIC_BUCKET": "music-public",
    "STORAGE_PUBLIC_URL": FILES,
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
async def music_server(migrated_url: str) -> AsyncIterator[httpx.AsyncBaseTransport]:
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
            timeout=120,
        )

    async def person(self, *roles: str) -> Person:
        email = f"music-{uuid.uuid4().hex[:10]}@site.test"
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

    async def upload_image(self, data: bytes) -> httpx.Response:
        return await self.http.post(
            "/api/media/admin/images", files={"file": ("cover.png", data, "image/png")}
        )

    async def upload_track(
        self, release_id: str, data: bytes, name: str = "Night Drive.wav"
    ) -> httpx.Response:
        return await self.http.post(
            f"/api/discography/admin/releases/{release_id}/tracks/upload",
            files={"file": (name, data, "application/octet-stream")},
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
async def browser(music_server: httpx.AsyncBaseTransport) -> AsyncIterator[Browser]:
    with _fake_s3():
        client = Browser(music_server)
        reset = await client.http.post("/api/_test/reset")
        assert reset.status_code == 204, reset.text
        yield client
        await client.http.aclose()


def unique_image(size: tuple[int, int] = (600, 600)) -> bytes:
    """A cover no other test uploads, under the kernel's 1 MB body limit at this size."""
    noise = Image.effect_noise(size, 60).convert("L")
    tint = Image.new("L", size, uuid.uuid4().int % 256)
    out = io.BytesIO()
    Image.merge("RGB", (noise, tint, noise)).save(out, "PNG")
    return out.getvalue()


def silence(seconds: float, rate: int = 1000) -> bytes:
    """A FLAC of digital silence, written a block at a time: an hour of it is a
    few kilobytes, so a master over the hour costs the test nothing to send."""
    out = io.BytesIO()
    block = np.zeros(rate * 60, dtype="int16")
    with sf.SoundFile(out, "w", rate, 1, "PCM_16", format="FLAC") as written:
        left = int(seconds * rate)
        while left > 0:
            written.write(block[: min(left, block.size)])
            left -= block.size
    return out.getvalue()


def slug() -> str:
    """A slug no other test uses."""
    return f"r-{uuid.uuid4().hex[:12]}"
