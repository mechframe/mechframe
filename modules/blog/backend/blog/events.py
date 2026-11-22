"""blog's events (SPEC.md section 11, decision 0036).

`blog.post.published` goes out once a post, the first time it goes live,
whether it was published at once or went live on its schedule: blog hears
the kernel's `kernel.content.published` for its own type and says it with
the post's After publishing choices, for `community` to post it and
`campaigns` to mail it. `announced_at` keeps it to once: a post unpublished
and published again, or a delivery tried twice, says nothing more.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from blog.models import Post
from kernel import clock, events, jobs, lifecycle

CONTENT_TYPE = "blog.post"


@events.payload("blog.post.published", v=1)
class PostPublished(events.Payload):
    """A post went live for the first time, with its writer's choices for it."""

    post_id: uuid.UUID
    slug: str
    title: str
    #: Its page: /blog/<slug>.
    path: str
    allow_comments: bool
    post_to_community: bool
    email_subscribers: bool


async def _announce(ctx: jobs.Context, event: events.Event) -> None:
    heard = event.parse(events.ContentPublished)
    if heard.type != CONTENT_TYPE:
        return
    async with ctx.sessions() as db:
        post = await db.scalar(select(Post).where(Post.id == heard.id).with_for_update())
        if post is None or post.announced_at is not None or post.status != lifecycle.PUBLISHED:
            return
        post.announced_at = clock.now()
        await events.emit(
            db,
            "blog.post.published",
            PostPublished(
                post_id=post.id,
                slug=post.slug,
                title=post.title,
                path=f"/blog/{post.slug}",
                allow_comments=post.allow_comments,
                post_to_community=post.post_to_community,
                email_subscribers=post.email_subscribers,
            ),
        )
        await db.commit()


ANNOUNCE = events.on("kernel.content.published", "blog.announce_published")(_announce)
