"""portfolio's migration on its own: taking portfolio away takes what it left
in the kernel's tables and media's with it, and its grants (blog's)."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from harness import migrations
from kernel.db import async_database_url

pytestmark = pytest.mark.db

PIECE = "00000000-0000-0000-0000-0000000000c1"
IMAGE = "00000000-0000-0000-0000-0000000000c2"


async def _run(url: str, *statements: str) -> list[int]:
    engine = create_async_engine(async_database_url(url))
    try:
        async with engine.begin() as connection:
            counts = []
            for statement in statements:
                found = await connection.execute(text(statement), {"piece": PIECE, "image": IMAGE})
                counts.append(found.scalar_one() if statement.startswith("SELECT") else 0)
            return counts
    finally:
        await engine.dispose()


async def test_downgrading_portfolio_removes_its_links_documents_uses_and_grants(
    empty_database_url: str,
) -> None:
    await asyncio.to_thread(
        migrations.upgrade, empty_database_url, "heads", confirm_destructive=True
    )
    await _run(
        empty_database_url,
        "INSERT INTO kernel_vocabulary (id, key, label, hierarchical) VALUES "
        "('00000000-0000-0000-0000-0000000000c3', 'portfolio_discipline', 'Disciplines', false)",
        "INSERT INTO kernel_term (id, vocabulary_id, slug, label) VALUES "
        "('00000000-0000-0000-0000-0000000000c4', '00000000-0000-0000-0000-0000000000c3', "
        "'paintings', 'Paintings')",
        "INSERT INTO kernel_term_link (term_id, content_type, content_id) VALUES "
        "('00000000-0000-0000-0000-0000000000c4', 'portfolio.piece', CAST(:piece AS uuid)), "
        "('00000000-0000-0000-0000-0000000000c4', 'probe.thing', CAST(:piece AS uuid))",
        "INSERT INTO kernel_search_document (content_type, content_id, title, body, path, "
        "language, updated_at) VALUES ('portfolio.piece', CAST(:piece AS uuid), 'Harbour', "
        "'Oil', '/art/piece/harbour', 'english', now())",
        "INSERT INTO media_image (id, version, file_version, content_type, sha256, width, height, "
        "bytes, filename, created_at, updated_at) VALUES (CAST(:image AS uuid), 1, 1, 'image/png', "
        "repeat('c', 64), 640, 480, 1000, 'piece.png', now(), now())",
        "INSERT INTO media_use (id, image_id, owner, label, link, created_at) VALUES "
        "(gen_random_uuid(), CAST(:image AS uuid), 'portfolio.piece:' || :piece, 'Harbour', "
        "'/admin/portfolio', now()), "
        "(gen_random_uuid(), CAST(:image AS uuid), 'blog.post:' || :piece, 'A post', "
        "'/admin/blog/x', now())",
        "INSERT INTO auth_role (id, name) VALUES ('artist', 'Artist')",
        "INSERT INTO auth_role_permission (role_id, permission) VALUES "
        "('artist', 'portfolio.piece.add'), ('artist', 'blog.post.write')",
    )

    await asyncio.to_thread(migrations.downgrade, empty_database_url, "portfolio@base")

    left = await _run(
        empty_database_url,
        "SELECT count(*) FROM kernel_term_link WHERE content_type = 'portfolio.piece'",
        "SELECT count(*) FROM kernel_term_link WHERE content_type = 'probe.thing'",
        "SELECT count(*) FROM kernel_search_document WHERE content_type = 'portfolio.piece'",
        "SELECT count(*) FROM media_use WHERE owner LIKE 'portfolio.piece:%'",
        "SELECT count(*) FROM media_use WHERE owner LIKE 'blog.post:%'",
        "SELECT count(*) FROM auth_role_permission WHERE permission LIKE 'portfolio.%'",
        "SELECT count(*) FROM auth_role_permission "
        "WHERE role_id = 'artist' AND permission = 'blog.post.write'",
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'portfolio_piece'",
    )
    assert left == [0, 1, 0, 0, 1, 0, 1, 0]
