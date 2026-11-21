"""Consent categories (decision 0052, hook 6; contract `dev plans/contracts/hooks.md`):
each `CSP` entry's category, `necessary` when it names none; the start
refusing one the kernel doesn't know; the categories of the modules on and
CONSENT_MODE in `GET /api/kernel/site`; and the policy itself unchanged."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from harness.probe import MODULES as PROBES
from kernel import consent
from kernel.config import KernelConfig
from kernel.db import Database
from kernel.models import ModuleState
from kernel.modules import InstalledModule, Manifest

from .conftest import AppFactory, Client, make_config


@pytest.fixture(autouse=True)
def _restore(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test's installs are undone after it: a server built later keeps its own."""
    monkeypatch.setattr(consent, "_categories", consent._categories)


def _module(module_id: str, *csp: tuple[str, ...]) -> InstalledModule:
    manifest = Manifest.from_dict(
        {
            "id": module_id,
            "name": module_id.title(),
            "version": "0.1.0",
            "summary": "A module for the consent tests",
            "category": "admin",
        }
    )
    return InstalledModule(manifest, csp=csp)  # type: ignore[arg-type]


def _id() -> str:
    return f"c{uuid.uuid4().hex[:10]}"


# --- each entry's category -----------------------------------------------------------------


def test_an_entry_naming_no_category_is_necessary() -> None:
    module = _module("payments", ("script-src", "https://js.stripe.com"))
    assert consent.entries(module) == (("script-src", "https://js.stripe.com", "necessary"),)


@pytest.mark.parametrize("category", consent.CATEGORIES)
def test_an_entry_keeps_the_category_it_names(category: str) -> None:
    module = _module("embeds", ("frame-src", "https://www.youtube-nocookie.com", category))
    assert consent.entries(module) == (("frame-src", "https://www.youtube-nocookie.com", category),)


def test_the_categories_are_the_four_the_contract_names() -> None:
    assert consent.CATEGORIES == ("necessary", "analytics", "marketing", "media")


@pytest.mark.parametrize("category", ["Media", "ads", "", "statistics"])
def test_a_category_the_kernel_doesnt_know_is_refused(category: str) -> None:
    module = _module("embeds", ("frame-src", "https://www.youtube-nocookie.com", category))
    with pytest.raises(ValueError, match="embeds") as refused:
        consent.entries(module)
    assert "necessary, analytics, marketing or media" in str(refused.value)


@pytest.mark.parametrize(
    "entry",
    [
        ("frame-src",),
        ("frame-src", "https://a.test", "media", "extra"),
        ("frame-src", 3),
        ("frame-src", "https://a.test", None),
        "frame-src https://a.test",
    ],
)
def test_an_entry_of_the_wrong_shape_is_refused(entry: Any) -> None:
    with pytest.raises(ValueError, match="embeds's CSP entry"):
        consent.entries(_module("embeds", entry))


def test_the_start_refuses_a_category_it_doesnt_know(app_factory: AppFactory) -> None:
    module = _module(_id(), ("frame-src", "https://player.test", "videos"))
    with pytest.raises(RuntimeError, match=r"Refusing to start: .*videos"):
        app_factory([module])


# --- the categories of the modules on -------------------------------------------------------


def test_only_the_probe_takes_part() -> None:
    """Both probes load; only `probe` names a category (`probe-addon` names none)."""
    found = consent.build(PROBES)
    assert found == {"probe": frozenset({"media"})}
    consent.install(found)
    assert consent.categories({"probe", "probe-addon"}) == ["media"]
    assert consent.categories({"probe-addon"}) == []


def test_necessary_is_never_listed_and_the_order_is_fixed() -> None:
    found = consent.build(
        [
            _module("a", ("script-src", "https://a.test", "marketing")),
            _module("b", ("img-src", "https://b.test"), ("frame-src", "https://b.test", "media")),
            _module("c", ("connect-src", "https://c.test", "analytics")),
            _module("d", ("script-src", "https://d.test", "necessary")),
        ]
    )
    assert found == {
        "a": frozenset({"marketing"}),
        "b": frozenset({"media"}),
        "c": frozenset({"analytics"}),
    }
    consent.install(found)
    assert consent.categories({"a", "b", "c", "d"}) == ["analytics", "marketing", "media"]
    assert consent.categories({"b", "d"}) == ["media"]
    assert consent.categories(set()) == []


# --- CONSENT_MODE ----------------------------------------------------------------------------


def test_the_mode_is_ask_by_default() -> None:
    assert KernelConfig().consent_mode == "ask"


def test_the_mode_can_be_off() -> None:
    assert make_config(consent_mode="off").consent_mode == "off"


@pytest.mark.parametrize("mode", ["on", "OFF", "", "granted"])
def test_another_mode_is_refused(mode: str) -> None:
    with pytest.raises(ValidationError, match="consent_mode"):
        KernelConfig(consent_mode=mode)


# --- GET /api/kernel/site and the policy -------------------------------------------------


@pytest.mark.db
async def test_the_site_lists_the_categories_of_the_modules_on(
    app_factory: AppFactory,
) -> None:
    embeds, analytics = _id(), _id()
    app = app_factory(
        [
            _module(embeds, ("frame-src", "https://www.youtube-nocookie.com", "media")),
            _module(analytics, ("script-src", "https://stats.test", "analytics")),
        ],
        modules_cache_seconds=0,
    )
    async with Client(app) as client:
        site = (await client.get("/api/kernel/site")).json()
        assert site["consent"] == {"mode": "ask", "categories": ["analytics", "media"]}

        database: Database = app.state.database
        async with database.sessions() as db:
            db.add(ModuleState(module_id=analytics, enabled=False))
            await db.commit()
        site = (await client.get("/api/kernel/site")).json()
        assert site["consent"] == {"mode": "ask", "categories": ["media"]}


@pytest.mark.db
async def test_the_site_says_when_consent_is_off(app_factory: AppFactory) -> None:
    app = app_factory(
        [_module(_id(), ("frame-src", "https://a.test", "media"))], consent_mode="off"
    )
    async with Client(app) as client:
        site = (await client.get("/api/kernel/site")).json()
    assert site["consent"] == {"mode": "off", "categories": ["media"]}


@pytest.mark.db
async def test_the_policy_takes_a_categorised_host_as_before(app_factory: AppFactory) -> None:
    """The CSP doesn't change with consent: the host is in the policy while
    its module is on, whatever its category and whatever was chosen."""
    module = _id()
    app = app_factory([_module(module, ("frame-src", "https://www.youtube-nocookie.com", "media"))])
    async with Client(app) as client:
        policy = (await client.get("/api/kernel/site")).headers["content-security-policy"]
    assert "frame-src 'self' https://www.youtube-nocookie.com;" in policy
