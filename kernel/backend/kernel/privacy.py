"""Export and erase (decision 0052, hook 7; contract `dev plans/contracts/hooks.md`;
SPEC.md 5, 10 and 14.7).

A module that holds a person's data gives two functions in its `privacy.py`
and says so in its manifest's `data_hooks`:

    async def export_user_data(db, subject: privacy.Subject) -> dict[str, list[dict]]: ...
    async def delete_user_data(db, subject: privacy.Subject) -> None: ...

`Subject` is `{user_id, email}`, so data held by address (a contact
inquiry, a campaign's contact) is found as well as data held by account. An
export answers lists of JSON objects by name (`{"notes": [{...}]}`); a
deletion removes or anonymises what the module holds, in the caller's
transaction, and never commits. The start refuses a module whose
`data_hooks` say one thing and whose `privacy.py` another.

**The export** (14.7) is the kernel's: `export(db, subject)` asks every
installed module that gives `export_user_data`, on or off, since what a
switched-off module holds is still the person's. The job
`kernel.privacy_export` (`kernel.auth.exports`) writes the answers as a ZIP
of JSON, one file per module and the kernel's own `kernel.json` first, to
private storage, and mails a link. **The deletion** is `erase(db,
subject)`, which K2's step 11 calls once an account's grace period is over
(decision 0029): nothing calls it before.
"""

from __future__ import annotations

import inspect
import io
import json
import uuid
import zipfile
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from kernel.modules import InstalledModule


@dataclass(frozen=True)
class Subject:
    """Whose data: the account's id and its address, as the account holds it.
    A module that keeps addresses compares them case-insensitively."""

    user_id: uuid.UUID
    email: str


Exported = dict[str, list[dict[str, Any]]]
Export = Callable[[AsyncSession, Subject], Awaitable[Exported]]
Delete = Callable[[AsyncSession, Subject], Awaitable[None]]


@dataclass(frozen=True)
class Hooks:
    """A module's two functions, either of which may be absent."""

    export: Export | None = None
    delete: Delete | None = None


_hooks: dict[str, Hooks] = {}


def _declared(module: InstalledModule, part: str) -> bool:
    hooks = module.manifest.raw.get("data_hooks") or {}
    return isinstance(hooks, dict) and hooks.get(part) is True


def build(installed: Iterable[InstalledModule]) -> dict[str, Hooks]:
    """Each module's functions, by id, for the modules that give either.
    ValueError, naming the module, when its manifest's `data_hooks` and its
    `privacy.py` disagree, or when a function isn't `async def`."""
    found: dict[str, Hooks] = {}
    for module in installed:
        hooks = Hooks(module.export_user_data, module.delete_user_data)
        for part, function in (("export", hooks.export), ("delete", hooks.delete)):
            name = f"{part}_user_data"
            if _declared(module, part) and function is None:
                raise ValueError(
                    f"{module.id}'s module.json says data_hooks.{part}, but its privacy.py "
                    f"has no {name}."
                )
            if function is not None and not _declared(module, part):
                raise ValueError(
                    f"{module.id}'s privacy.py has {name}, but its module.json doesn't say "
                    f'"data_hooks": {{"{part}": true}}.'
                )
            if function is not None and not inspect.iscoroutinefunction(function):
                raise ValueError(f"{module.id}'s {name} is `async def {name}(db, subject)`.")
        if hooks.export is not None or hooks.delete is not None:
            found[module.id] = hooks
    return found


def install(hooks: Mapping[str, Hooks]) -> None:
    """Called by `kernel.app.assemble` with `build`'s answer."""
    global _hooks
    _hooks = dict(hooks)


def exporting() -> list[str]:
    """The modules that export, in id order."""
    return sorted(module for module, hooks in _hooks.items() if hooks.export is not None)


def _checked(module: str, answer: object) -> Exported:
    if not isinstance(answer, dict) or not all(
        isinstance(name, str)
        and isinstance(rows, list)
        and all(isinstance(row, dict) for row in rows)
        for name, rows in answer.items()
    ):
        raise ValueError(
            f"{module}'s export_user_data answers lists of objects by name, " '{"notes": [{...}]}.'
        )
    return answer


async def export(db: AsyncSession, subject: Subject) -> dict[str, Exported]:
    """What every module that exports holds about `subject`, by module id.
    ValueError for an answer that isn't lists of objects by name."""
    found: dict[str, Exported] = {}
    for module in exporting():
        function = _hooks[module].export
        if function is not None:
            found[module] = _checked(module, await function(db, subject))
    return found


async def erase(db: AsyncSession, subject: Subject) -> list[str]:
    """Runs every module's `delete_user_data` for `subject` in the caller's
    transaction, in id order; answers the modules that deleted. For K2's
    step 11, once an account's grace period is over."""
    done = []
    for module in sorted(_hooks):
        function = _hooks[module].delete
        if function is not None:
            await function(db, subject)
            done.append(module)
    return done


def _json(value: object) -> str:
    def plain(item: object) -> object:
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, uuid.UUID):
            return str(item)
        raise TypeError(f"{type(item).__name__} isn't JSON.")

    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=plain) + "\n"


def archive(files: Mapping[str, object], *, at: datetime) -> bytes:
    """A ZIP holding each `<name>.json`, in the order given, every entry
    dated `at`. A value JSON can't hold raises TypeError."""
    stamp = (at.year, at.month, at.day, at.hour, at.minute, at.second)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as made:
        for name, value in files.items():
            entry = zipfile.ZipInfo(f"{name}.json", date_time=stamp)
            entry.compress_type = zipfile.ZIP_DEFLATED
            made.writestr(entry, _json(value))
    return buffer.getvalue()
