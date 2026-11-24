"""Fixtures for audio-player's tests: a session on the migrated test database
(the root conftest's `migrated_url`). Every test counts plays of items it makes
up, so tests sharing the database never meet (isolation by unique keys); a test
that needs a day of its own picks one no other test uses."""

from __future__ import annotations

import random
import uuid
from collections.abc import AsyncIterator
from datetime import date, timedelta

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database


@pytest_asyncio.fixture(loop_scope="session")
async def database(migrated_url: str) -> AsyncIterator[Database]:
    db = Database(migrated_url, pool_size=4, max_overflow=2)
    yield db
    await db.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session


def item() -> uuid.UUID:
    """An item no other test counts."""
    return uuid.uuid4()


def far_day() -> date:
    """A day centuries from now, which no other test (and no prune) touches."""
    return date(2400, 1, 1) + timedelta(days=random.randrange(200_000))
