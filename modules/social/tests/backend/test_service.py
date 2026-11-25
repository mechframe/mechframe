"""social's service against the test database, with no app (`dev plans/contracts/social.md`
§7): two sends of one thing at once share once, a saved token that can't be
opened is reported and never swapped for the host's, and export and erase."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from social import buffer, service
from social import privacy as social_privacy
from social.models import Channel, Share
from social.schemas import Settings, ShareSend
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from harness.fake_buffer import FakeBuffer
from kernel import Database, Problem, privacy, server_copy
from kernel.settings import settings

from ..conftest import make_person

pytestmark = pytest.mark.db

TOKEN = "buffer-token-for-the-service-tests-01"


@pytest.fixture(autouse=True)
def registered() -> Iterator[None]:
    """social's settings, as an app with social on registers them."""
    known = "social" in settings.models
    if not known:
        settings.register("social", Settings)
    yield
    if not known:
        settings.models.pop("social", None)
        settings.own_routes.pop("social", None)


@pytest.fixture
def fake() -> Iterator[FakeBuffer]:
    found = FakeBuffer()
    before = buffer.use_transport(found.transport)
    yield found
    buffer.use_transport(before)


@pytest_asyncio.fixture(loop_scope="session")
async def channel(db: AsyncSession) -> AsyncIterator[str]:
    """A channel of this test's own, beside whatever another test listed."""
    channel_id = f"race-{uuid.uuid4().hex[:10]}"
    db.add(
        Channel(
            id=channel_id,
            name="@race",
            service="twitter",
            position=99,
            listed_at=datetime.now(UTC),
        )
    )
    await db.commit()
    yield channel_id
    await db.execute(delete(Share).where(Share.channel_id == channel_id))
    await db.execute(delete(Channel).where(Channel.id == channel_id))
    await db.commit()


async def test_two_sends_of_one_thing_at_once_share_once(
    database: Database, channel: str, fake: FakeBuffer, monkeypatch: pytest.MonkeyPatch
) -> None:
    thing = uuid.uuid4()
    card = server_copy.Preview(
        url="https://site.test/blog/race", title="Race", description="", image=None
    )

    async def preview(db: object, content_type: str, content_id: uuid.UUID) -> server_copy.Preview:
        return card

    async def token(db: object) -> str:
        return TOKEN

    read = service.history

    async def slow(db: AsyncSession, content_type: str, content_id: uuid.UUID) -> list[Share]:
        # Both sends read their history, then wait: without the lock on the
        # thing, both would find nothing and both would share.
        found = await read(db, content_type, content_id)
        await asyncio.sleep(0.3)
        return found

    monkeypatch.setattr(server_copy, "preview", preview)
    monkeypatch.setattr(service, "token_in_use", token)
    monkeypatch.setattr(service, "history", slow)
    body = ShareSend(
        type="blog.post",
        id=str(thing),
        admin_path="/admin/blog/race",
        channel_ids=[channel],
        text="Race",
        when="draft",
    )

    async def press() -> int:
        async with database.sessions() as db:
            try:
                await service.send(db, body, user=None)
            except Problem as refused:
                return refused.status
            return 200

    assert sorted(await asyncio.gather(press(), press())) == [200, 409]
    assert len(fake.made()) == 1


async def _keep(db: AsyncSession, values: dict[str, Any]) -> None:
    await db.execute(text("DELETE FROM kernel_setting WHERE module_id = 'social'"))
    await db.execute(
        text(
            "INSERT INTO kernel_setting (module_id, version, values, updated_at) "
            "VALUES ('social', 1, CAST(:values AS jsonb), now())"
        ),
        {"values": json.dumps(values)},
    )
    await db.commit()


async def test_a_saved_token_that_cant_be_opened_is_reported_not_swapped(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUFFER_ACCESS_TOKEN", "host-buffer-token-for-the-tests-0001")
    try:
        await _keep(db, {"buffer_token": {"sealed": "not-a-sealed-token", "changes": 1}})
        state = await service.token_state(db)
        assert (state.source, state.unreadable, state.usable) == ("saved", True, False)
        with pytest.raises(Problem) as refused:
            await service.token_in_use(db)
        assert refused.value.code == "social.token_unreadable"
        await _keep(db, {})
        assert (await service.token_state(db)).source == "host"
        assert await service.token_in_use(db) == "host-buffer-token-for-the-tests-0001"
    finally:
        await db.execute(text("DELETE FROM kernel_setting WHERE module_id = 'social'"))
        await db.commit()


async def test_export_lists_a_persons_shares_and_erase_keeps_them_the_sites(
    db: AsyncSession,
) -> None:
    person, email = await make_person(db)
    now = datetime.now(UTC)
    share = Share(
        content_type="blog.post",
        content_id=uuid.uuid4(),
        admin_path="/admin/blog/x",
        channel_id=f"ch-{uuid.uuid4().hex[:8]}",
        channel_name="@testsite",
        service="twitter",
        text="Jazz",
        link="https://site.test/blog/jazz",
        mode="queue",
        state="queued",
        sent_by_id=person,
        sent_by_name="Ada",
        created_at=now,
        updated_at=now,
    )
    # Shared by the same person before they had a name: kept by their address, its account gone.
    by_address = Share(
        content_type="blog.post",
        content_id=uuid.uuid4(),
        admin_path="/admin/blog/y",
        channel_id=share.channel_id,
        channel_name="@testsite",
        service="twitter",
        text="Blues",
        link="https://site.test/blog/blues",
        mode="queue",
        state="sent",
        sent_by_id=None,
        sent_by_name=email.upper(),
        created_at=now,
        updated_at=now,
    )
    db.add_all([share, by_address])
    await db.commit()
    subject = privacy.Subject(user_id=person, email=email)
    exported = await social_privacy.export_user_data(db, subject)
    assert sorted(row["text"] for row in exported["social_shares"]) == ["Blues", "Jazz"]
    await social_privacy.delete_user_data(db, subject)
    await db.commit()
    kept = await db.scalar(
        select(Share).where(Share.id == share.id).execution_options(populate_existing=True)
    )
    assert kept is not None
    assert (kept.sent_by_id, kept.sent_by_name) == (None, "")
    assert (await social_privacy.export_user_data(db, subject))["social_shares"] == []
    await db.execute(delete(Share).where(Share.id.in_((share.id, by_address.id))))
    await db.commit()
