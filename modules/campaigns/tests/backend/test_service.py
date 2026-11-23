"""The newsletter's service and send job against the test database
(`dev plans/contracts/campaigns.md` §2, §3 and §7): sign-ups and their
confirmations, the links, the send's audience and pace, an address that
leaves mid-send, a post's email, the prune, the seed, export and erase, and
the attention items. Mail is recorded as it's queued."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
import pytest_asyncio
from campaigns import privacy, sending, service
from campaigns import seed as campaigns_seed
from campaigns.models import Delivery, Email, SetAside, Subscriber
from campaigns.schemas import CampaignEmailChange, NewCampaignEmail
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, clock, crypto, email
from kernel import privacy as kernel_privacy
from kernel import seed as seeding

from ..conftest import make_person

pytestmark = pytest.mark.db

Subject = kernel_privacy.Subject


@dataclass
class Queued:
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to(self, address: str) -> list[dict[str, Any]]:
        return [each for each in self.messages if each["to"].lower() == address.lower()]


@pytest.fixture(autouse=True)
def queued(monkeypatch: pytest.MonkeyPatch) -> Iterator[Queued]:
    found = Queued()

    async def record(
        db: AsyncSession,
        to: str,
        subject: str,
        text: str,
        html: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        email.check(to, subject, text, html, headers)
        found.messages.append(
            {"to": to, "subject": subject, "text": text, "html": html, "headers": headers or {}}
        )

    monkeypatch.setattr(email, "queue_message", record)
    yield found
    clock.reset()


@pytest_asyncio.fixture(loop_scope="session", autouse=True)
async def quiet(db: AsyncSession) -> None:
    """No other test's subscribers or sends: each test has the list to itself."""
    await db.execute(update(Email).where(Email.status == "sending").values(status="sent"))
    await db.execute(
        update(Email).where(Email.status == "scheduled").values(status="draft", send_at=None)
    )
    await db.execute(delete(Subscriber))
    # Copies queued by earlier tests fall out of the pace's minute.
    await db.execute(
        update(Delivery)
        .where(Delivery.queued_at.is_not(None))
        .values(queued_at=Delivery.queued_at - timedelta(days=1))
    )
    await db.commit()


def _address(name: str = "fan") -> str:
    return f"{name}-{uuid.uuid4().hex[:10]}@example.org"


async def _ask(db: AsyncSession, address: str, **given: Any) -> None:
    await service.request_news(db, address=address, name=given.get("name"), source="form")
    await db.commit()


def _token_in(message: dict[str, Any]) -> str:
    link = message["text"].split("Confirm it: ", 1)[1].split()[0]
    return link.split("token=", 1)[1]


async def _subscribed(db: AsyncSession, queued: Queued, *addresses: str) -> None:
    for address in addresses:
        await _ask(db, address)
        await service.confirm(db, _token_in(queued.to(address)[-1]))
        await db.commit()


async def _row(db: AsyncSession, address: str) -> Subscriber | None:
    found = await db.scalar(
        select(Subscriber)
        .where(Subscriber.email_normal == address.lower())
        .execution_options(populate_existing=True)
    )
    return found


async def _email(db: AsyncSession, subject: str = "Winter shows") -> Email:
    row = await service.create(
        db, NewCampaignEmail(subject=subject, body="Three nights in December."), by=None
    )
    await db.commit()
    return row


async def _send_now(db: AsyncSession, row: Email) -> None:
    await service.send(db, row.id, None, by=None)
    await db.commit()


async def _run(db: AsyncSession) -> int:
    queued = await sending.run(db)
    await db.commit()
    return queued


# --- signing up -----------------------------------------------------------------------


async def test_a_new_address_is_pending_with_one_confirmation(
    db: AsyncSession, queued: Queued
) -> None:
    address = _address()
    await _ask(db, address, name="Rae")
    row = await _row(db, address)
    assert row is not None
    assert (row.status, row.name, row.source) == ("pending", "Rae", "form")
    [sent] = queued.to(address)
    assert sent["subject"] == "Confirm your subscription to Test Site"
    assert "https://site.test/newsletter/confirm?token=" in sent["text"]
    assert row.token_hash not in sent["text"]  # the link carries the token, never its hash


async def test_a_pending_address_asked_again_gets_one_more_only_after_a_while(
    db: AsyncSession, queued: Queued
) -> None:
    address = _address()
    await _ask(db, address)
    await _ask(db, address)
    assert len(queued.to(address)) == 1
    clock.advance(service.RESEND_AFTER.total_seconds() + 1)
    await _ask(db, address)
    sent = queued.to(address)
    assert len(sent) == 2
    assert _token_in(sent[0]) == _token_in(sent[1])  # the same link, so the first still works


