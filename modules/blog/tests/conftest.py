"""Fixtures for the blog module's tests: a session on the migrated test
database (the root conftest's `migrated_url`), people to write the posts, an
image in the media library for a cover, and slugs unique to each test, so
tests sharing the database never meet (isolation by unique keys). The
backend's own fixtures are in `backend/conftest.py`; the contract suite reads
only the running app."""

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


def slug() -> str:
    """A slug no other test uses."""
    return f"p-{uuid.uuid4().hex[:12]}"


async def make_person(
    db: AsyncSession, name: str | None = None, *, role: str | None = None
) -> uuid.UUID:
    """An account, committed, with a unique address, holding `role` when one is given."""
    person = uuid.uuid4()
    email = f"blog-{person.hex[:12]}@example.test"
    await db.execute(
        text(
            "INSERT INTO auth_user (id, email, email_normal, display_name) "
            "VALUES (:id, :email, :email, :name)"
        ),
        {"id": person, "email": email, "name": name},
    )
    if role is not None:
        await db.execute(
            text("INSERT INTO auth_user_role (user_id, role_id) VALUES (:id, :role)"),
            {"id": person, "role": role},
        )
    await db.commit()
    return person


async def make_image(db: AsyncSession, alt: str = "A photo") -> uuid.UUID:
    """An image in the media library, committed: a row as an upload leaves one."""
    image = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO media_image (id, version, file_version, content_type, sha256, width, "
            "height, bytes, filename, alt, created_at, updated_at) VALUES (:id, 1, 1, "
            "'image/png', :sha, 1200, 630, 1000, 'cover.png', :alt, now(), now())"
        ),
        {"id": image, "sha": image.hex * 2, "alt": alt},
    )
    await db.commit()
    return image
