"""The bot check for public forms (SPEC.md sections 6, 7 and 8; hook 5,
decision 0052; contract `dev plans/contracts/hooks.md`).

A public form's body carries `bot: BotProof | None` (`{website, elapsed_ms,
token}`, each optional), which the kit's `<BotFields />` and `useBotProof()`
fill in. Its service asks, before it stores anything:

    found = await bot.verify(request, body.bot, form="contact.inquiry", db=db)

and gets `Pass()` or `Held(reason)`. A held submission is still stored, marked
with its reason and set apart for a person to release; it never reaches
anyone's inbox, and it is never dropped without a trace: a real message lost
to a false positive costs far more than a bot's message kept. The visitor gets
the same answer either way, so a bot learns nothing from it.

**The provider** is the settings section `kernel.bot`'s `provider`: `form`,
the kernel's own check, by default, or the id of a module whose
`__init__.py` gives `BOT_PROVIDER`, an object with `async def verify(request,
proof, form) -> Pass | Held` (bot-shield's Turnstile, later). A provider no
module on gives falls back to the form check. A provider that raises, or
answers something else, holds the submission as `provider_error`.

**The form check** (`verdict`), lifted from VybeSite's contact filter
(`backend/app/services/contact_filter.py`), reads two signals nobody using
the form sees:

- **A trap field**, `website`: hidden from sight, the keyboard and screen
  readers, but an ordinary input to a bot, which fills in every field it finds.
  Text in it is `honeypot`; whitespace alone isn't typing, since autofill can
  leave it.
- **How long the form was open**, `elapsed_ms`: a person needs more than
  three seconds (`MIN_FILL_MS`), even with autofill; a script needs none. Less
  is `too_fast`.

A proof missing either signal, or no proof at all, is `not_from_form`: posted
straight to the API, or from a page opened before the form had the fields.
"""

from __future__ import annotations

import inspect
import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from kernel.settings import settings

if TYPE_CHECKING:
    from kernel.modules import InstalledModule, ModuleRegistry

#: The settings section that names the provider.
SECTION = "kernel.bot"
#: The kernel's own provider.
FORM = "form"
#: Faster than this, the form was not filled in by a person.
MIN_FILL_MS = 3_000
#: A form's name: `<module>.<form>`, as `contact.inquiry`.
_FORM_NAME = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.[a-z][a-z0-9_]*")

log = logging.getLogger(__name__)


class BotProof(BaseModel):
    """What a public form sends for the bot check; every field optional."""

    model_config = ConfigDict(strict=True, extra="forbid")

    #: The trap field: empty from a person.
    website: str | None = Field(default=None, max_length=500)
    #: How long the form was open, in milliseconds.
    elapsed_ms: int | None = Field(default=None, ge=0, le=10**10)
    #: A provider's token, such as Turnstile's (bot-shield); the form check ignores it.
    token: str | None = Field(default=None, max_length=4096)


@dataclass(frozen=True)
class Pass:
    """It looks like a person's."""


@dataclass(frozen=True)
class Held:
    """Set it apart, stored, with this reason: `honeypot`, `too_fast`,
    `not_from_form`, `provider_error` or a provider's own."""

    reason: str


class Provider(Protocol):
    """A module's bot check, its `__init__.py`'s `BOT_PROVIDER`."""

    async def verify(self, request: Request, proof: BotProof | None, form: str) -> Pass | Held: ...


class Choice(BaseModel):
    """The settings section `kernel.bot`: which provider judges public forms."""

    model_config = ConfigDict(extra="forbid")

    #: `form`, or the id of a module that gives `BOT_PROVIDER`.
    provider: str = Field(default=FORM, pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", max_length=64)


def verdict(proof: BotProof | None, *, min_fill_ms: int = MIN_FILL_MS) -> Pass | Held:
    """The form check: `Pass()` for what looks like a person's, else why not.
    The trap outranks the rest: text in a field nobody can see is the surest
    sign there is."""
    website = proof.website if proof is not None else None
    elapsed_ms = proof.elapsed_ms if proof is not None else None
    if website is not None and website.strip():
        return Held("honeypot")
    if website is None or elapsed_ms is None:
        return Held("not_from_form")
    if elapsed_ms < min_fill_ms:
        return Held("too_fast")
    return Pass()


class FormCheck:
    """The kernel's provider, `form`: `verdict` on the proof."""

    async def verify(self, request: Request, proof: BotProof | None, form: str) -> Pass | Held:
        return verdict(proof)


_FORM_CHECK = FormCheck()
_providers: dict[str, Provider] = {}


def build(installed: Iterable[InstalledModule]) -> dict[str, Provider]:
    """The providers the modules add, by module id. ValueError for one named
    like the kernel's or without an async `verify`."""
    found: dict[str, Provider] = {}
    for module in installed:
        provider = module.bot_provider
        if provider is None:
            continue
        if module.id == FORM:
            raise ValueError(
                f"A module named {FORM} can't add a bot provider: that's the kernel's."
            )
        if not inspect.iscoroutinefunction(getattr(provider, "verify", None)):
            raise ValueError(
                f"{module.id}'s BOT_PROVIDER has `async def verify(request, proof, form)`."
            )
        found[module.id] = provider
    return found


def install(providers: Mapping[str, Provider]) -> None:
    """The providers `kernel.app.assemble` built, for `verify`."""
    global _providers
    _providers = dict(providers)


async def _chosen(request: Request, db: AsyncSession) -> tuple[str, Provider]:
    """The provider the setting names, while its module is on; else the form
    check. Read through the route's own session: a second connection could
    wait for the one `require_module` already holds (Codex on #103)."""
    registry: ModuleRegistry = request.app.state.modules
    choice: Any = await settings.for_module(db, SECTION)
    named: str = choice.provider
    if named == FORM:
        return FORM, _FORM_CHECK
    provider = _providers.get(named)
    if provider is not None and named in await registry.on(db):
        return named, provider
    log.warning(
        "The bot check's provider isn't on; the form check judges instead.",
        extra={"provider": named},
    )
    return FORM, _FORM_CHECK


async def verify(
    request: Request, proof: BotProof | None, *, form: str, db: AsyncSession
) -> Pass | Held:
    """Whether a public form's submission looks like a person's, by the
    provider `kernel.bot` names, read through the route's own session `db`.
    A submission held is still stored, set apart."""
    if not (isinstance(form, str) and len(form) <= 130 and _FORM_NAME.fullmatch(form)):
        raise ValueError(f"{form!r} isn't a form's name: <module>.<form>, lowercase.")
    named, provider = await _chosen(request, db)
    try:
        found = await provider.verify(request, proof, form)
    except Exception as error:
        # Its type alone: a provider's message can carry the token it was given.
        log.warning(
            "The bot check's provider failed: the submission is held.",
            extra={"provider": named, "form": form, "error": type(error).__name__},
        )
        return Held("provider_error")
    if not isinstance(found, Pass | Held):
        log.warning(
            "The bot check's provider answered neither Pass nor Held: the submission is held.",
            extra={"provider": named, "form": form},
        )
        return Held("provider_error")
    if isinstance(found, Held):
        log.info(
            "A public form's submission is held.",
            extra={"provider": named, "form": form, "reason": found.reason},
        )
    return found
