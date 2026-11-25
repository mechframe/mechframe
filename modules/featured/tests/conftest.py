"""Fixtures for featured's tests: a session on the migrated test database (the
root conftest's `migrated_url`) and slot keys unique to each test, so tests
sharing the database never meet (isolation by unique keys). The backend's own
fixtures are in `backend/conftest.py`; the contract suite reads only the
running app."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database


@pytest_asyncio.fixture(loop_scope="session")
async def database(migrated_url: str) -> AsyncIterator[Database]:
    db = Database(migrated_url, pool_size=3, max_overflow=2)
    yield db
    await db.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db(database: Database) -> AsyncIterator[AsyncSession]:
    async with database.sessions() as session:
        yield session


def key() -> str:
    """A slot key no other test uses."""
    return f"s-{uuid.uuid4().hex[:12]}"
