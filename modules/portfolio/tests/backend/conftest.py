"""The backend tests' own fixtures: the kernel's registries hold portfolio's
type, its vocabulary and its settings, as an app with portfolio on does, for
tests that call the service without an app; the media library's files have
addresses; and events said are kept for the test to read. The contract
suite, which runs the app, never has them."""

from __future__ import annotations

from typing import Any

import pytest

from kernel import audit, events, lifecycle, search, server_copy, storage, taxonomy
from kernel.settings import settings

FILES = "https://files.portfolio.test"


@pytest.fixture(autouse=True)
def said(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Every event portfolio says, by name and payload."""
    heard: list[tuple[str, Any]] = []

    async def emit(db: Any, name: str, payload: Any) -> int:
        heard.append((name, payload))
        return 1

    monkeypatch.setattr(events, "emit", emit)
    return heard


@pytest.fixture(autouse=True)
def portfolio_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit log takes portfolio's actions, and the lifecycle, search,
    taxonomy and settings know it, as an app with portfolio on does."""
    from portfolio.lifecycle import PUBLISHABLE
    from portfolio.schemas import Settings
    from portfolio.search import SEARCH

    monkeypatch.setattr(audit, "_owners", audit._owners | {"portfolio", "media"})
    monkeypatch.setattr(lifecycle, "_publishable", {"portfolio.piece": PUBLISHABLE[0]})
    monkeypatch.setattr(search, "_sources", {"portfolio.piece": SEARCH[0]})
    discipline = taxonomy.Vocabulary("portfolio_discipline", "Disciplines", False, ("portfolio",))
    monkeypatch.setattr(
        taxonomy,
        "_declared",
        taxonomy.Declared(
            {"portfolio_discipline": discipline},
            {"portfolio.piece": frozenset({"portfolio_discipline"})},
        ),
    )
    monkeypatch.setattr(storage, "public_url", lambda key: f"{FILES}/{key}")
    monkeypatch.setitem(settings.models, "portfolio", Settings)
    monkeypatch.setitem(settings.models, server_copy.SECTION, server_copy.SiteSettings)
