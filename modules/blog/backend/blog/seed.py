"""blog: its seed data (kernel.seed, hook 4, decision 0052): the categories
News, Poetry and Rap battles, a live post in each, one scheduled a week out
with no cover (so "Needs you" shows its note) and one draft. Each has a fixed
id, so a second run finds them and changes nothing; a slug another post
already has is left to it."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from blog.models import Post
from blog.service import CONTENT_TYPE, VOCABULARY
from kernel import clock, lifecycle, taxonomy
from kernel import seed as seeding

_NAMESPACE = uuid.UUID("8d2b4f61-0c3e-4a7d-b915-2f6e8a1c7d40")
LIVE, SCHEDULED, DRAFT = "live", "scheduled", "draft"
#: Slug, title, category, state, summary and body.
POSTS = (
    (
        "the-collective-is-ten",
        "The collective is ten",
        "news",
        LIVE,
        "Ten years of shows, records and late nights, and what comes next.",
        "Ten years ago a few of us booked a room and played to twelve people.\n\n"
        "## What we made\n\nFour records, a hundred shows and a crew that keeps growing.\n\n"
        "## What's next\n\nA new record in the spring, and a show to mark the year.",
    ),
    (
        "salt-on-the-window",
        "Salt on the window",
        "poetry",
        LIVE,
        "A short poem about the sea in winter.",
        "Salt on the window,\nthe harbour gone grey,\n" "the gulls keep the hours\nwe gave away.",
    ),
    (
        "the-friday-cypher",
        "The Friday cypher",
        "rap-battles",
        LIVE,
        "Eight MCs, three rounds and a crowd that wouldn't sit down.",
        "Eight MCs signed up and three rounds later two were left.\n\n"
        "## The final\n\nIt went to a fourth round, and the crowd called it.",
    ),
    (
        "spring-tour-dates",
        "Spring tour dates",
        "news",
        SCHEDULED,
        "Where we're playing in the spring.",
        "The spring tour starts in March.\n\n## The dates\n\n- To be announced",
    ),
    (
        "notes-from-the-studio",
        "Notes from the studio",
        "news",
        DRAFT,
        "What the new record sounds like so far.",
        "We've been in the studio since the autumn.\n\n## The sound\n\n[A paragraph]",
    ),
)


async def seed(db: AsyncSession, ctx: seeding.Context) -> None:
    editor = await ctx.user("editor")
    for slug, title, category, state, summary, body in POSTS:
        post_id = uuid.uuid5(_NAMESPACE, slug)
        taken = await db.scalar(select(Post.id).where(or_(Post.id == post_id, Post.slug == slug)))
        if taken is not None:
            continue
        post = Post(
            id=post_id,
            version=1,
            title=title,
            slug=slug,
            summary=summary,
            body=body,
            author_id=editor,
            created_at=ctx.now,
            updated_at=ctx.now,
        )
        db.add(post)
        await db.flush()
        await taxonomy.tag(db, CONTENT_TYPE, post.id, VOCABULARY, [category])
        if state == LIVE:
            post.published_at = ctx.now  # publish keeps it: the seed's own fixed instant
            await lifecycle.publish(db, post)
        elif state == SCHEDULED:
            # A week from the day it runs, as the kernel's clock has it: always to come.
            await lifecycle.schedule(db, post, clock.now() + timedelta(days=7))
