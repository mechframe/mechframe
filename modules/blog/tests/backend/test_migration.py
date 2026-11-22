"""blog's migration on its own (CodeRabbit on #123): taking the blog away
takes what it left in the kernel's tables and media's with it."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from harness import migrations
from kernel.db import async_database_url

pytestmark = pytest.mark.db

POST = "00000000-0000-0000-0000-0000000000b1"
IMAGE = "00000000-0000-0000-0000-0000000000b2"


async def _run(url: str, *statements: str) -> list[int]:
    engine = create_async_engine(async_database_url(url))
    try:
        async with engine.begin() as connection:
            counts = []
            for statement in statements:
                found = await connection.execute(text(statement), {"post": POST, "image": IMAGE})
                counts.append(found.scalar_one() if statement.startswith("SELECT") else 0)
            return counts
    finally:
        await engine.dispose()


async def test_downgrading_the_blog_removes_its_links_documents_and_uses(
    empty_database_url: str,
) -> None:
    await asyncio.to_thread(
        migrations.upgrade, empty_database_url, "heads", confirm_destructive=True
    )
    await _run(
        empty_database_url,
        "INSERT INTO kernel_vocabulary (id, key, label, hierarchical) VALUES "
        "('00000000-0000-0000-0000-0000000000b3', 'blog_category', 'Categories', false)",
        "INSERT INTO kernel_term (id, vocabulary_id, slug, label) VALUES "
        "('00000000-0000-0000-0000-0000000000b4', '00000000-0000-0000-0000-0000000000b3', 'news', 'News')",
        "INSERT INTO kernel_term_link (term_id, content_type, content_id) VALUES "
        "('00000000-0000-0000-0000-0000000000b4', 'blog.post', CAST(:post AS uuid)), "
        "('00000000-0000-0000-0000-0000000000b4', 'probe.thing', CAST(:post AS uuid))",
        "INSERT INTO kernel_search_document (content_type, content_id, title, body, path, language, "
        "updated_at) VALUES ('blog.post', CAST(:post AS uuid), 'Ten years', 'Words', '/blog/ten-years', "
        "'english', now())",
        "INSERT INTO media_image (id, version, file_version, content_type, sha256, width, height, "
        "bytes, filename, created_at, updated_at) VALUES (CAST(:image AS uuid), 1, 1, 'image/png', "
        "repeat('b', 64), 640, 480, 1000, 'cover.png', now(), now())",
        "INSERT INTO media_use (id, image_id, owner, label, link, created_at) VALUES "
        "(gen_random_uuid(), CAST(:image AS uuid), 'blog.post:' || :post, 'Ten years', '/admin/blog/x', now()), "
        "(gen_random_uuid(), CAST(:image AS uuid), 'pages.page:' || :post, 'About', '/admin/pages/x', now())",
    )

    await asyncio.to_thread(migrations.downgrade, empty_database_url, "blog@base")

    left = await _run(
        empty_database_url,
        "SELECT count(*) FROM kernel_term_link WHERE content_type = 'blog.post'",
        "SELECT count(*) FROM kernel_term_link WHERE content_type = 'probe.thing'",
        "SELECT count(*) FROM kernel_search_document WHERE content_type = 'blog.post'",
        "SELECT count(*) FROM media_use WHERE owner LIKE 'blog.post:%'",
        "SELECT count(*) FROM media_use WHERE owner LIKE 'pages.page:%'",
    )
    assert left == [0, 1, 0, 0, 1]
