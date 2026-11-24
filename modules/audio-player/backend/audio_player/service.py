"""All of audio-player's logic (`dev plans/contracts/audio-player.md` §2 and §3).

Counting a play, without keeping anyone's details:

1. The day (UTC) has one random salt, made by its first play. Two first plays
   at once both insert it with `ON CONFLICT DO NOTHING`: one wins, the other
   waits for it and reads the winner's salt.
2. The listener is an HMAC-SHA256 of the visitor's address, as the rate limits
   read it, and their browser's name, under that salt.
3. A row `(day, source, item, listener)` is inserted if it isn't there. Only a
   new row adds one to the item's daily total, in the same transaction.

The prune deletes yesterday's salt and rows, so a hash can't be traced back,
and daily totals two years old.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from collections.abc import Iterable
from datetime import date, timedelta
from typing import cast

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from audio_player.models import MAX_SOURCE, SALT_BYTES, Daily, Play, Salt
from audio_player.schemas import Settings
from kernel import client_address, clock
from kernel import settings as module_settings

MODULE = "audio-player"
#: `<module>.<type>`, such as `discography.track`.
SOURCE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")
#: How much of a browser's name goes into the hash: enough to tell browsers apart.
MAX_AGENT = 512
#: How long daily totals are kept (§8, 3).
KEEP_DAILY = timedelta(days=730)


async def current(db: AsyncSession) -> Settings:
    return cast(Settings, await module_settings.for_module(db, MODULE))


def today() -> date:
    """The day a play counts on: a UTC day, as the kernel keeps time."""
    return clock.now().date()


def checked_source(source: str) -> str:
    """`source` as given, refused unless it's `<module>.<type>`."""
    if len(source) > MAX_SOURCE or not SOURCE.match(source):
        raise ValueError(f"A play's source is '<module>.<type>', not {source!r}.")
    return source


async def salt_for(db: AsyncSession, day: date) -> bytes:
    """The day's salt, made now if this is its first play."""
    await db.execute(
        insert(Salt)
        .values(day=day, salt=secrets.token_bytes(SALT_BYTES))
        .on_conflict_do_nothing(index_elements=[Salt.day])
    )
    found = await db.scalar(select(Salt.salt).where(Salt.day == day))
    if found is None:  # only if the row was deleted between the two statements
        raise RuntimeError(f"No salt for {day}.")
    return bytes(found)


def listener(salt: bytes, address: str, agent: str) -> str:
    """Who's listening, as a hex HMAC no one can read back without the day's salt."""
    message = f"{address}\n{agent[:MAX_AGENT]}".encode()
    return hmac.new(salt, message, hashlib.sha256).hexdigest()


async def count(db: AsyncSession, request: Request, *, source: str, item_id: uuid.UUID) -> bool:
    """One play of the item, unless this listener was counted for it today.
    True when it counted. Written in the caller's transaction, never committed."""
    checked_source(source)
    day = today()
    salt = await salt_for(db, day)
    who = listener(salt, client_address(request), request.headers.get("user-agent", ""))
    added = await db.execute(
        insert(Play)
        .values(day=day, source=source, item_id=item_id, listener=who)
        .on_conflict_do_nothing()
        .returning(Play.day)
    )
    if added.first() is None:
        return False
    await db.execute(
        insert(Daily)
        .values(source=source, item_id=item_id, day=day, plays=1)
        .on_conflict_do_update(
            index_elements=[Daily.source, Daily.item_id, Daily.day],
            set_={"plays": Daily.plays + 1},
        )
    )
    return True


async def forget(db: AsyncSession, source: str, item_ids: Iterable[uuid.UUID]) -> None:
    """Every play of these items, in the caller's transaction: for an item that's gone."""
    checked_source(source)
    ids = list(set(item_ids))
    if not ids:
        return
    await db.execute(delete(Play).where(Play.source == source, Play.item_id.in_(ids)))
    await db.execute(delete(Daily).where(Daily.source == source, Daily.item_id.in_(ids)))


async def plays(db: AsyncSession, source: str, *, since: date, until: date) -> dict[uuid.UUID, int]:
    """Each item's plays from `since` to `until`, both days included; items with none left out."""
    checked_source(source)
    rows = await db.execute(
        select(Daily.item_id, func.sum(Daily.plays))
        .where(Daily.source == source, Daily.day >= since, Daily.day <= until)
        .group_by(Daily.item_id)
    )
    return {item: int(total) for item, total in rows if total}


async def add_daily(
    db: AsyncSession, source: str, item_id: uuid.UUID, day: date, plays: int
) -> None:
    """Set an item's total for a day, for a seed: run twice, it leaves the same."""
    checked_source(source)
    if plays < 0:
        raise ValueError("A day's plays can't be negative.")
    await db.execute(
        insert(Daily)
        .values(source=source, item_id=item_id, day=day, plays=plays)
        .on_conflict_do_update(
            index_elements=[Daily.source, Daily.item_id, Daily.day], set_={"plays": plays}
        )
    )


async def prune(db: AsyncSession) -> int:
    """Yesterday's salts and listeners, and daily totals past two years: how many rows went."""
    day = today()
    gone = 0
    for statement in (
        delete(Play).where(Play.day < day),
        delete(Salt).where(Salt.day < day),
        delete(Daily).where(Daily.day < day - KEEP_DAILY),
    ):
        result = cast(CursorResult[object], await db.execute(statement))
        gone += result.rowcount or 0
    return gone
