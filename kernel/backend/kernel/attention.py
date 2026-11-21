"""The dashboard's "Needs you" list (K4 contract §2, addition 9; SPEC 8, the
owner's lens): what's wrong, why it matters and what fixes it, each item only
for the people who can act on it.

The kernel's own items are the site's missing description and card image,
for those who can change the site's settings, and failed background jobs, for
those who can also open System and retry them. The worst come first: a
danger, then a warning, then what's only worth knowing.

**Modules add theirs** (hook 8, decision 0052): a module's `dashboard.py`
gives `ATTENTION`, `async def ATTENTION(db, user) -> list[attention.Item]`,
each item keyed `<id>.<name>` and naming the `permission` a person needs to
see it. The kernel asks the modules that are on, keeps each item only for
those who hold its permission, and drops a module's items, logged by its
error's type, when its `ATTENTION` fails, so one module can't break the
Dashboard.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import server_copy
from kernel.auth.permissions import can
from kernel.models import Job

if TYPE_CHECKING:
    from kernel.auth.models import User
    from kernel.modules import InstalledModule

log = logging.getLogger(__name__)

Tone = Literal["info", "warning", "danger"]

#: The order a tone sorts in: the worst first.
_RANK: dict[Tone, int] = {"danger": 0, "warning": 1, "info": 2}

SETTINGS = "kernel.settings.manage"
JOBS = "kernel.jobs.manage"
SITE_PAGE = "/admin/settings"
SYSTEM_PAGE = "/admin/settings/system"


@dataclass(frozen=True)
class Item:
    key: str
    tone: Tone
    what: str
    why: str
    label: str
    to: str
    #: Who sees it: those who hold this permission. A module's item MUST name
    #: one; the kernel's own are checked in code.
    permission: str | None = None

    def as_answer(self) -> dict[str, object]:
        return {
            "key": self.key,
            "tone": self.tone,
            "what": self.what,
            "why": self.why,
            "action": {"label": self.label, "to": self.to},
        }


def _failed(count: int) -> Item:
    jobs = "1 background job" if count == 1 else f"{count} background jobs"
    return Item(
        key="kernel.jobs.dead",
        tone="danger",
        what=f"{jobs} failed",
        why=(
            "They ran out of tries, so what they were doing, such as sending an email, "
            "didn't happen. Retry them once the cause is fixed, or discard them."
        ),
        label="See failed jobs",
        to=SYSTEM_PAGE,
    )


DESCRIPTION_MISSING = Item(
    key="kernel.site.description_missing",
    tone="warning",
    what="The site has no description",
    why=(
        "Search engines and AI answers describe the site with whatever words they "
        "find on the home page instead."
    ),
    label="Add a description",
    to=SITE_PAGE,
)

CARD_MISSING = Item(
    key="kernel.site.card_missing",
    tone="info",
    what="Shared links show no picture",
    why="A link to the site posted anywhere has no image beside it until you choose one.",
    label="Choose a picture",
    to=SITE_PAGE,
)


async def _dead_jobs(db: AsyncSession) -> int:
    count = await db.scalar(select(func.count()).select_from(Job).where(Job.state == "dead"))
    return int(count or 0)


Provider = Callable[[AsyncSession, "User"], Awaitable[list[Item]]]

_providers: dict[str, Provider] = {}
_declared: frozenset[str] = frozenset()


def build(installed: Iterable[InstalledModule]) -> dict[str, Provider]:
    """Each module's `ATTENTION`, by id. ValueError for one that isn't
    `async def ATTENTION(db, user)`. Also notes the permissions the kernel and
    the modules declare, the only ones an item may name."""
    from kernel import setup  # its declared permissions, the same for steps and items

    modules = list(installed)
    global _declared
    _declared = frozenset(setup.declared(modules))
    found: dict[str, Provider] = {}
    for module in modules:
        if module.attention is None:
            continue
        if not inspect.iscoroutinefunction(module.attention):
            raise ValueError(f"{module.id}'s ATTENTION is `async def ATTENTION(db, user)`.")
        found[module.id] = module.attention
    return found


def install(providers: Mapping[str, Provider]) -> None:
    """Called by `kernel.app.assemble` with `build`'s answer."""
    global _providers
    _providers = dict(providers)


async def _modules_items(db: AsyncSession, user: User, on: Iterable[str]) -> list[Item]:
    found: list[Item] = []
    allowed: dict[str, bool] = {}
    for module in sorted(set(on) & set(_providers)):
        try:
            # A savepoint of its own: a database error rolls back only this
            # module's reads, and the next module's still run (Codex on #110).
            async with db.begin_nested():
                items = await _providers[module](db, user)
            if not isinstance(items, list):  # checked here, so it costs only this module
                raise TypeError(f"answered {type(items).__name__}, not a list of Items")
        except Exception as error:  # one module's failure never breaks the Dashboard
            log.warning("%s's attention items failed (%s).", module, type(error).__name__)
            continue
        for item in items:
            if (
                not isinstance(item, Item)
                or not item.key.startswith(f"{module}.")
                or item.permission not in _declared
            ):
                log.warning(
                    "%s gave an attention item that isn't its own Item naming a declared "
                    "permission.",
                    module,
                )
                continue
            if item.permission not in allowed:
                allowed[item.permission] = await can(db, user.id, item.permission)
            if allowed[item.permission]:
                found.append(item)
    return found


async def for_person(db: AsyncSession, user: User, on: Iterable[str] = ()) -> list[Item]:
    """What needs this person, the worst first: the kernel's items, then
    those of the modules `on` that they hold the permission for."""
    user_id = user.id
    found: list[Item] = []
    site_settings = await can(db, user_id, SETTINGS)
    if site_settings:
        identity = await server_copy.identity(db)
        if not identity.description.strip():
            found.append(DESCRIPTION_MISSING)
        if not identity.card_image.strip():
            found.append(CARD_MISSING)
    # System is read with the settings permission; a job is retried with the jobs one.
    if site_settings and await can(db, user_id, JOBS):
        dead = await _dead_jobs(db)
        if dead:
            found.append(_failed(dead))
    found.extend(await _modules_items(db, user, on))
    return sorted(found, key=lambda item: _RANK[item.tone])
