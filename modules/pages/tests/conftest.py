"""Fixtures for the pages module's tests: a session on the migrated test
database (the root conftest's `migrated_url`), people to write the pages, and
addresses unique to each test, so tests sharing the database never meet
(isolation by unique keys). The backend's own fixtures are in
`backend/conftest.py`; the contract suite reads only the running app."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
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


def address() -> str:
    """An address no other test uses."""
    return f"/p-{uuid.uuid4().hex[:12]}"


async def make_person(db: AsyncSession, name: str | None = None) -> uuid.UUID:
    """An account, committed, with a unique address."""
    person = uuid.uuid4()
    email = f"pages-{person.hex[:12]}@example.test"
    await db.execute(
        text(
            "INSERT INTO auth_user (id, email, email_normal, display_name) "
            "VALUES (:id, :email, :email, :name)"
        ),
        {"id": person, "email": email, "name": name},
    )
    await db.commit()
    return person