async def test_a_subscribed_or_set_aside_address_gets_nothing(
    db: AsyncSession, queued: Queued
) -> None:
    subscribed, aside = _address("in"), _address("out")
    await _subscribed(db, queued, subscribed)
    await service.set_aside(db, aside, "complained", "spam report: abuse")
    await db.commit()
    before = len(queued.messages)
    await _ask(db, subscribed)
    await _ask(db, aside.upper())
    assert len(queued.messages) == before
    assert await _row(db, aside) is None


async def test_confirm_and_unsubscribe_work_by_token_and_unsubscribing_sets_aside(
    db: AsyncSession, queued: Queued
) -> None:
    address = _address()
    await _ask(db, address)
    token = _token_in(queued.to(address)[0])
    shown = await service.confirm(db, token)
    await db.commit()
    assert shown == {"email_hint": f"{address[0]}…@example.org", "subscribed": True}
    assert await service.looked_up(db, token) == shown
    assert (await service.unsubscribe(db, token))["subscribed"] is False
    await db.commit()
    assert await service.unsubscribe(db, token) == {
        "email_hint": shown["email_hint"],
        "subscribed": False,
    }
    await db.commit()
    assert await service.is_set_aside(db, address)
    again = await service.confirm(db, token)
    assert again["subscribed"] is False
    with pytest.raises(Problem) as unknown:
        await service.looked_up(db, "not-a-token")
    assert unknown.value.code == "campaigns.unknown_link"


# --- sending --------------------------------------------------------------------------


