"""Fixtures for portfolio's tests: a session on the migrated test database
(the root conftest's `migrated_url`), people to credit the pieces to, roles
holding portfolio's permissions, an image in the media library for a
picture, and slugs unique to each test, so tests sharing the database never
meet (isolation by unique keys). The backend's own fixtures are in
`backend/conftest.py`; the contract suite reads only the running app."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, taxonomy


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


async def make_role(db: AsyncSession, *permissions: str) -> str:
    """A site's own role holding `permissions`, committed: an artist role, say."""
    role = f"r-{uuid.uuid4().hex[:12]}"
    await db.execute(
        text("INSERT INTO auth_role (id, name) VALUES (:id, :name)"),
        {"id": role, "name": f"Role {role}"},
    )
    for key in permissions:
        await db.execute(
            text("INSERT INTO auth_role_permission (role_id, permission) VALUES (:id, :key)"),
            {"id": role, "key": key},
        )
    await db.commit()
    return role


async def make_person(
    db: AsyncSession, name: str | None = None, *, role: str | None = None
) -> uuid.UUID:
    """An account, committed, with a unique address, holding `role` when one is given."""
    person = uuid.uuid4()
    email = f"portfolio-{person.hex[:12]}@example.test"
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


async def make_image(db: AsyncSession, alt: str = "A painting") -> uuid.UUID:
    """An image in the media library, committed: a row as an upload leaves one."""
    image = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO media_image (id, version, file_version, content_type, sha256, width, "
            "height, bytes, filename, alt, created_at, updated_at) VALUES (:id, 1, 1, "
            "'image/png', :sha, 1200, 900, 1000, 'piece.png', :alt, now(), now())"
        ),
        {"id": image, "sha": image.hex * 2, "alt": alt},
    )
    await db.commit()
    return image


async def new_discipline(db: AsyncSession, label: str | None = None, *, position: int = 0) -> str:
    """A discipline of the test's own, committed: its slug. The vocabulary must
    be installed (the backend's fixture, or the app)."""
    found = taxonomy.vocabulary("portfolio_discipline")
    assert found is not None
    term = f"d-{uuid.uuid4().hex[:10]}"
    await taxonomy.create(
        db,
        found,
        slug=term,
        label=label or f"Discipline {term}",
        parent_id=None,
        position=position,
        actor=await make_person(db),
    )
    await db.commit()
    return term
