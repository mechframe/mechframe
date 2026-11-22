"""Fixtures for the media module's tests: a session on the migrated test
database (the root conftest's `migrated_url`), an in-memory public bucket in
place of the kernel's storage, people to upload, and images unique to each
test, so tests sharing the database never meet (isolation by unique keys)."""

from __future__ import annotations

import asyncio
import io
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, audit, storage

PUBLIC = "https://cdn.mechframe.test"


@pytest_asyncio.fixture(loop_scope="session")
async def database(migrated_url: str) -> AsyncIterator[Database]:
    db = Database(migrated_url, pool_size=2, max_overflow=2)
    yield db
    await db.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session


@pytest.fixture(autouse=True)
def media_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit log takes media's actions, as an app with media on does (`audit.install`)."""
    monkeypatch.setattr(audit, "_owners", audit._owners | {"media"})


@dataclass
class Bucket:
    """The public bucket, in memory: what was put, and what was deleted."""

    files: dict[str, bytes] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    on: bool = True
    #: While set and not open, deletes wait for it: a cleanup held back.
    gate: asyncio.Event | None = None

    def under(self, prefix: str) -> list[str]:
        return sorted(key for key in self.files if key.startswith(prefix))


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> Bucket:
    found = Bucket()

    def public_url(key: str) -> str:
        if not found.on:
            raise storage.StorageNotConfigured("Public links are off.")
        return f"{PUBLIC}/{key}"

    async def put(key: str, data: bytes, **_: object) -> storage.StoredFile:
        if not found.on:
            raise storage.StorageNotConfigured("Storage is off.")
        found.files[key] = bytes(data)
        return storage.StoredFile(key=key, size=len(data), content_type="image/png", inline=True)

    async def delete(key: str, **_: object) -> None:
        if found.gate is not None:
            await found.gate.wait()
        found.files.pop(key, None)
        found.deleted.append(key)

    monkeypatch.setattr(storage, "public_url", public_url)
    monkeypatch.setattr(storage, "put", put)
    monkeypatch.setattr(storage, "delete", delete)
    return found


async def make_person(db: AsyncSession, name: str | None = None) -> uuid.UUID:
    """An account, committed, with a unique address."""
    person = uuid.uuid4()
    address = f"media-{person.hex[:12]}@example.test"
    await db.execute(
        text(
            "INSERT INTO auth_user (id, email, email_normal, display_name) "
            "VALUES (:id, :email, :email, :name)"
        ),
        {"id": person, "email": address, "name": name},
    )
    await db.commit()
    return person


def unique_image(kind: str = "PNG", size: tuple[int, int] = (1000, 600)) -> bytes:
    """An image no other test uploads: noise from a fresh seed."""
    noise = Image.effect_noise(size, 60).convert("L")
    tint = Image.new("L", size, uuid.uuid4().int % 256)
    out = io.BytesIO()
    Image.merge("RGB", (noise, tint, noise)).save(out, kind)
    return out.getvalue()
