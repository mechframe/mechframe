"""Item references: what another module may point at (decision 0072, hook
11; `dev plans/contracts/featured.md` §2, "The hook"; SPEC.md
sections 6 and 7).

A module whose things another may pick, list or show as gone gives a source
for each kind of thing in its `refs.py`:

    class Tracks(refs.Source):
        type = "discography.track"
        label = "Tracks"

        async def find(self, db, ids):
            return {track.id: refs.Ref(track.id, track.title, ...) for track in ...}

        async def pick(self, db, q, *, cursor, limit):
            return {"items": [...], "next_cursor": None}

    REFS = (Tracks(),)

A module that points at things (featured's slots) stores `{type, id}` and
asks `kernel.refs`, never the module: so neither requires the other. A module
that doesn't take part gives no `refs.py` and loses nothing.

- **`find`** answers the things among `ids` that are there, drafts too, each
  with `live` saying whether the site shows it now; an id left out is gone.
- **`pick`** answers a page of things to choose from, matching `q`.
- **Only the modules that are on are asked:** a type whose module is off,
  or that no module gives, is `UnknownType`.
- **No HTTP route of the kernel's:** a module that points answers through
  its own routes, under its own permission.
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from kernel.modules import InstalledModule

#: A thing's type, `<module id>.<name>`, as discography's `discography.track`,
#: and its longest: what a module that points stores it in (CubicDev on #153).
TYPE = re.compile(r"[a-z][a-z0-9-]*\.[a-z][a-z0-9_]*")
MAX_TYPE = 80
#: The ids one `find` may ask for.
MAX_IDS = 200
#: A page of `pick`: its size when none is asked, and the largest.
PICK_LIMIT = 20
MAX_PICK = 50
#: The characters of a `pick`'s words.
MAX_QUERY = 200


@dataclass(frozen=True)
class Ref:
    """One thing as a module that points at it shows it."""

    id: uuid.UUID
    #: "Catalyst (full album)".
    title: str
    #: The words under it: "Catalyst, petro and J Tone".
    line: str
    #: A small picture's address, such as a cover's, or None.
    image: str | None
    #: Its page on the site while the site shows it, else None.
    path: str | None
    #: Whether the site shows it now.
    live: bool


class RefPage(TypedDict):
    items: list[Ref]
    next_cursor: str | None


class Source(ABC):
    """A module's things of one type, `type`, named `label` ("Tracks")."""

    type: str
    label: str

    @abstractmethod
    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Ref]:
        """The things among `ids` that are there, drafts too, by id: an id
        left out is gone."""

    @abstractmethod
    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> RefPage:
        """A page of things to choose from, drafts too: those matching `q`
        when it's given, newest edit first, at most `limit`."""


class UnknownType(LookupError):
    """A type no module that's on gives."""


class _Switches(Protocol):
    async def on(self, db: AsyncSession, *, fresh: bool = False) -> frozenset[str]: ...


# --- the start's checks ------------------------------------------------------------------


def build(installed: Iterable[InstalledModule]) -> dict[str, Source]:
    """Every type another module may point at, and its source. ValueError,
    naming the module, for what isn't a source, a type that isn't the
    module's own `<id>.<name>`, a source without a label, or a type given twice."""
    found: dict[str, Source] = {}
    for module in installed:
        for source in module.referable:
            if not isinstance(source, Source):
                raise ValueError(f"{module.id}'s {source!r} in REFS isn't a refs.Source.")
            kind = getattr(source, "type", None)
            if (
                not isinstance(kind, str)
                or len(kind) > MAX_TYPE
                or not TYPE.fullmatch(kind)
                or kind.partition(".")[0] != module.id
            ):
                raise ValueError(
                    f"{module.id} may only give {module.id}.<name> types in REFS, "
                    f"{MAX_TYPE} characters at most, not {kind!r}."
                )
            label = getattr(source, "label", None)
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"{module.id}'s {kind} in REFS has no label.")
            if kind in found:
                raise ValueError(f"The type {kind} is given twice in REFS.")
            found[kind] = source
    return found


_sources: dict[str, Source] = {}
_switches: _Switches | None = None


def install(sources: Mapping[str, Source], switches: _Switches | None) -> None:
    """Sets the sources, and the modules' switches it asks which are on:
    `assemble` calls it. Without switches, every source counts as on."""
    global _sources, _switches
    _sources = dict(sources)
    _switches = switches


async def _on(db: AsyncSession) -> dict[str, Source]:
    if _switches is None:
        return dict(_sources)
    on = await _switches.on(db)
    return {kind: source for kind, source in _sources.items() if kind.partition(".")[0] in on}


async def _source(db: AsyncSession, kind: str) -> Source:
    found = (await _on(db)).get(kind)
    if found is None:
        raise UnknownType(f"No module that's on gives the type {kind!r}.")
    return found


# --- the reads ---------------------------------------------------------------------------


async def types(db: AsyncSession) -> dict[str, str]:
    """Each type of the modules on, by type: its label."""
    return {kind: source.label for kind, source in sorted((await _on(db)).items())}


async def find(db: AsyncSession, type: str, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, Ref]:
    """The things of `type` among `ids` that are there, by id: an id left out
    is gone. Each id is asked once, and only what was asked is answered.
    UnknownType for a type no module on gives; ValueError past MAX_IDS."""
    wanted = list(dict.fromkeys(ids))
    source = await _source(db, type)
    if not wanted:
        return {}
    if len(wanted) > MAX_IDS:
        raise ValueError(f"At most {MAX_IDS} ids are looked up at once.")
    answered = await source.find(db, wanted)
    asked = set(wanted)
    return {
        each: ref
        for each, ref in answered.items()
        if each in asked and isinstance(ref, Ref) and ref.id == each
    }


async def pick(
    db: AsyncSession, type: str, q: str | None, *, cursor: str | None, limit: int = PICK_LIMIT
) -> RefPage:
    """A page of things of `type` to choose from, matching `q` when it has
    words. UnknownType for a type no module on gives; ValueError for a limit
    outside 1 to MAX_PICK or words past MAX_QUERY, and for a source's page
    that holds more than `limit`, or anything but a `Ref`, or a cursor that
    isn't a string: cutting it would lose what its next cursor has passed
    (CubicDev on #153)."""
    if not 1 <= limit <= MAX_PICK:
        raise ValueError(f"A page holds 1 to {MAX_PICK} things.")
    words = (q or "").strip() or None
    if words is not None and len(words) > MAX_QUERY:
        raise ValueError(f"A search is at most {MAX_QUERY} characters.")
    source = await _source(db, type)
    page = await source.pick(db, words, cursor=cursor, limit=limit)
    items, after = page.get("items"), page.get("next_cursor")
    if (
        not isinstance(items, list)
        or len(items) > limit
        or not all(isinstance(each, Ref) for each in items)
        or not (after is None or isinstance(after, str))
    ):
        raise ValueError(
            f"{type.partition('.')[0]}'s {type} answered a page that isn't at most {limit} refs.Ref "
            "with a string or null next_cursor."
        )
    return {"items": items, "next_cursor": after}
