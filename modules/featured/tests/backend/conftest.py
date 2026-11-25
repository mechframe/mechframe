"""The backend tests' own fixtures: the kernel's registries hold featured's
actions and settings, as an app with it on does; `kernel.refs` holds two
sources of made-up things (`music.track` and `music.album`), whose module a
test may switch off; and events said are kept for the test to read."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import audit, events, refs
from kernel.settings import settings


@dataclass
class Things(refs.Source):
    """Things of one type, in memory: `add` one, `drop` it, or make it a draft."""

    type: str = "music.track"
    label: str = "Tracks"
    items: dict[uuid.UUID, refs.Ref] = field(default_factory=dict)
    asked: list[Any] = field(default_factory=list)
    #: Seconds `find` waits, for a save the test holds in the middle.
    pause: float = 0.0

    def add(self, title: str = "Catalyst (full album)", *, live: bool = True) -> uuid.UUID:
        ident = uuid.uuid4()
        self.items[ident] = refs.Ref(
            ident,
            title,
            "Catalyst, petro and J Tone",
            "https://files.test/cover.jpg",
            f"/music/{ident.hex[:8]}" if live else None,
            live,
        )
        return ident

    def drop(self, ident: uuid.UUID) -> None:
        del self.items[ident]

    def draft(self, ident: uuid.UUID) -> None:
        self.items[ident] = replace(self.items[ident], live=False, path=None)

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        import asyncio

        self.asked.append(("find", list(ids)))
        if self.pause:
            await asyncio.sleep(self.pause)
        return {each: self.items[each] for each in ids if each in self.items}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        self.asked.append(("pick", q, cursor, limit))
        found = [each for each in self.items.values() if not q or q.lower() in each.title.lower()]
        return {"items": found[:limit], "next_cursor": "more" if len(found) > limit else None}


class Switches:
    """Which modules are on: `music` until a test turns it off."""

    def __init__(self) -> None:
        self.off: set[str] = set()

    async def on(self, db: AsyncSession, *, fresh: bool = False) -> frozenset[str]:
        return frozenset({"music"} - self.off)


@dataclass
class Sources:
    tracks: Things
    albums: Things
    switches: Switches


@pytest.fixture
def sources() -> Iterator[Sources]:
    tracks = Things()
    albums = Things(type="music.album", label="Albums")
    switches = Switches()
    refs.install({"music.track": tracks, "music.album": albums}, switches)
    yield Sources(tracks, albums, switches)
    refs.install({}, None)


@pytest.fixture(autouse=True)
def said(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Every event featured says, by name and payload."""
    heard: list[tuple[str, Any]] = []

    async def emit(db: Any, name: str, payload: Any) -> int:
        heard.append((name, payload))
        return 1

    monkeypatch.setattr(events, "emit", emit)
    return heard


@pytest.fixture(autouse=True)
def featured_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit log takes featured's actions, and settings know its section."""
    from featured.schemas import Settings

    monkeypatch.setattr(audit, "_owners", audit._owners | {"featured"})
    monkeypatch.setitem(settings.models, "featured", Settings)
