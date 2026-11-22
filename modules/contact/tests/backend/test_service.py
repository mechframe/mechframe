"""contact's service on the test database (`dev plans/contracts/contact.md`
§2, §7): the Inbox's order and pages, a message let out of spam counting
once, the retention, export and erase, the seed and the waiting item's
words. A message arriving through the form is the contract suite's."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from contact import privacy as contact_privacy
from contact import service
from contact.models import Message
from contact.seed import _NAMESPACE, MESSAGES
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, Problem, clock, load_module, privacy
from kernel import seed as seeding
from kernel.models import AuditEvent

from ..conftest import make_person, unique

pytestmark = pytest.mark.db

MODULE = Path(__file__).resolve().parents[2]
#: Far ahead of any other test's messages, so these come first in their rank.
AHEAD = datetime(2100, 1, 1, tzinfo=UTC)


def _message(**fields: Any) -> Message:
    at = fields.pop("at", clock.now())
    name = fields.pop("name", unique("sender"))
    email = fields.pop("email", f"{uuid.uuid4().hex[:10]}@example.test")
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "received_at": at,
        "name": name,
        "email": email,
        "email_normal": service.normal(email),
        "topic": "question",
        "topic_label": "A question",
        "message": "Hello there.",
        "wants_news": False,
        "status": "new",
        "status_at": at,
        **fields,
    }
    return Message(**values)


@pytest_asyncio.fixture(loop_scope="session")
async def made(db: AsyncSession) -> AsyncIterator[list[uuid.UUID]]:
    """Ids to delete after the test, so far-ahead rows never meet another test."""
    ids: list[uuid.UUID] = []
    yield ids
    await db.rollback()
    await db.execute(delete(Message).where(Message.id.in_(ids)))
    await db.commit()


async def _add(db: AsyncSession, made: list[uuid.UUID], **fields: Any) -> Message:
    message = _message(**fields)
    db.add(message)
    await db.commit()
    made.append(message.id)
    return message


# --- the Inbox -----------------------------------------------------------------------------


async def _every(db: AsyncSession, tab: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = await service.listed(db, tab, cursor, 2)
        items += page["items"]
        cursor = page["next_cursor"]
        if cursor is None:
            return items


async def test_a_first_topic_s_new_messages_come_first_then_newest_page_by_page(
    db: AsyncSession, made: list[uuid.UUID]
) -> None:
    booking = await _add(db, made, topic="work", topic_label="Working together", at=AHEAD)
    question = await _add(db, made, at=AHEAD + timedelta(hours=3))
    replied = await _add(db, made, topic="work", status="replied", at=AHEAD + timedelta(hours=2))
    older = await _add(db, made, topic="work", at=AHEAD - timedelta(hours=1))
    spam = await _add(db, made, status="spam", held_reason="links", at=AHEAD + timedelta(hours=4))
    mine = {m.id: m for m in (booking, question, replied, older, spam)}

    every = [item for item in await _every(db, "all") if uuid.UUID(item["id"]) in mine]
    assert [item["id"] for item in every] == [
        str(m.id) for m in (booking, older, question, replied)
    ]
    assert [item["first"] for item in every] == [True, True, False, True]
    assert every[0]["topic_label"] == "Working together"

    spammed = [item["id"] for item in await _every(db, "spam") if uuid.UUID(item["id"]) in mine]
    assert spammed == [str(spam.id)]
    news = [item["id"] for item in await _every(db, "new") if uuid.UUID(item["id"]) in mine]
    assert news == [str(m.id) for m in (booking, older, question)]


async def test_a_cursor_that_isn_t_one_is_a_422(db: AsyncSession) -> None:
    for cursor in ("x", "2.1.0", "0.a.b", f"1.{10**6}.not-a-uuid"):
        with pytest.raises(Problem) as refused:
            await service.listed(db, "all", cursor)
        assert refused.value.status == 422


async def test_the_counts_are_each_tab_s(db: AsyncSession, made: list[uuid.UUID]) -> None:
    before = await service.counts(db)
    await _add(db, made, status="archived")
    await _add(db, made, status="spam")
    after = await service.counts(db)
    assert after == {**before, "archived": before["archived"] + 1, "spam": before["spam"] + 1}


def test_the_first_line_keeps_a_short_message_and_cuts_a_long_one_at_a_word() -> None:
    assert service.first_line("Hi,\n\n  can you  play?") == "Hi, can you play?"
    long = "word " * 40
    cut = service.first_line(long)
    assert cut.endswith("word…")
    assert len(cut) <= service.FIRST_LINE + 1


# --- leaving spam counts a message once ----------------------------------------------------


async def test_a_message_let_out_of_spam_tells_people_and_signs_up_once(
    db: AsyncSession, made: list[uuid.UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    told: list[tuple[Any, ...]] = []
    emitted: list[tuple[str, Any]] = []

    async def notify_holders(db: AsyncSession, *args: Any, **kwargs: Any) -> list[uuid.UUID]:
        told.append((*args, kwargs.get("link")))
        return []

    async def emit(db: AsyncSession, name: str, payload: Any) -> int:
        emitted.append((name, payload))
        return 0

    monkeypatch.setattr(service.notifications, "notify_holders", notify_holders)
    monkeypatch.setattr(service.events, "emit", emit)
    actor, _ = await make_person(db)
    held = await _add(db, made, status="spam", held_reason="too_fast", wants_news=True)

    for status in ("new", "spam", "new", "archived"):
        await service.change_status(db, held.id, status, by=actor)  # type: ignore[arg-type]
        await db.commit()

    assert told == [
        (
            "contact.message.manage",
            "contact.message_received",
            {"topic": "A question", "name": held.name},
            f"/admin/contact/{held.id}",
        )
    ]
    assert [(name, payload.message_id, payload.email) for name, payload in emitted] == [
        ("contact.news.requested", held.id, held.email)
    ]
    changes = (
        await db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.action == "contact.message.status", AuditEvent.target_id == str(held.id)
            )
            .order_by(AuditEvent.id)
        )
    ).all()
    assert [(c.details["from"], c.details["to"]) for c in changes] == [
        ("spam", "new"),
        ("new", "spam"),
        ("spam", "new"),
        ("new", "archived"),
    ]


async def test_the_same_status_changes_nothing(db: AsyncSession, made: list[uuid.UUID]) -> None:
    actor, _ = await make_person(db)
    message = await _add(db, made, status="replied")
    at = message.status_at
    same = await service.change_status(db, message.id, "replied", by=actor)
    await db.commit()
    assert same.status_at == at


async def test_a_message_that_isn_t_there_is_a_404(db: AsyncSession) -> None:
    with pytest.raises(Problem) as missing:
        await service.get(db, uuid.uuid4())
    assert (missing.value.status, missing.value.code) == (404, "contact.message_not_found")


# --- retention, export and erase -----------------------------------------------------------


async def test_prune_deletes_old_spam_and_old_messages_and_keeps_the_rest(
    db: AsyncSession, made: list[uuid.UUID]
) -> None:
    now = clock.now()
    old_spam = await _add(db, made, status="spam", at=now - timedelta(days=31))
    young_spam = await _add(db, made, status="spam", at=now - timedelta(days=29))
    old_archived = await _add(db, made, status="archived", at=now - timedelta(days=731))
    kept = await _add(db, made, status="replied", at=now - timedelta(days=700))
    # Its status changed lately: the 2 years run from that, not from when it came.
    moved = await _add(
        db, made, status="archived", at=now - timedelta(days=900), status_at=now - timedelta(days=5)
    )

    assert await service.prune(db) >= 2
    await db.commit()
    left = set(await db.scalars(select(Message.id).where(Message.id.in_(made))))
    assert left == {young_spam.id, kept.id, moved.id}
    assert old_spam.id not in left
    assert old_archived.id not in left
    await service.prune(db)  # a second run deletes nothing of these
    await db.commit()
    assert set(await db.scalars(select(Message.id).where(Message.id.in_(made)))) == left


async def test_export_and_erase_find_a_person_by_address_in_any_case_and_by_account(
    db: AsyncSession, made: list[uuid.UUID]
) -> None:
    person, address = await make_person(db)
    typed = await _add(db, made, email=address.upper(), message="By address.")
    signed_in = await _add(db, made, user_id=person, message="Signed in.")
    someone_else = await _add(db, made, message="Not theirs.")
    subject = privacy.Subject(user_id=person, email=address)

    exported = await contact_privacy.export_user_data(db, subject)
    assert sorted(row["message"] for row in exported["messages"]) == ["By address.", "Signed in."]
    assert {row["email"] for row in exported["messages"]} >= {address.upper()}

    await contact_privacy.delete_user_data(db, subject)
    await db.commit()
    left = set(await db.scalars(select(Message.id).where(Message.id.in_(made))))
    assert left == {someone_else.id}
    assert typed.id not in left
    assert signed_in.id not in left


async def test_the_seed_gives_a_message_in_each_tab_once(db: AsyncSession) -> None:
    contact = load_module(MODULE / "module.json")
    allowed = {"MECHFRAME_ALLOW_SEED": "1"}
    ids = [uuid.uuid5(_NAMESPACE, each[1]) for each in MESSAGES]

    await seeding.run(db, [contact], environ=allowed)
    first = {
        row.id: (row.status, row.topic, row.held_reason, row.notified_at is None)
        for row in await db.scalars(select(Message).where(Message.id.in_(ids)))
    }
    await seeding.run(db, [contact], environ=allowed)
    db.expire_all()
    again = {
        row.id: (row.status, row.topic, row.held_reason, row.notified_at is None)
        for row in await db.scalars(select(Message).where(Message.id.in_(ids)))
    }

    assert again == first
    assert sorted(status for status, *_ in first.values()) == [
        "archived",
        "new",
        "new",
        "replied",
        "spam",
    ]
    assert [held for status, _, held, untold in first.values() if status == "spam"] == ["links"]
    assert all(untold == (status == "spam") for status, _, _, untold in first.values())


# --- the waiting item ----------------------------------------------------------------------


def test_the_waiting_item_s_words_and_tone() -> None:
    top = uuid.uuid4()
    one = service.waiting_item(1, timedelta(hours=3), top)
    assert (one.tone, one.what, one.why, one.label, one.to, one.permission) == (
        "info",
        "1 new message is waiting",
        "It came in today and hasn't had a reply yet.",
        "Open it",
        f"/admin/contact/{top}",
        "contact.message.manage",
    )
    two = service.waiting_item(2, timedelta(days=1, hours=2), top)
    assert (two.tone, two.what, two.why, two.label) == (
        "info",
        "2 new messages are waiting",
        "The oldest came in yesterday and hasn't had a reply.",
        "Open the first",
    )
    late = service.waiting_item(3, timedelta(days=4), top)
    assert (late.tone, late.why) == (
        "warning",
        "The oldest came in 4 days ago and hasn't had a reply.",
    )
    assert service.waiting_item(1, timedelta(days=2), top).tone == "warning"


async def test_the_daily_job_prunes_in_a_session_of_its_own(
    database: Database, db: AsyncSession, made: list[uuid.UUID]
) -> None:
    from contact.jobs import prune as daily

    class Context:
        def sessions(self) -> AsyncSession:
            return database.sessions()

    old_id = (await _add(db, made, status="spam", at=clock.now() - timedelta(days=40))).id
    assert daily.name == "contact.prune"
    await daily.run(Context(), {})  # type: ignore[arg-type]
    await db.rollback()  # a fresh read: the job's own session deleted it
    assert await db.scalar(select(Message.id).where(Message.id == old_id)) is None
