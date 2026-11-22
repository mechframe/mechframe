"""The backend tests' own fixture: the kernel's registries hold pages' type, as
an app with pages on does, for tests that call the service without an app.
The contract suite, which runs the app, never has it (CodeRabbit on #121)."""

from __future__ import annotations

import pytest

from kernel import audit, lifecycle, search


@pytest.fixture(autouse=True)
def pages_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit log takes pages' actions, and the lifecycle and search know
    its type, as an app with pages on does (`audit.install`, `lifecycle.install`,
    `search.install`)."""
    from pages.lifecycle import PUBLISHABLE
    from pages.search import SEARCH

    monkeypatch.setattr(audit, "_owners", audit._owners | {"pages"})
    monkeypatch.setattr(lifecycle, "_publishable", {"pages.page": PUBLISHABLE[0]})
    monkeypatch.setattr(search, "_sources", {"pages.page": SEARCH[0]})
