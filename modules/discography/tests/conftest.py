"""Fixtures for discography's tests: a session on the migrated test database
(the root conftest's `migrated_url`), an image in the media library for a
cover, a master made by the test itself, and slugs unique to each test, so
tests sharing the database never meet (isolation by unique keys). The
backend's own fixtures are in `backend/conftest.py`; the contract suite reads
only the running app."""

from __future__ import annotations

import io
import math
import uuid
from collections.abc import AsyncIterator

import numpy as np
import pytest_asyncio
import soundfile as sf
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database


@pytest_asyncio.fixture(loop_scope="session")
async def database(migrated_url: str) -> AsyncIterator[Database]:
    db = Database(migrated_url, pool_size=2, max_overflow=2)
    yield db
    await db.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session


def slug() -> str:
    """A slug no other test uses."""
    return f"r-{uuid.uuid4().hex[:12]}"


def master(seconds: float = 3.0, rate: int = 44100, channels: int = 2, fmt: str = "WAV") -> bytes:
    """A master of a rising sine, made here: no file is checked in."""
    t = np.arange(int(seconds * rate)) / rate
    wave = (0.6 * np.sin(2 * math.pi * 330 * t) * np.linspace(0, 1, t.size)).astype("float32")
    out = io.BytesIO()
    sf.write(out, np.stack([wave] * channels, axis=1), rate, format=fmt)
    return out.getvalue()


async def make_image(db: AsyncSession, alt: str = "A cover") -> uuid.UUID:
    """An image in the media library, committed: a row as an upload leaves one."""
    image = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO media_image (id, version, file_version, content_type, sha256, width, "
            "height, bytes, filename, alt, created_at, updated_at) VALUES (:id, 1, 1, "
            "'image/png', :sha, 1200, 1200, 1000, 'cover.png', :alt, now(), now())"
        ),
        {"id": image, "sha": image.hex * 2, "alt": alt},
    )
    await db.commit()
    return image
