"""The backend tests' own fixtures: `kernel.refs` holds a source of made-up
things (`music.track`), whose module a test may switch off, as featured's
tests do; settings know reactions' section; and people are accounts in the
database, verified or not."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import refs
from kernel.settings import settings

from ..conftest import make_person


@dataclass
class Things(refs.Source):
    """Things of one type, in memory: `add` one, `drop` it, or make it a draft."""

    type: str = "music.track"
    label: str = "Tracks"
    items: dict[uuid.UUID, refs.Ref] = field(default_factory=dict)
    asked: list[list[uuid.UUID]] = field(default_factory=list)

    def add(self, *, live: bool = True) -> uuid.UUID:
        ident = uuid.uuid4()
        self.items[ident] = refs.Ref(
            ident, "Catalyst", "petro and J Tone", None, f"/music/{ident.hex[:8]}", live
        )
        return ident

    def drop(self, ident: uuid.UUID) -> None:
        del self.items[ident]

    def draft(self, ident: uuid.UUID) -> None:
        self.items[ident] = replace(self.items[ident], live=False, path=None)

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        self.asked.append(list(ids))
        return {each: self.items[each] for each in ids if each in self.items}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        return {"items": list(self.items.values())[:limit], "next_cursor": None}


class Switches:
    """Which modules are on: `music` until a test turns it off."""

    def __init__(self) -> None:
        self.off: set[str] = set()

    async def on(self, db: AsyncSession, *, fresh: bool = False) -> frozenset[str]:
        return frozenset({"music"} - self.off)


@dataclass
class Sources:
    tracks: Things
    switches: Switches


@pytest.fixture
def sources() -> Iterator[Sources]:
    tracks = Things()
    switches = Switches()
    refs.install({"music.track": tracks}, switches)
    yield Sources(tracks, switches)
    refs.install({}, None)


@pytest.fixture(autouse=True)
def reactions_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings know reactions' section, as an app with it on does."""
    from reactions.schemas import Settings

    monkeypatch.setitem(settings.models, "reactions", Settings)


@dataclass(frozen=True)
class Who:
    """A person as the routes hand one to the service."""

    id: uuid.UUID
    email: str
    email_verified_at: datetime | None


async def member(db: AsyncSession, *, verified: bool = True) -> Who:
    """An account in the database, its address verified unless asked otherwise."""
    ident, email = await make_person(db)
    return Who(ident, email, datetime(2026, 11, 1, tzinfo=UTC) if verified else None)
