"""audio-player's counting, called as a source module calls it
(`dev plans/contracts/audio-player.md` §2, §3 and §7): once per listener per
item per day, a salt per day even when two first plays race, `forget`, `plays`,
the seed's `add_daily`, the prune, and no row holding anything that identifies
a visitor."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from audio_player import jobs, public, service
from audio_player.models import Daily, Play, Salt
from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database

from ..conftest import far_day, item

pytestmark = pytest.mark.db
SOURCE = "discography.track"
#: Each of the module's tables, every column of a row read as one string.
EVERY_ROW_AS_TEXT = {
    "audio_player_salt": text(
        "SELECT count(*) FROM audio_player_salt AS row WHERE row::text LIKE :needle"
    ),
    "audio_player_play": text(
        "SELECT count(*) FROM audio_player_play AS row WHERE row::text LIKE :needle"
    ),
    "audio_player_play_daily": text(
        "SELECT count(*) FROM audio_player_play_daily AS row WHERE row::text LIKE :needle"
    ),
}


def visit(address: str = "203.0.113.7", agent: str = "Mozilla/5.0 (Test)") -> Request:
    """A request from `address` in a browser that calls itself `agent`."""
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"user-agent", agent.encode())],
            "client": (address, 51000),
            "app": SimpleNamespace(state=SimpleNamespace()),
        }
    )


def on(monkeypatch: pytest.MonkeyPatch, day: date) -> None:
    monkeypatch.setattr(service, "today", lambda: day)


async def _daily(db: AsyncSession, item_id: uuid.UUID, day: date) -> int | None:
    found = await db.scalar(
        select(Daily.plays).where(
            Daily.source == SOURCE, Daily.item_id == item_id, Daily.day == day
        )
    )
    await db.rollback()
    return found


async def test_a_listener_counts_once_per_item_a_day(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    day, track = far_day(), item()
    on(monkeypatch, day)
    assert await public.count(db, visit(), source=SOURCE, item_id=track)
    await db.commit()
    assert not await public.count(db, visit(), source=SOURCE, item_id=track)
    await db.commit()
    assert await _daily(db, track, day) == 1


async def test_another_address_browser_or_day_counts_again(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    day, track = far_day(), item()
    on(monkeypatch, day)
    assert await public.count(db, visit(), source=SOURCE, item_id=track)
    assert await public.count(db, visit(address="198.51.100.4"), source=SOURCE, item_id=track)
    assert await public.count(db, visit(agent="Other/2.0"), source=SOURCE, item_id=track)
    # Another item, by the same listener, counts on its own.
    assert await public.count(db, visit(), source=SOURCE, item_id=item())
    await db.commit()
    assert await _daily(db, track, day) == 3
    on(monkeypatch, day + timedelta(days=1))
    assert await public.count(db, visit(), source=SOURCE, item_id=track)
    await db.commit()
    assert await _daily(db, track, day + timedelta(days=1)) == 1


async def test_an_ipv6_listener_is_their_slash_64(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    on(monkeypatch, far_day())
    track = item()
    assert await public.count(db, visit(address="2001:db8:1:2::10"), source=SOURCE, item_id=track)
    assert not await public.count(
        db, visit(address="2001:db8:1:2::99"), source=SOURCE, item_id=track
    )
    await db.rollback()


async def test_a_salt_is_the_days_own(db: AsyncSession) -> None:
    one, two = far_day(), far_day()
    first = await service.salt_for(db, one)
    assert len(first) == 32
    assert await service.salt_for(db, one) == first
    assert await service.salt_for(db, two) != first
    await db.rollback()


async def _blocked(probe: AsyncSession, actor: int, holder: int) -> None:
    """Until the holder's backend blocks the actor's, for 5 seconds at most."""
    for _ in range(100):
        blocked = await probe.scalar(
            text("SELECT CAST(:holder AS integer) = ANY(pg_blocking_pids(:actor))"),
            {"holder": holder, "actor": actor},
        )
        await probe.rollback()
        if blocked:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("The second play never waited on the first's salt.")


async def test_two_first_plays_of_a_day_at_once_make_one_salt(database: Database) -> None:
    """The first play's salt is still uncommitted when the second asks for the
    day's: the second waits on it, then reads it. Checked with a mutant: with a
    plain INSERT in `salt_for`, the second raises a unique violation."""
    day = far_day()
    async with (
        database.sessions() as holder,
        database.sessions() as actor,
        database.sessions() as probe,
    ):
        mine = await service.salt_for(holder, day)
        holder_pid = int(await holder.scalar(text("SELECT pg_backend_pid()")) or 0)
        actor_pid = int(await actor.scalar(text("SELECT pg_backend_pid()")) or 0)
        second = asyncio.ensure_future(service.salt_for(actor, day))
        await _blocked(probe, actor_pid, holder_pid)
        await holder.commit()
        assert await second == mine
        await actor.commit()
        assert await probe.scalar(select(func.count()).where(Salt.day == day)) == 1


async def test_forget_takes_only_those_items(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    day = far_day()
    on(monkeypatch, day)
    gone, kept = item(), item()
    for each in (gone, kept):
        assert await public.count(db, visit(), source=SOURCE, item_id=each)
    await db.commit()
    await public.forget(db, SOURCE, [gone])
    await db.commit()
    assert await _daily(db, gone, day) is None
    assert await _daily(db, kept, day) == 1
    left = await db.scalar(select(func.count()).where(Play.item_id == gone))
    assert left == 0
    await db.rollback()
    # Another source's item of the same id isn't this one.
    await public.add_daily(db, "radio.show", kept, day, 4)
    await public.forget(db, "radio.show", [kept])
    await db.commit()
    assert await _daily(db, kept, day) == 1


async def test_plays_adds_up_the_days_asked_for(db: AsyncSession) -> None:
    start, track, other = far_day(), item(), item()
    for offset, count in ((0, 3), (1, 4), (2, 5)):
        await public.add_daily(db, SOURCE, track, start + timedelta(days=offset), count)
    await public.add_daily(db, SOURCE, other, start, 2)
    await db.commit()
    found = await public.plays(db, SOURCE, since=start, until=start + timedelta(days=1))
    assert found == {track: 7, other: 2}
    assert await public.plays(db, SOURCE, since=start + timedelta(days=2), until=start) == {}
    later = await public.plays(
        db, SOURCE, since=start + timedelta(days=2), until=start + timedelta(days=2)
    )
    assert later == {track: 5}
    await db.rollback()


async def test_add_daily_run_twice_leaves_the_same(db: AsyncSession) -> None:
    day, track = far_day(), item()
    for _ in range(2):
        await public.add_daily(db, SOURCE, track, day, 9)
        await db.commit()
    assert await _daily(db, track, day) == 9
    with pytest.raises(ValueError, match="negative"):
        await public.add_daily(db, SOURCE, track, day, -1)


@pytest.mark.parametrize("source", ["", "discography", "Discography.track", "a.b.c", "x" * 41])
async def test_a_source_is_module_dot_type(db: AsyncSession, source: str) -> None:
    with pytest.raises(ValueError, match=r"<module>.<type>"):
        await public.count(db, visit(), source=source, item_id=item())
    with pytest.raises(ValueError, match=r"<module>.<type>"):
        await public.forget(db, source, [item()])
    await db.rollback()


async def test_no_row_holds_the_address_or_the_browser(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    on(monkeypatch, far_day())
    address, agent = "192.0.2.201", f"Marker/{uuid.uuid4().hex}"
    assert await public.count(db, visit(address, agent), source=SOURCE, item_id=item())
    await db.commit()
    for table, query in EVERY_ROW_AS_TEXT.items():
        for needle in (address, agent, agent.encode().hex()):
            found = await db.scalar(query, {"needle": f"%{needle}%"})
            assert found == 0, (table, needle)
    await db.rollback()


async def test_the_prune_keeps_today_and_two_years_of_totals(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    today = far_day()
    yesterday, old, kept = (
        today - timedelta(days=1),
        today - timedelta(days=731),
        today - timedelta(days=730),
    )
    track = item()
    async with database.sessions() as db:
        for day in (yesterday, today):
            on(monkeypatch, day)
            assert await public.count(db, visit(), source=SOURCE, item_id=track)
        await public.add_daily(db, SOURCE, track, old, 6)
        await public.add_daily(db, SOURCE, track, kept, 8)
        await db.commit()
    on(monkeypatch, today)
    ctx = SimpleNamespace(sessions=database.sessions)
    await jobs.prune.run(ctx, {})  # type: ignore[arg-type]
    async with database.sessions() as db:
        days = set(await db.scalars(select(Play.day).where(Play.item_id == track)))
        assert days == {today}
        assert await db.scalar(select(func.count()).where(Salt.day == yesterday)) == 0
        assert await db.scalar(select(func.count()).where(Salt.day == today)) == 1
        totals = set(await db.scalars(select(Daily.day).where(Daily.item_id == track)))
        assert totals == {kept, yesterday, today}
    # Run twice, it deletes nothing more of today's.
    await jobs.prune.run(ctx, {})  # type: ignore[arg-type]
    async with database.sessions() as db:
        assert await db.scalar(select(func.count()).where(Play.item_id == track)) == 1
