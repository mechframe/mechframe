"""Item references (decision 0072, the tenth hook; `dev plans/contracts/featured.md`
Â§2, "The hook"): a module's `refs.py`'s `REFS`, found by `load_module`, checked
at the start, and read through `kernel.refs` for the modules that are on."""

from __future__ import annotations

import sys
import textwrap
import uuid
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import refs
from kernel.modules import InstalledModule, Manifest, load_module

ALBUM = uuid.UUID("11111111-1111-4111-8111-111111111111")
DRAFT = uuid.UUID("22222222-2222-4222-8222-222222222222")


class Tracks(refs.Source):
    type = "music.track"
    label = "Tracks"

    def __init__(self) -> None:
        self.asked: list[tuple[Any, ...]] = []
        self.rows = {
            ALBUM: refs.Ref(ALBUM, "Gather Around", "Unified Vibration", None, "/music/uv", True),
            DRAFT: refs.Ref(DRAFT, "Pray For You", "Unified Vibration", None, None, False),
        }

    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        self.asked.append(("find", tuple(ids)))
        return {each: self.rows[each] for each in ids if each in self.rows}

    async def pick(
        self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int
    ) -> refs.RefPage:
        self.asked.append(("pick", q, cursor, limit))
        return {"items": list(self.rows.values())[:limit], "next_cursor": None}


def _module(module_id: str, *sources: Any) -> InstalledModule:
    manifest = Manifest.from_dict(
        {
            "id": module_id,
            "name": module_id.title(),
            "version": "0.1.0",
            "requires": {"modules": {}},
        }
    )
    return InstalledModule(manifest, referable=tuple(sources))


class Switches:
    """The modules on, as the registry answers."""

    def __init__(self, *on: str) -> None:
        self.on_now = frozenset(on)

    async def on(self, db: Any, *, fresh: bool = False) -> frozenset[str]:
        return self.on_now


@pytest.fixture
def tracks() -> Iterator[Tracks]:
    source = Tracks()
    refs.install(refs.build([_module("music", source), _module("blog")]), Switches("music"))
    yield source
    refs.install({}, None)


# --- the start's checks ------------------------------------------------------------------


def test_only_the_module_that_takes_part_shows() -> None:
    found = refs.build([_module("music", Tracks()), _module("blog")])
    assert list(found) == ["music.track"]


@pytest.mark.parametrize(
    ("module_id", "kind", "label"),
    [
        ("blog", "music.track", "Tracks"),  # another module's type
        ("music", "music", "Tracks"),  # not <module>.<name>
        ("music", "music.Track", "Tracks"),
        ("music", "music.track", ""),  # no label
    ],
)
def test_a_type_the_module_may_not_give_is_refused(module_id: str, kind: str, label: str) -> None:
    source = Tracks()
    source.type, source.label = kind, label
    with pytest.raises(ValueError, match=module_id):
        refs.build([_module(module_id, source)])


def test_what_isnt_a_source_and_a_type_given_twice_are_refused() -> None:
    with pytest.raises(ValueError, match=r"isn't a refs\.Source"):
        refs.build([_module("music", object())])
    with pytest.raises(ValueError, match="twice"):
        refs.build([_module("music", Tracks(), Tracks())])


def test_load_module_finds_refs_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Discovery itself: a test that builds InstalledModule by hand passes without it.
    package = tmp_path / "pointed_at"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "refs.py").write_text(textwrap.dedent("""
            from kernel import refs

            class Things(refs.Source):
                type = "pointed-at.thing"
                label = "Things"

                async def find(self, db, ids):
                    return {}

                async def pick(self, db, q, *, cursor, limit):
                    return {"items": [], "next_cursor": None}

            REFS = (Things(),)
            """))
    manifest = tmp_path / "module.json"
    manifest.write_text('{"id": "pointed-at", "name": "Pointed at", "version": "0.1.0"}')
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        found = load_module(manifest)
        assert [source.type for source in found.referable] == ["pointed-at.thing"]
        assert list(refs.build([found])) == ["pointed-at.thing"]
    finally:
        for name in [each for each in sys.modules if each.startswith("pointed_at")]:
            del sys.modules[name]


# --- the reads -----------------------------------------------------------------------------


async def test_types_names_each_type_of_the_modules_on(tracks: Tracks) -> None:
    assert await refs.types(None) == {"music.track": "Tracks"}  # type: ignore[arg-type]
    refs.install(refs.build([_module("music", tracks)]), Switches())
    assert await refs.types(None) == {}  # type: ignore[arg-type]


async def test_find_reaches_the_source_with_each_id_once(tracks: Tracks) -> None:
    gone = uuid.uuid4()
    found = await refs.find(None, "music.track", [ALBUM, ALBUM, DRAFT, gone])  # type: ignore[arg-type]
    assert set(found) == {ALBUM, DRAFT}  # a gone id is left out
    assert (found[ALBUM].live, found[DRAFT].live, found[DRAFT].path) == (True, False, None)
    assert tracks.asked == [("find", (ALBUM, DRAFT, gone))]
    assert await refs.find(None, "music.track", []) == {}  # type: ignore[arg-type]
    assert len(tracks.asked) == 1  # nothing to look up asks nothing


async def test_pick_reaches_the_source_within_its_limits(tracks: Tracks) -> None:
    page = await refs.pick(None, "music.track", "  gather  ", cursor=None, limit=1)  # type: ignore[arg-type]
    assert [each.title for each in page["items"]] == ["Gather Around"]
    assert tracks.asked == [("pick", "gather", None, 1)]
    await refs.pick(None, "music.track", "   ", cursor=None)  # type: ignore[arg-type]
    assert tracks.asked[-1] == ("pick", None, None, refs.PICK_LIMIT)
    for limit in (0, refs.MAX_PICK + 1):
        with pytest.raises(ValueError, match="1 to"):
            await refs.pick(None, "music.track", None, cursor=None, limit=limit)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at most"):
        await refs.pick(None, "music.track", "x" * (refs.MAX_QUERY + 1), cursor=None)  # type: ignore[arg-type]


async def test_a_type_no_module_on_gives_is_unknown(tracks: Tracks) -> None:
    with pytest.raises(refs.UnknownType):
        await refs.find(None, "shop.product", [ALBUM])  # type: ignore[arg-type]
    refs.install(refs.build([_module("music", tracks)]), Switches("blog"))
    for read in (
        refs.find(None, "music.track", [ALBUM]),  # type: ignore[arg-type]
        refs.pick(None, "music.track", None, cursor=None),  # type: ignore[arg-type]
    ):
        with pytest.raises(refs.UnknownType):
            await read
    assert tracks.asked == []  # a module that's off is never asked


async def test_find_answers_only_what_was_asked(tracks: Tracks) -> None:
    # A source that answers more than it was asked for, or under another id, is held to the ask.
    stray = uuid.uuid4()
    tracks.rows[stray] = refs.Ref(stray, "Stray", "", None, None, True)

    async def everything(db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, refs.Ref]:
        return {ALBUM: tracks.rows[DRAFT], stray: tracks.rows[stray]}

    tracks.find = everything  # type: ignore[method-assign]
    assert await refs.find(None, "music.track", [ALBUM]) == {}  # type: ignore[arg-type]