async def test_a_send_reaches_the_subscribed_not_set_aside_each_with_their_own_link(
    db: AsyncSession, queued: Queued
) -> None:
    one, two, pending, aside = (_address(name) for name in ("one", "two", "pending", "aside"))
    await _subscribed(db, queued, one, two, aside)
    await _ask(db, pending)
    await service.set_aside(db, aside, "bounced", "address: 5.1.1")
    await db.commit()
    row = await _email(db)
    await _send_now(db, row)
    assert await _run(db) == 2
    assert await _run(db) == 0  # run twice, nobody twice
    links = set()
    for address in (one, two):
        [sent] = [each for each in queued.to(address) if each["subject"] == "Winter shows"]
        token = crypto.open((await _row(db, address)).token_sealed)  # type: ignore[union-attr]
        assert f"https://site.test/newsletter/unsubscribe?token={token}" in sent["text"]
        assert sent["headers"] == {
            "List-Unsubscribe": f"<https://site.test/api/campaigns/unsubscribe?token={token}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        links.add(token)
    assert len(links) == 2
    assert not [each for each in queued.to(aside) if each["subject"] == "Winter shows"]
    assert not [each for each in queued.to(pending) if each["subject"] == "Winter shows"]
    done = await service.get(db, row.id)
    await db.refresh(done)
    assert (done.status, done.sent_to) == ("sent", 2)


async def test_the_pace_queues_a_sixtieth_of_the_hour_each_minute(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    campaigns_settings["send_per_hour"] = 120  # two a minute
    people = [_address(f"p{each}") for each in range(5)]
    await _subscribed(db, queued, *people)
    row = await _email(db)
    await _send_now(db, row)
    assert await _run(db) == 2
    assert await _run(db) == 0  # an extra run in the same minute adds nothing
    clock.advance(61)
    assert await _run(db) == 2
    clock.advance(61)
    assert await _run(db) == 1
    await db.refresh(row)
    assert (row.status, row.sent_to) == ("sent", 5)


async def test_an_address_that_leaves_mid_send_is_skipped(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    campaigns_settings["send_per_hour"] = 60  # one a minute
    people = [_address(f"m{each}") for each in range(3)]
    await _subscribed(db, queued, *people)
    row = await _email(db)
    await _send_now(db, row)
    assert await _run(db) == 1
    got = {
        address
        for address in people
        if any(each["subject"] == "Winter shows" for each in queued.to(address))
    }
    left = [address for address in people if address not in got]
    unsubscribed, bounced = left
    await service.unsubscribe(
        db, crypto.open((await _row(db, unsubscribed)).token_sealed)  # type: ignore[union-attr]
    )
    await service.set_aside(db, bounced, "bounced", "address: 5.1.1")
    await db.commit()
    for _ in range(3):
        clock.advance(61)
        await _run(db)
    for address in left:
        assert not [each for each in queued.to(address) if each["subject"] == "Winter shows"]
    await db.refresh(row)
    assert (row.status, row.sent_to) == ("sent", 1)


async def test_nothing_sends_without_the_postal_address(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    await _subscribed(db, queued, _address())
    row_id = (await _email(db)).id
    campaigns_settings["postal_address"] = ""
    with pytest.raises(Problem) as refused:
        await service.send(db, row_id, None, by=None)
    assert refused.value.code == "campaigns.no_address"
    await db.rollback()
    waiting = select(func.count()).select_from(Delivery).where(Delivery.email_id == row_id)
    assert await db.scalar(waiting) == 0


async def test_with_nobody_subscribed_a_send_is_refused(db: AsyncSession) -> None:
    row = await _email(db)
    with pytest.raises(Problem) as refused:
        await service.send(db, row.id, None, by=None)
    assert refused.value.code == "campaigns.nobody"


async def test_a_scheduled_email_starts_at_its_time_and_cancel_stops_it(
    db: AsyncSession, queued: Queued
) -> None:
    address = _address()
    await _subscribed(db, queued, address)
    later = await _email(db, "Later")
    soon = await _email(db, "Soon")
    for row in (later, soon):
        await service.send(db, row.id, (clock.now() + timedelta(hours=1)).isoformat(), by=None)
        await db.commit()
    await service.cancel(db, later.id, by=uuid.uuid4())
    await db.commit()
    assert await _run(db) == 0
    clock.advance(3601)
    assert await _run(db) == 1
    subjects = [each["subject"] for each in queued.to(address)]
    assert "Soon" in subjects
    assert "Later" not in subjects
    await db.refresh(later)
    assert (later.status, later.send_at) == ("draft", None)


async def test_cancel_while_sending_stops_the_rest(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    campaigns_settings["send_per_hour"] = 60
    await _subscribed(db, queued, *(_address(f"c{each}") for each in range(3)))
    row = await _email(db)
    await _send_now(db, row)
    assert await _run(db) == 1
    await service.cancel(db, row.id, by=uuid.uuid4())
    await db.commit()
    clock.advance(61)
    assert await _run(db) == 0
    await db.refresh(row)
    assert (row.status, row.sent_to) == ("sent", 1)


async def test_a_post_s_email_goes_once_and_waits_as_a_draft_without_the_address(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    address = _address()
    await _subscribed(db, queued, address)
    post = uuid.uuid4()
    made = await service.from_post(
        db, post_id=post, title="Don't *stop*", summary="A new song.", path="/blog/dont-stop"
    )
    await db.commit()
    assert made is not None
    assert made.status == "sending"
    assert await service.from_post(db, post_id=post, title="x", summary="", path="/blog/x") is None
    await _run(db)
    [sent] = [each for each in queued.to(address) if each["subject"] == "Don't *stop*"]
    assert "[Read the post](https://site.test/blog/dont-stop)" in sent["text"]
    assert "Don\\'t \\*stop\\*" not in (sent["html"] or "")
    campaigns_settings["postal_address"] = ""
    waiting = await service.from_post(
        db, post_id=uuid.uuid4(), title="Held", summary="", path="/blog/held"
    )
    await db.commit()
    assert waiting is not None
    assert waiting.status == "draft"


# --- what goes, the seed, export and erase ----------------------------------------------


async def test_the_prune_keeps_30_days_of_pending_sign_ups(
    db: AsyncSession, queued: Queued
) -> None:
    old, new, confirmed = _address("old"), _address("new"), _address("kept")
    await _ask(db, old)
    await _subscribed(db, queued, confirmed)
    await db.execute(
        update(Subscriber)
        .where(Subscriber.email_normal.in_([old, confirmed]))
        .values(created_at=clock.now() - timedelta(days=31))
    )
    await db.commit()
    await _ask(db, new)
    assert await service.prune(db) == 1
    await db.commit()
    assert await _row(db, old) is None
    assert await _row(db, new) is not None
    assert await _row(db, confirmed) is not None


async def test_the_seed_twice_is_the_same(db: AsyncSession) -> None:
    async def counts() -> tuple[int, int, int]:
        return (
            int(await db.scalar(select(func.count()).select_from(Subscriber)) or 0),
            int(await db.scalar(select(func.count()).select_from(SetAside)) or 0),
            int(await db.scalar(select(func.count()).select_from(Email)) or 0),
        )

    before = await counts()
    for _ in range(2):
        await campaigns_seed.seed(db, seeding.Context("campaigns", None, {}))  # type: ignore[arg-type]
        await db.commit()
        if _ == 0:
            once = await counts()
    assert await counts() == once
    assert once[0] - before[0] == len(campaigns_seed.SUBSCRIBERS)
    seeded = list(
        await db.scalars(select(Subscriber.email).where(Subscriber.email.like("%@example.com")))
    )
    assert all(each.endswith("@example.com") for each in seeded)


async def test_export_and_erase_by_address_and_by_account(db: AsyncSession, queued: Queued) -> None:
    person, _account_address = await make_person(db)
    by_address = _address("Asked")
    await _subscribed(db, queued, by_address)
    other = _address("other")
    await service.request_news(db, address=other, name="Signed in", source="form", user_id=person)
    await db.commit()
    mixed = Subject(person, by_address.upper())
    exported = await privacy.export_user_data(db, mixed)
    assert {row["email"] for row in exported["newsletter"]} == {by_address, other}
    await privacy.delete_user_data(db, mixed)
    await db.commit()
    assert await _row(db, by_address) is None
    assert await _row(db, other) is None
    assert await service.is_set_aside(db, by_address)
    assert await service.is_set_aside(db, other)
    after = await privacy.export_user_data(db, mixed)
    assert after["newsletter"] == []
    assert {row["why"] for row in after["newsletter_set_aside"]} == {"unsubscribed"}


async def test_both_attention_items(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    await db.execute(
        update(SetAside)
        .where(SetAside.why == "bounced")
        .values(since=clock.now() - timedelta(days=30))
    )
    await db.commit()
    assert await service.bounced_item(db) is None
    for each in range(2):
        await service.set_aside(db, _address(f"b{each}"), "bounced", "address: 5.1.1")
    await db.commit()
    item = await service.bounced_item(db)
    assert item is not None
    assert (item.key, item.what, item.label, item.permission) == (
        "campaigns.set_aside",
        "2 addresses bounced and were set aside",
        "See them",
        "campaigns.subscriber.manage",
    )
    assert await service.no_address_item(db) is None  # nobody subscribed yet, and an address
    await _subscribed(db, queued, _address())
    assert await service.no_address_item(db) is None
    campaigns_settings["postal_address"] = ""
    missing = await service.no_address_item(db)
    assert missing is not None
    assert (missing.key, missing.permission) == (
        "campaigns.no_address",
        "campaigns.email.manage",
    )


async def test_a_replay_key_is_taken_once(db: AsyncSession) -> None:
    key = f"test:{uuid.uuid4()}"
    assert await service.first_time(db, key) is True
    assert await service.first_time(db, key) is False
    await db.execute(text("SELECT 1"))
    await db.rollback()


async def test_erasing_a_person_takes_their_address_out_of_every_send(
    db: AsyncSession, queued: Queued
) -> None:
    address = _address("erased")
    await _subscribed(db, queued, address)
    row = await _email(db)
    await _send_now(db, row)
    await _run(db)
    sent = select(func.count()).select_from(Delivery).where(Delivery.email_normal == address)
    assert await db.scalar(sent) == 1
    await privacy.delete_user_data(db, Subject(uuid.uuid4(), address))
    await db.commit()
    assert await db.scalar(sent) == 0
    await db.refresh(row)
    assert row.sent_to == 1  # the count stays; the address doesn't


async def test_the_prune_keeps_a_send_s_rows_30_days(db: AsyncSession, queued: Queued) -> None:
    address = _address("kept")
    await _subscribed(db, queued, address)
    row = await _email(db)
    await _send_now(db, row)
    await _run(db)
    rows = select(func.count()).select_from(Delivery).where(Delivery.email_id == row.id)
    assert await service.prune(db) == 0
    assert await db.scalar(rows) == 1
    clock.advance(31 * 24 * 3600)
    await service.prune(db)
    await db.commit()
    assert await db.scalar(rows) == 0


# --- the review's findings (Codex on #134) ---------------------------------------------


@dataclass
class Account:
    id: uuid.UUID
    email: str
    email_verified_at: object


def test_a_sign_up_joins_an_account_only_for_its_own_verified_address() -> None:
    """Codex on #134 (P1): a signed-in person signing up someone else's address
    mustn't make it theirs, or their account's export would hold it."""
    person = Account(uuid.uuid4(), "Rae@Example.org", clock.now())
    assert service.owner_of(person, " rae@example.ORG ") == person.id
    assert service.owner_of(person, "someone-else@example.org") is None
    assert service.owner_of(Account(person.id, person.email, None), person.email) is None
    assert service.owner_of(None, person.email) is None


async def test_a_send_run_while_another_holds_the_pace_queues_nothing(
    database: Any, db: AsyncSession, queued: Queued
) -> None:
    """Codex on #134 (P2): two runs at once mustn't each spend the minute's allowance."""
    await _subscribed(db, queued, *(_address(f"r{each}") for each in range(2)))
    row = await _email(db)
    await _send_now(db, row)
    async with database.sessions() as other:
        await other.execute(select(func.pg_advisory_xact_lock(sending.LOCK)))
        assert await _run(db) == 0  # the other run holds it: this one leaves the work to it
        await other.rollback()
    assert await _run(db) == 2


async def test_an_email_too_long_once_rendered_is_refused_before_it_sends(
    db: AsyncSession, queued: Queued
) -> None:
    """Codex on #134 (P2): a body under the input limit can render past the
    mailer's, which would stop every send behind it."""
    await _subscribed(db, queued, _address())
    long = "a\n\n" * 10_000
    row = await service.create(db, NewCampaignEmail(subject="Long", body=long), by=None)
    await db.commit()
    row_id = row.id
    with pytest.raises(Problem) as refused:
        await service.send(db, row_id, None, by=None)
    assert refused.value.code == "campaigns.too_long"
    assert "body.body" in refused.value.errors
    await db.rollback()
    waiting = select(func.count()).select_from(Delivery).where(Delivery.email_id == row_id)
    assert await db.scalar(waiting) == 0


async def test_a_scheduled_email_saved_too_long_is_refused(
    db: AsyncSession, queued: Queued
) -> None:
    await _subscribed(db, queued, _address())
    row = await _email(db)
    await service.send(db, row.id, (clock.now() + timedelta(hours=1)).isoformat(), by=None)
    await db.commit()
    await db.refresh(row)
    with pytest.raises(Problem) as refused:
        await service.change(
            db,
            row.id,
            CampaignEmailChange(version=row.version, body="a\n\n" * 10_000),
            by=uuid.uuid4(),
        )
    assert refused.value.code == "campaigns.too_long"
    await db.rollback()


async def test_a_send_too_long_to_queue_stops_and_never_blocks_the_rest(
    db: AsyncSession, queued: Queued
) -> None:
    address = _address()
    await _subscribed(db, queued, address)
    stuck = await _email(db, "Stuck")
    await _send_now(db, stuck)
    await db.execute(update(Email).where(Email.id == stuck.id).values(body="a\n\n" * 10_000))
    await db.commit()
    later = await _email(db, "Later")
    await _send_now(db, later)
    assert await _run(db) == 1
    assert [each["subject"] for each in queued.to(address)][-1:] == ["Later"]
    await db.refresh(stuck)
    assert (stuck.status, stuck.sent_to) == ("sent", 0)


async def test_a_pace_under_60_an_hour_holds_to_its_hour(
    db: AsyncSession, queued: Queued, campaigns_settings: dict[str, Any]
) -> None:
    """CodeRabbit on #134: at least one a minute mustn't make 20 an hour 60."""
    campaigns_settings["send_per_hour"] = 2
    await _subscribed(db, queued, *(_address(f"h{each}") for each in range(3)))
    row = await _email(db)
    await _send_now(db, row)
    assert await _run(db) == 1
    clock.advance(61)
    assert await _run(db) == 1
    clock.advance(61)
    assert await _run(db) == 0  # two in the hour already
    clock.advance(3600)
    assert await _run(db) == 1


async def test_a_token_no_key_opens_skips_that_copy_alone(db: AsyncSession, queued: Queued) -> None:
    """CodeRabbit on #134: one unreadable token mustn't hold every send behind it."""
    broken, fine = _address("broken"), _address("fine")
    await _subscribed(db, queued, broken, fine)
    await db.execute(
        update(Subscriber)
        .where(Subscriber.email_normal == broken)
        .values(token_sealed="not sealed")
    )
    await db.commit()
    row = await _email(db)
    await _send_now(db, row)
    assert await _run(db) == 1
    assert [each for each in queued.to(fine) if each["subject"] == "Winter shows"]
    assert not [each for each in queued.to(broken) if each["subject"] == "Winter shows"]
    await db.refresh(row)
    assert (row.status, row.sent_to) == ("sent", 1)


async def test_a_test_too_long_is_refused(db: AsyncSession) -> None:
    row = await service.create(db, NewCampaignEmail(subject="Long", body="a\n\n" * 10_000), by=None)
    await db.commit()
    with pytest.raises(Problem) as refused:
        await service.send_test(db, row.id, to="me@example.org")
    assert refused.value.code == "campaigns.too_long"
