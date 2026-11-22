"""The backend tests' own fixture: the kernel's audit log takes contact's
actions and the module reads its settings' defaults, as an app with contact
on does, for tests that call the service without an app. The contract suite,
which runs the app, never has it."""

from __future__ import annotations

import pytest

from kernel import audit


@pytest.fixture(autouse=True)
def contact_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    from contact import service
    from contact.schemas import Settings

    async def defaults(db: object) -> Settings:
        return Settings()

    monkeypatch.setattr(audit, "_owners", audit._owners | {"contact"})
    monkeypatch.setattr(service, "current", defaults)
