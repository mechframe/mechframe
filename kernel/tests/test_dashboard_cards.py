"""Dashboard cards (decision 0052, hook 8; contract `dev plans/contracts/hooks.md`):
the start's checks on a module's `SETUP` and `ATTENTION`, the steps and
items each person sees by permission and by the modules on, and a module
whose part fails costing the Dashboard nothing. The HTTP half is
`kernel/tests/contract/test_hook_dashboard.py`."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from harness.probe import MODULES as PROBES
from kernel import attention, setup
from kernel.auth.models import User, UserRole
from kernel.modules import InstalledModule, Manifest

from .conftest import AppFactory


async def _done(db: Any) -> bool:
    return True


async def _open(db: Any) -> bool:
    return False


async def _broken(db: Any) -> bool:
    raise RuntimeError("the check fell over")


def _step(key: str = "shop.connect", **fields: Any) -> setup.Step:
    made: dict[str, Any] = {
        "key": key,
        "title": "Connect payments",
        "why": "Nobody can pay until it's connected.",
        "link": "/admin/settings/shop",
        "permission": "kernel.settings.manage",
        "done": _open,
        **fields,
    }
    return setup.Step(**made)


def _module(
    module_id: str = "shop", *, steps: tuple[Any, ...] = (), needs: Any = None
) -> InstalledModule:
    manifest = Manifest.from_dict(
        {
            "id": module_id,
            "name": module_id.title(),
            "version": "0.1.0",
            "summary": "A module for the dashboard tests",
            "category": "admin",
            "permissions": [{"key": f"{module_id}.manage", "description": "Run it"}],
        }
    )
    return InstalledModule(manifest, setup=steps, attention=needs)


def _item(
    key: str, permission: str | None = "kernel.settings.manage", tone: Any = "info"
) -> attention.Item:
    return attention.Item(key, tone, "What", "Why", "Fix it", "/admin", permission=permission)


@pytest.fixture(autouse=True)
def _restore(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test's installs are undone after it: a server built later keeps its own."""
    monkeypatch.setattr(setup, "_steps", setup._steps)
    monkeypatch.setattr(attention, "_providers", attention._providers)


# --- the start's checks ----------------------------------------------------------------------


def test_only_the_probe_takes_part() -> None:
    assert list(setup.build(PROBES)) == ["probe"]
    assert [step.key for step in setup.build(PROBES)["probe"]] == ["probe.count"]
    assert list(attention.build(PROBES)) == ["probe"]


@pytest.mark.parametrize(
    ("step", "words"),
    [
        ("not a step", "each is a kernel.setup.Step"),
        (_step(key="blog.connect"), "is named shop.<name>"),
        (_step(key="shop"), "is named shop.<name>"),
        (_step(key="shop.Connect"), "is named shop.<name>"),
        (_step(title=""), "a title of 1 to 80"),
        (_step(why="x" * 301), "a why of 1 to 300"),
        (_step(link="https://elsewhere.test/admin"), "a path on this site"),
        (_step(link="//elsewhere.test"), "a path on this site"),
        (_step(permission="shop.nothing"), "names shop.nothing, which nothing declares"),
        (_step(done=lambda db: True), "is `async def done(db) -> bool`"),
    ],
)
def test_a_step_the_kernel_cant_show_is_refused(step: Any, words: str) -> None:
    with pytest.raises(
        ValueError, match=words.replace("(", r"\(").replace(")", r"\)").replace(".", r"\.")
    ):
        setup.build([_module(steps=(step,))])


def test_a_step_given_twice_is_refused() -> None:
    with pytest.raises(ValueError, match="names a step twice"):
        setup.build([_module(steps=(_step(), _step()))])


def test_a_step_may_name_its_own_modules_permission() -> None:
    assert (
        setup.build([_module(steps=(_step(permission="shop.manage"),))])["shop"][0].key
        == "shop.connect"
    )


def test_attention_that_isnt_async_is_refused() -> None:
    with pytest.raises(ValueError, match="async def ATTENTION"):
        attention.build([_module(needs=lambda db, user: [])])


# --- who sees what --------------------------------------------------------------------------------


async def _person(db: AsyncSession, *roles: str) -> User:
    user_id = uuid.uuid4()
    address = f"{user_id.hex[:12]}@site.test"
    user = User(id=user_id, email=address, email_normal=address, session_epoch=0, role_version=0)
    db.add(user)
    await db.flush()
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role))
    await db.commit()
    return user


@pytest.mark.db
async def test_steps_show_by_permission_and_module_each_checked_now(db: AsyncSession) -> None:
    setup.install(
        setup.build(
            [
                _module("shop", steps=(_step(done=_done), _step(key="shop.ship", done=_broken))),
                _module("blog", steps=(_step(key="blog.write", permission="auth.audit.read"),)),
            ]
        )
    )
    admin, editor = await _person(db, "admin"), await _person(db, "editor")
    admin_id, editor_id = admin.id, editor.id
    found = await setup.for_person(db, admin_id, {"shop", "blog"})
    assert [(step["key"], step["done"]) for step in found] == [
        ("blog.write", False),
        ("shop.connect", True),
        ("shop.ship", False),  # a check that fails shows the step open
    ]
    assert [step["key"] for step in await setup.for_person(db, admin_id, {"blog"})] == [
        "blog.write"
    ]
    assert await setup.for_person(db, editor_id, {"shop", "blog"}) == []


@pytest.mark.db
async def test_items_show_by_permission_and_module_and_a_failure_costs_nothing(
    app_factory: AppFactory, db: AsyncSession
) -> None:
    app_factory([])  # the kernel's own items read the site's settings section

    async def shop(db: Any, user: Any) -> list[attention.Item]:
        return [
            _item("shop.low_stock", tone="warning"),
            _item("shop.unnamed", permission=None),  # dropped: an item names who sees it
            _item("blog.not_mine"),  # dropped: a module adds only its own
            _item("shop.audit", permission="auth.audit.read", tone="danger"),
        ]

    async def broken(db: Any, user: Any) -> list[attention.Item]:
        raise RuntimeError("its query fell over")

    attention.install(attention.build([_module("shop", needs=shop), _module("blog", needs=broken)]))
    admin = await _person(db, "admin")
    editor = await _person(db, "editor")
    found = await attention.for_person(db, admin, {"shop", "blog"})
    module_items = [item.key for item in found if not item.key.startswith("kernel.")]
    assert module_items == ["shop.audit", "shop.low_stock"]  # the worst first
    assert [item.key for item in await attention.for_person(db, admin, {"blog"})] == [
        item.key for item in found if item.key.startswith("kernel.")
    ]
    assert [
        item.key
        for item in await attention.for_person(db, editor, {"shop"})
        if item.key.startswith("shop.")
    ] == []
