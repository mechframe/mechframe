"""The backend tests' own fixture: what an app with campaigns on gives the
service, for tests that call it without one. The kernel's audit log takes
campaigns' actions; the settings are the defaults with a postal address (a
test changes `campaigns_settings` before the service reads them); the footer
names a test site; and mail goes to a capturing mailer, installed for the test
and put back after. The contract suite, which runs the app, never has it."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from kernel import audit, email


@pytest.fixture
def campaigns_settings() -> dict[str, Any]:
    return {"postal_address": "P.O. Box 12\nBoston, MA 02101"}


@pytest.fixture(autouse=True)
def mailbox(
    monkeypatch: pytest.MonkeyPatch, campaigns_settings: dict[str, Any]
) -> Iterator[email.CapturingMailer]:
    from campaigns import render, service
    from campaigns.emails import EMAILS
    from campaigns.schemas import Settings

    async def chosen(db: object) -> Settings:
        return Settings(**campaigns_settings)

    async def footer(db: object, cfg: Settings | None = None) -> render.Footer:
        cfg = cfg or Settings(**campaigns_settings)
        return render.Footer(
            render.footer_note(cfg.footer_note, "Test Site"), "Test Site", cfg.postal_address
        )

    monkeypatch.setattr(audit, "_owners", audit._owners | {"campaigns"})
    monkeypatch.setattr(service, "current", chosen)
    monkeypatch.setattr(service, "footer", footer)
    before = email._postbox
    captured = email.CapturingMailer()
    email.install(
        captured,
        email.build_templates([("campaigns", EMAILS)], {}),
        site_name="Test Site",
        site_url="https://site.test",
    )
    yield captured
    email._postbox = before
