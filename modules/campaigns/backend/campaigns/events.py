"""The events campaigns hears (SPEC.md section 11, decision 0036).

- `contact.news.requested` v1 `{message_id, email, name}`: the address becomes
  pending from the source `contact` and gets the confirmation email, unless
  it's subscribed or set aside already.
- `blog.post.published` v1, with `email_subscribers` true: the post's email,
  its title, its summary when the payload carries one, and a link to its
  path, sent at once (§8, 3).

Each is read into campaigns' own view of the payload (modules don't import
each other), and each delivery's id is kept 7 days (`service.first_time`), so a
second delivery changes nothing.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from campaigns import service
from campaigns.models import MAX_EMAIL
from kernel import email, events, jobs


class NewsRequested(BaseModel):
    """campaigns' view of contact's payload."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    message_id: uuid.UUID
    email: str
    name: str = ""


class PostPublished(BaseModel):
    """campaigns' view of blog's payload: what the email needs of it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    post_id: uuid.UUID
    title: str
    path: str
    email_subscribers: bool
    #: Not in blog's v1 payload: read when a later one carries it.
    summary: str = ""


async def _news(ctx: jobs.Context, event: events.Event) -> None:
    heard = event.parse(NewsRequested)
    address = heard.email.strip()
    if not email.is_address(address) or len(address.lower()) > MAX_EMAIL:
        return
    async with ctx.sessions() as db:
        if not await service.first_time(db, f"event:{event.id}"):
            return
        name = " ".join(heard.name.split())[:200] or None
        await service.request_news(db, address=address, name=name, source="contact")
        await db.commit()


async def _post(ctx: jobs.Context, event: events.Event) -> None:
    heard = event.parse(PostPublished)
    if not heard.email_subscribers or not heard.path.startswith("/"):
        return
    async with ctx.sessions() as db:
        if not await service.first_time(db, f"event:{event.id}"):
            return
        await service.from_post(
            db, post_id=heard.post_id, title=heard.title, summary=heard.summary, path=heard.path
        )
        await db.commit()


NEWS = events.on("contact.news.requested", "campaigns.news_requested")(_news)
POST = events.on("blog.post.published", "campaigns.post_published")(_post)
