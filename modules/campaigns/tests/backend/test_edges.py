"""The newsletter's edges: pages and their cursors, the listeners' guards, the
jobs as the worker runs them, other shapes of report, and the server copy."""

from __future__ import annotations

import email as mail
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from campaigns import bounces, events, jobs, server_copy, service
from campaigns.models import Email, SetAside, Subscriber
from campaigns.schemas import NewCampaignEmail
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, Problem, clock
from kernel import events as kernel_events

from .test_bounces import arf

pytestmark = pytest.mark.db


class Ctx:
    """What a job gets, as far as campaigns' jobs read it."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def sessions(self) -> Any:
        @asynccontextmanager
        async def opened() -> AsyncIterator[AsyncSession]:
            async with self.database.sessions() as session:
                yield session

        return opened()


def _event(payload: dict[str, Any], event_id: uuid.UUID | None = None) -> kernel_events.Event:
    return kernel_events.Event(
        id=event_id or uuid.uuid4(),
        name="x.y.z",
        v=1,
        emitted_at=datetime.now(UTC),
        payload=payload,
    )


def _address(name: str = "fan") -> str:
    return f"{name}-{uuid.uuid4().hex[:10]}@example.org"


# --- pages and cursors -----------------------------------------------------------------------


async def test_each_list_pages_by_its_cursor(db: AsyncSession) -> None:
    for each in range(3):
        await service.create(db, NewCampaignEmail(subject=f"Page {each}"), by=None)
        await service.request_news(db, address=_address(f"p{each}"), name=None, source="form")
        await service.set_aside(db, _address(f"a{each}"), "bounced", "address: 5.1.1")
    await db.commit()
    for read in (
        lambda cursor: service.emails_page(db, "all", cursor, 1),
        lambda cursor: service.subscribers_page(db, "pending", cursor, 1),
        lambda cursor: service.set_aside_page(db, cursor, 1),
    ):
        seen: list[str] = []
        cursor = None
        while True:
            page = await read(cursor)
            assert len(page["items"]) <= 1
            seen += [str(item.get("id") or item.get("email")) for item in page["items"]]
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert len(seen) == len(set(seen)) >= 3


@pytest.mark.parametrize("cursor", ["nonsense", "12", "x.y", "99999999999999999999999.ab"])
async def test_a_cursor_that_isn_t_one_is_422(db: AsyncSession, cursor: str) -> None:
    for read in (
        service.emails_page(db, "all", cursor),
        service.subscribers_page(db, "all", cursor),
        service.set_aside_page(db, cursor),
    ):
        with pytest.raises(Problem) as refused:
            await read
        assert refused.value.status == 422


async def test_the_tabs_filter_the_emails(db: AsyncSession) -> None:
    row = await service.create(db, NewCampaignEmail(subject="Tabbed"), by=None)
    await db.commit()
    drafts = await service.emails_page(db, "draft", None, 100)
    sent = await service.emails_page(db, "sent", None, 100)
    assert str(row.id) in [item["id"] for item in drafts["items"]]
    assert str(row.id) not in [item["id"] for item in sent["items"]]
    assert drafts["setup"]["has_address"] is True


async def test_an_email_that_isn_t_there_is_404_and_only_a_draft_is_deleted(
    db: AsyncSession,
) -> None:
    with pytest.raises(Problem) as missing:
        await service.get(db, uuid.uuid4())
    assert missing.value.code == "campaigns.email_not_found"
    with pytest.raises(Problem) as nobody:
        await service.subscriber(db, uuid.uuid4())
    assert nobody.value.code == "campaigns.subscriber_not_found"
    row = await service.create(db, NewCampaignEmail(subject="Gone"), by=None)
    await service.remove(db, row.id, by=uuid.uuid4())
    await db.commit()
    assert await db.scalar(select(Email.id).where(Email.id == row.id)) is None
    with pytest.raises(Problem) as stuck:
        await service.cancel(
            db,
            (await service.create(db, NewCampaignEmail(subject="D"), by=None)).id,
            by=uuid.uuid4(),
        )
    assert stuck.value.code == "campaigns.not_cancellable"
    await db.rollback()


async def test_a_time_without_its_zone_is_422(db: AsyncSession) -> None:
    row_id = (await service.create(db, NewCampaignEmail(subject="When"), by=None)).id
    await db.commit()
    for at in ("tomorrow", "2026-12-01T09:00:00"):
        with pytest.raises(Problem) as refused:
            await service.send(db, row_id, at, by=None)
        assert refused.value.errors == {
            "at": ["A time with its zone, such as 2026-12-01T09:00:00+00:00."]
        }
        await db.rollback()


async def test_a_hand_set_aside_unsubscribes_and_the_hint_hides_the_address(
    db: AsyncSession,
) -> None:
    address = _address()
    await service.request_news(db, address=address, name=None, source="form")
    row = await db.scalar(select(Subscriber).where(Subscriber.email_normal == address))
    assert row is not None
    await service.set_aside_by_hand(db, row.id, "unsubscribed", None, by=uuid.uuid4())
    await db.commit()
    await db.refresh(row)
    assert row.status == "unsubscribed"
    aside = await db.scalar(select(SetAside).where(SetAside.email_normal == address))
    assert aside is not None
    assert aside.detail == "Set aside by hand"
    assert service.email_hint("rae@example.org") == "r…@example.org"
    assert service.email_hint("no-at-sign") == "…"


# --- the listeners' guards -------------------------------------------------------------------


async def test_a_news_request_is_taken_once_and_a_bad_address_is_dropped(
    database: Database, db: AsyncSession
) -> None:
    ctx = Ctx(database)
    address = _address()
    once = uuid.uuid4()
    payload = {"message_id": str(uuid.uuid4()), "email": address, "name": "  Rae  "}
    await events._news(ctx, _event(payload, once))  # type: ignore[arg-type]
    await events._news(ctx, _event(payload, once))  # type: ignore[arg-type]
    row = await db.scalar(select(Subscriber).where(Subscriber.email_normal == address))
    assert row is not None
    assert (row.status, row.source, row.name) == ("pending", "contact", "Rae")
    bad = {"message_id": str(uuid.uuid4()), "email": "not an address", "name": ""}
    await events._news(ctx, _event(bad))  # type: ignore[arg-type]
    assert await db.scalar(select(Subscriber).where(Subscriber.email == "not an address")) is None


async def test_a_post_is_taken_only_with_email_subscribers_and_a_path_on_the_site(
    database: Database, db: AsyncSession
) -> None:
    ctx = Ctx(database)
    base = {"post_id": str(uuid.uuid4()), "slug": "s", "title": "T", "post_to_community": False}
    for payload in (
        base | {"path": "/blog/s", "email_subscribers": False},
        base | {"path": "https://elsewhere.test/x", "email_subscribers": True},
    ):
        await events._post(ctx, _event(payload))  # type: ignore[arg-type]
    assert (
        await db.scalar(select(Email.id).where(Email.post_id == uuid.UUID(base["post_id"]))) is None
    )
    taken = uuid.uuid4()
    good = base | {"path": "/blog/s", "email_subscribers": True}
    await events._post(ctx, _event(good, taken))  # type: ignore[arg-type]
    await events._post(ctx, _event(good, taken))  # type: ignore[arg-type]
    found = list(await db.scalars(select(Email).where(Email.post_id == uuid.UUID(base["post_id"]))))
    assert len(found) == 1


# --- the jobs, as the worker runs them ---------------------------------------------------------


async def test_the_jobs_run_as_the_worker_runs_them(
    database: Database, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (bounces.HOST, bounces.USERNAME, bounces.PASSWORD):
        monkeypatch.delenv(name, raising=False)
    ctx = Ctx(database)
    await jobs.read_bounces.run(ctx, {})  # type: ignore[arg-type]
    await jobs.send.run(ctx, {})  # type: ignore[arg-type]
    old = _address("old")
    await service.request_news(db, address=old, name=None, source="form")
    await db.commit()
    clock.advance(31 * 24 * 3600)
    try:
        await jobs.prune.run(ctx, {})  # type: ignore[arg-type]
    finally:
        clock.reset()
    assert await db.scalar(select(Subscriber).where(Subscriber.email_normal == old)) is None
    await db.execute(delete(Subscriber).where(Subscriber.email_normal == old))
    await db.commit()


# --- other shapes of report --------------------------------------------------------------------


def test_a_spam_report_with_only_the_returned_message_s_headers() -> None:
    raw = arf(None, to="fan@example.org").replace(
        b"Content-Type: message/rfc822", b"Content-Type: text/rfc822-headers"
    )
    assert bounces.read_report(raw) == [
        ("fan@example.org", bounces.Verdict("complained", "spam report: abuse"))
    ]


def test_report_fields_given_as_text_are_read_as_header_blocks() -> None:
    part = mail.message.Message()
    part.set_payload("Feedback-Type: abuse\r\nVersion: 1\r\n\r\nOther: block\r\n")
    blocks = bounces._fields(part)
    assert [block.get("Feedback-Type") for block in blocks] == ["abuse", None]
    empty = mail.message.Message()
    assert bounces._fields(empty) == []


def test_a_report_naming_nobody_names_nobody() -> None:
    nameless = arf(None, to="")
    assert bounces.read_report(nameless) == []
    assert bounces.handled([("1", nameless), ("2", b"Content-Type: text/plain\r\n\r\nx")]) == [
        ("1", [])
    ]


# --- the server copy ----------------------------------------------------------------------------


async def test_the_server_copy_answers_only_its_two_pages_and_lists_none(db: AsyncSession) -> None:
    pages = server_copy.NewsletterPages()
    assert await pages.page(db, "/newsletter/elsewhere", {}) is None
    assert list(await pages.sitemap(db)) == []


async def test_a_bounce_report_about_an_address_set_aside_twice_counts_once(
    db: AsyncSession,
) -> None:
    address = _address()
    await service.request_news(db, address=address, name=None, source="form")
    verdict = bounces.Verdict("bounced", "address: 5.1.1")
    assert await service.apply(db, [(address, verdict), (address, verdict)]) == 1
    assert await service.apply(db, [(_address("stranger"), verdict)]) == 0
    await db.commit()


def test_a_time_far_off_is_a_bad_cursor() -> None:
    with pytest.raises(Problem):
        service._after(f"{10**30}.ab", "emails")
    assert service._cursor_of(datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=1), "ab") == (
        "1000000.ab"
    )
