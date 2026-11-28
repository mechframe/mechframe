"""reactions' logic (`dev plans/contracts/reactions.md` §2): the counts of the
things asked about, a person's press and its taking back, and the weekly sweep.

A thing is named by its content type and id, and `kernel.refs.find` says
whether it's there and live: reactions never reads another module's rows. Only
a live thing is answered or reacted to; a type no module on gives is
`reactions.unknown_type`, a thing gone or hidden `reactions.not_found`.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol, cast

import sqlalchemy as sa
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, refs
from kernel import settings as module_settings
from reactions.models import Reaction
from reactions.schemas import BUILT_IN, Settings

RATE_VARIABLE = "REACTIONS_RATE_LIMIT"
DEFAULT_RATE = "60/1m"


class Person(Protocol):
    @property
    def id(self) -> uuid.UUID: ...

    @property
    def email_verified_at(self) -> datetime | None: ...


def rate_rule() -> str:
    """REACTIONS_RATE_LIMIT: the reactions one person may add or take back."""
    return (os.environ.get(RATE_VARIABLE) or "").strip() or DEFAULT_RATE


async def palette(db: AsyncSession) -> list[str]:
    """The reactions offered, in the row's order."""
    found = cast(Settings, await module_settings.for_module(db, "reactions"))
    return list(found.palette)


async def _live(db: AsyncSession, kind: str, ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
    """The things among `ids` the site shows now."""
    try:
        found = await refs.find(db, kind, ids)
    except refs.UnknownType:
        raise Problem("reactions.unknown_type", 404, f"Nothing on this site is a {kind}.") from None
    return {each for each, ref in found.items() if ref.live}


async def _thing(db: AsyncSession, kind: str, ident: uuid.UUID) -> None:
    if ident not in await _live(db, kind, [ident]):
        raise Problem("reactions.not_found", 404, "That isn't on the site now.")


async def _counted(
    db: AsyncSession,
    kind: str,
    ids: Sequence[uuid.UUID],
    person: Person | None,
    keys: Sequence[str],
) -> list[dict[str, Any]]:
    """Each thing's count of each key, 0 included, and the person's own."""
    if not ids:
        return []
    # One statement, so the counts and the reader's own come from one snapshot
    # (CodeRabbit on #170): two would each take their own under READ COMMITTED.
    theirs = func.bool_or(Reaction.user_id == person.id) if person is not None else sa.false()
    rows = await db.execute(
        select(Reaction.target_id, Reaction.key, func.count(), theirs)
        .where(
            Reaction.target_type == kind,
            Reaction.target_id.in_(ids),
            Reaction.key.in_(keys),
        )
        .group_by(Reaction.target_id, Reaction.key)
    )
    counts: dict[tuple[uuid.UUID, str], int] = {}
    mine: set[tuple[uuid.UUID, str]] = set()
    for target, key, n, own in rows:
        counts[(target, key)] = int(n)
        if own:
            mine.add((target, key))
    return [
        {
            "id": str(each),
            "counts": {key: counts.get((each, key), 0) for key in keys},
            "mine": [key for key in keys if (each, key) in mine],
        }
        for each in ids
    ]


async def counted(
    db: AsyncSession, kind: str, ids: Sequence[uuid.UUID], person: Person | None
) -> dict[str, Any]:
    """What `GET` answers: the palette, and the things asked about that are live now, in order."""
    keys = await palette(db)
    asked = list(dict.fromkeys(ids))
    live = await _live(db, kind, asked)
    return {
        "palette": [{"key": key, "label": BUILT_IN[key]} for key in keys],
        "items": await _counted(db, kind, [each for each in asked if each in live], person, keys),
    }


async def react(
    db: AsyncSession, person: Person, kind: str, ident: uuid.UUID, key: str
) -> dict[str, Any]:
    """The person's reaction added: pressing twice, or twice at once, adds one."""
    if person.email_verified_at is None:
        raise Problem("reactions.email_unverified", 403, "Verify your email address first.")
    await _thing(db, kind, ident)
    keys = await palette(db)
    if key not in keys:
        raise Problem("reactions.unknown_key", 422, f"{key} isn't one of this site's reactions.")
    await db.execute(
        insert(Reaction)
        .values(id=uuid.uuid4(), target_type=kind, target_id=ident, user_id=person.id, key=key)
        .on_conflict_do_nothing(
            index_elements=[
                Reaction.target_type,
                Reaction.target_id,
                Reaction.user_id,
                Reaction.key,
            ]
        )
    )
    return (await _counted(db, kind, [ident], person, keys))[0]


async def unreact(
    db: AsyncSession, person: Person, kind: str, ident: uuid.UUID, key: str
) -> dict[str, Any]:
    """The person's reaction taken back, if they had it: only their own, ever.
    A key taken out of the palette can still be taken back."""
    await _thing(db, kind, ident)
    if key not in BUILT_IN:
        raise Problem("reactions.unknown_key", 422, f"{key} isn't a reaction.")
    await db.execute(
        delete(Reaction).where(
            Reaction.target_type == kind,
            Reaction.target_id == ident,
            Reaction.user_id == person.id,
            Reaction.key == key,
        )
    )
    return (await _counted(db, kind, [ident], person, await palette(db)))[0]


async def sweep(db: AsyncSession) -> int:
    """The reactions of things that are gone deleted: how many. A thing that's
    only hidden keeps them, and a type whose module is off, or that no module
    gives, is skipped, so switching a module off never loses its reactions."""
    on = await refs.types(db)
    gone = 0
    kinds = list(await db.scalars(select(Reaction.target_type).distinct()))
    for kind in kinds:
        if kind not in on:
            continue
        ids = list(
            await db.scalars(
                select(Reaction.target_id)
                .where(Reaction.target_type == kind)
                .distinct()
                .order_by(Reaction.target_id)
            )
        )
        for start in range(0, len(ids), refs.MAX_IDS):
            batch = ids[start : start + refs.MAX_IDS]
            try:
                there = await refs.find(db, kind, batch)
            except refs.UnknownType:  # switched off since it was listed
                break
            missing = [each for each in batch if each not in there]
            if missing:
                result = await db.execute(
                    delete(Reaction).where(
                        Reaction.target_type == kind, Reaction.target_id.in_(missing)
                    )
                )
                gone += cast(Any, result).rowcount or 0
    return gone
