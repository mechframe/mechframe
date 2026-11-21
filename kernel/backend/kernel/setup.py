"""Dashboard cards (decision 0052, hook 8; contract `dev plans/contracts/hooks.md`):
the setup steps every module can list, and the attention items it can add to
the Dashboard's "Needs you" (`kernel.attention`).

A module's `dashboard.py` gives either or both:

    SETUP = (
        setup.Step(
            key="payments.connect",
            title="Connect Stripe",
            why="Until it's connected, nobody can pay for anything.",
            link="/admin/settings/payments",
            permission="kernel.settings.manage",
            done=stripe_connected,  # async (db) -> bool, checked each time it's read
        ),
    )

    async def ATTENTION(db, user) -> list[attention.Item]: ...

`GET /api/kernel/admin/setup` lists the steps of the modules on that the
person holds the permission for, each `done` checked live, and the
Dashboard shows a Set up card while any is open. A step whose check fails
counts as open, logged by its error's type. A module that lists nothing
declares nothing.
"""

from __future__ import annotations

import inspect
import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from kernel.auth.permissions import KERNEL_PERMISSIONS, can

if TYPE_CHECKING:
    from kernel.modules import InstalledModule

log = logging.getLogger(__name__)

_NAME = re.compile(r"[a-z][a-z0-9_]*")
MAX_TITLE = 80
MAX_WHY = 300


@dataclass(frozen=True)
class Step:
    """One thing to set up: what, why it matters, the page that does it, who
    may, and how to tell it's done."""

    key: str
    title: str
    why: str
    link: str
    permission: str
    done: Callable[[AsyncSession], Awaitable[bool]] = field(repr=False, compare=False)


def declared(installed: Iterable[InstalledModule]) -> set[str]:
    """The permissions the kernel and the modules declare."""
    found = set(KERNEL_PERMISSIONS)
    for module in installed:
        for permission in module.manifest.raw.get("permissions", []):
            if isinstance(permission, dict) and isinstance(permission.get("key"), str):
                found.add(permission["key"])
    return found


def _check(module: InstalledModule, step: object, known: set[str]) -> Step:
    if not isinstance(step, Step):
        raise ValueError(f"{module.id}'s SETUP holds {step!r}: each is a kernel.setup.Step.")
    owner, dot, name = step.key.partition(".")
    if owner != module.id or not dot or not _NAME.fullmatch(name):
        raise ValueError(f"{module.id}'s setup step {step.key!r} is named {module.id}.<name>.")
    if not 0 < len(step.title) <= MAX_TITLE or not 0 < len(step.why) <= MAX_WHY:
        raise ValueError(
            f"{step.key} has a title of 1 to {MAX_TITLE} characters and a why of 1 to {MAX_WHY}."
        )
    # A backslash reads as a slash in a URL (`/\\host` is another site), and
    # a control character as nothing (CodeRabbit on #110).
    if (
        not step.link.startswith("/")
        or step.link.startswith("//")
        or "\\" in step.link
        or any(ord(character) < 32 or ord(character) == 127 for character in step.link)
    ):
        raise ValueError(f"{step.key}'s link is a path on this site, such as /admin/settings.")
    if step.permission not in known:
        raise ValueError(f"{step.key} names {step.permission}, which nothing declares.")
    if not inspect.iscoroutinefunction(step.done):
        raise ValueError(f"{step.key}'s done is `async def done(db) -> bool`.")
    return step


def build(installed: Iterable[InstalledModule]) -> dict[str, tuple[Step, ...]]:
    """Each module's steps, by id. ValueError, naming the step, for one that
    isn't a `Step`, isn't named `<id>.<name>`, links off the site, names a
    permission nothing declares, or has a `done` that isn't `async`; or for
    a key given twice."""
    modules = list(installed)
    known = declared(modules)
    found: dict[str, tuple[Step, ...]] = {}
    for module in modules:
        steps = tuple(_check(module, step, known) for step in module.setup)
        keys = [step.key for step in steps]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{module.id}'s SETUP names a step twice.")
        if steps:
            found[module.id] = steps
    return found


_steps: dict[str, tuple[Step, ...]] = {}


def install(steps: Mapping[str, tuple[Step, ...]]) -> None:
    """Called by `kernel.app.assemble` with `build`'s answer."""
    global _steps
    _steps = dict(steps)


async def _done(db: AsyncSession, step: Step) -> bool:
    """The step's check, in a savepoint of its own: a database error in it
    rolls back only the check, and the rest of the page reads on (Codex on
    #110)."""
    try:
        async with db.begin_nested():
            return bool(await step.done(db))
    except Exception as error:  # a broken check shows the step open, never the page broken
        log.warning("Setup step %s couldn't be checked (%s).", step.key, type(error).__name__)
        return False


async def for_person(
    db: AsyncSession, user_id: uuid.UUID, on: Iterable[str]
) -> list[dict[str, Any]]:
    """The steps of the modules `on` that the person may take, in module id
    order and each module's own, each checked now."""
    found: list[dict[str, Any]] = []
    allowed: dict[str, bool] = {}
    for module in sorted(set(on) & set(_steps)):
        for step in _steps[module]:
            if step.permission not in allowed:
                allowed[step.permission] = await can(db, user_id, step.permission)
            if not allowed[step.permission]:
                continue
            found.append(
                {
                    "key": step.key,
                    "title": step.title,
                    "why": step.why,
                    "link": step.link,
                    "done": await _done(db, step),
                }
            )
    return found
