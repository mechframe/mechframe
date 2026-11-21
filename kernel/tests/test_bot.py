"""The bot check (decision 0052, hook 5; contract `dev plans/contracts/hooks.md`):
the kernel's `form` check (lifted from VybeSite's contact filter, with its
tests), the providers modules add and the start's checks, and `bot.verify`
choosing the provider the setting `kernel.bot` names, falling back to the
form check, and holding a submission it can't judge."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from harness.probe import MODULES as PROBES
from kernel import BotProof, bot
from kernel.access import public
from kernel.db import Database, get_db
from kernel.models import ModuleState
from kernel.modules import InstalledModule, Manifest
from kernel.settings import settings

from .conftest import AppFactory, Client

# --- the form check, called directly (VybeSite's contact filter) -------------------------


def _proof(website: str | None = "", elapsed_ms: int | None = 45_000) -> bot.BotProof:
    return bot.BotProof(website=website, elapsed_ms=elapsed_ms)


def test_a_person_using_the_form_passes() -> None:
    assert bot.verdict(_proof()) == bot.Pass()


@pytest.mark.parametrize("website", ["http://spam.example", "x", "  y  "])
def test_anything_typed_in_the_hidden_field_is_a_bot(website: str) -> None:
    assert bot.verdict(_proof(website)) == bot.Held("honeypot")


def test_a_stray_space_in_the_hidden_field_is_not_typing() -> None:
    # Autofill can leave whitespace in a field nobody sees; a bot fills it with text.
    assert bot.verdict(_proof("   ")) == bot.Pass()


@pytest.mark.parametrize("elapsed_ms", [0, 1, bot.MIN_FILL_MS - 1])
def test_a_form_sent_faster_than_a_person_can_fill_it_is_held(elapsed_ms: int) -> None:
    assert bot.verdict(_proof(elapsed_ms=elapsed_ms)) == bot.Held("too_fast")


def test_the_threshold_itself_passes_and_is_three_seconds() -> None:
    assert bot.verdict(_proof(elapsed_ms=bot.MIN_FILL_MS)) == bot.Pass()
    assert bot.MIN_FILL_MS == 3_000


def test_the_hidden_field_outranks_the_timing_and_the_missing_signals() -> None:
    assert bot.verdict(_proof("spam", 10)) == bot.Held("honeypot")
    assert bot.verdict(_proof("spam", None)) == bot.Held("honeypot")


@pytest.mark.parametrize(("website", "elapsed_ms"), [(None, 45_000), ("", None), (None, None)])
def test_a_proof_without_the_forms_signals_did_not_come_from_the_form(
    website: str | None, elapsed_ms: int | None
) -> None:
    assert bot.verdict(_proof(website, elapsed_ms)) == bot.Held("not_from_form")


def test_no_proof_at_all_is_held() -> None:
    assert bot.verdict(None) == bot.Held("not_from_form")


@pytest.mark.parametrize(
    "given",
    [
        {"website": "x" * 501},
        {"elapsed_ms": -1},
        {"token": "t" * 4097},
        {"elapsed_ms": "4000"},  # strict: a number, not text
        {"name": "a field the proof doesn't have"},
    ],
)
def test_a_proof_is_bounded_and_strict(given: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        bot.BotProof.model_validate(given)


# --- the providers modules add -------------------------------------------------------------


class Tokens:
    """A provider that passes one token and holds the rest."""

    def __init__(self, raises: bool = False, answers: Any = None) -> None:
        self.raises = raises
        self.answers = answers

    async def verify(
        self, request: Request, proof: bot.BotProof | None, form: str
    ) -> bot.Pass | bot.Held:
        if self.raises:
            raise RuntimeError("the provider's service is down")
        if self.answers is not None:
            return self.answers  # type: ignore[no-any-return]
        return bot.Pass() if proof is not None and proof.token == "ok" else bot.Held("no_token")


def _module(
    module_id: str, provider: Any = None, router: APIRouter | None = None
) -> InstalledModule:
    manifest = Manifest.from_dict(
        {
            "id": module_id,
            "name": module_id.title(),
            "version": "0.1.0",
            "summary": "A module for the bot check's tests",
            "category": "admin",
            **({"routes": {"api": f"/api/{module_id}"}} if router is not None else {}),
        }
    )
    return InstalledModule(manifest, router=router, bot_provider=provider)


def test_only_the_modules_that_add_a_provider_show() -> None:
    found = bot.build(PROBES)
    assert list(found) == ["probe"]  # probe-addon adds none


def test_a_provider_named_like_the_kernels_or_not_async_is_refused() -> None:
    with pytest.raises(ValueError, match="the kernel's"):
        bot.build([_module("form", Tokens())])

    class Plain:
        def verify(self, request: Request, proof: Any, form: str) -> bot.Pass:
            return bot.Pass()

    with pytest.raises(ValueError, match="plain's BOT_PROVIDER"):
        bot.build([_module("plain", Plain())])


@pytest.mark.parametrize("form", ["contact", "Contact.inquiry", "contact.", ".inquiry", ""])
async def test_a_form_is_named_by_its_module(form: str) -> None:
    with pytest.raises(ValueError, match="isn't a form's name"):
        await bot.verify(object(), None, form=form, db=object())  # type: ignore[arg-type]


# --- verify, through an app ------------------------------------------------------------------


class Sent(BaseModel):
    # `kernel.BotProof`, not `bot.BotProof`: a field named `bot` hides the module.
    bot: BotProof | None = None


def _sender(module_id: str) -> APIRouter:
    router = APIRouter()

    @router.post("/send", dependencies=[Depends(public)])
    async def send(
        body: Sent, request: Request, db: AsyncSession = Depends(get_db)
    ) -> dict[str, str | None]:
        found = await bot.verify(request, body.bot, form=f"{module_id}.send", db=db)
        return {"held": found.reason if isinstance(found, bot.Held) else None}

    return router


def _ids() -> tuple[str, str]:
    """Two module ids no other test's app has, so their switches and settings are their own."""
    tail = uuid.uuid4().hex[:8]
    return f"sender-{tail}", f"tokens-{tail}"


async def _choose(database: Database, provider: str) -> None:
    async with database.sessions() as db:
        form = await settings.form(db, bot.SECTION)
        await settings.save(db, bot.SECTION, {"provider": provider}, version=form["version"])


async def _send(client: Any, sender: str, **proof: Any) -> str | None:
    answer = await client.post(f"/api/{sender}/send", json={"bot": proof} if proof else {})
    assert answer.status_code == 200, answer.text
    held: str | None = answer.json()["held"]
    return held


@pytest.mark.db
async def test_the_setting_picks_a_modules_provider_while_its_module_is_on(
    app_factory: AppFactory,
) -> None:
    sender, tokens = _ids()
    app = app_factory(
        [_module(sender, router=_sender(sender)), _module(tokens, Tokens())],
        modules_cache_seconds=0,
    )
    async with Client(app) as client:
        database: Database = app.state.database
        try:
            # The kernel's form check, by default.
            assert await _send(client, sender, website="", elapsed_ms=5_000) is None
            assert await _send(client, sender) == "not_from_form"

            await _choose(database, tokens)
            assert await _send(client, sender, token="ok") is None
            assert await _send(client, sender, website="", elapsed_ms=5_000) == "no_token"

            # Its module switched off: the form check again.
            async with database.sessions() as db:
                db.add(ModuleState(module_id=tokens, enabled=False))
                await db.commit()
            assert await _send(client, sender, token="ok") == "not_from_form"
            assert await _send(client, sender, website="", elapsed_ms=5_000) is None

            # A provider no module adds: the form check.
            await _choose(database, "nobody")
            assert await _send(client, sender, token="ok") == "not_from_form"
        finally:
            await _choose(database, bot.FORM)


@pytest.mark.db
@pytest.mark.parametrize(
    "provider",
    [Tokens(raises=True), Tokens(answers=True), Tokens(answers="pass")],
    ids=["raises", "answers-true", "answers-a-word"],
)
async def test_a_provider_that_fails_or_answers_neither_holds_the_submission(
    app_factory: AppFactory, provider: Tokens
) -> None:
    sender, tokens = _ids()
    app = app_factory([_module(sender, router=_sender(sender)), _module(tokens, provider)])
    async with Client(app) as client:
        database: Database = app.state.database
        try:
            await _choose(database, tokens)
            assert await _send(client, sender, token="ok") == "provider_error"
        finally:
            await _choose(database, bot.FORM)


@pytest.mark.db
async def test_it_reads_through_the_routes_own_session(app_factory: AppFactory) -> None:
    """One connection is enough: the route's `require_module` holds it, so
    `verify` reads the setting and the switches through the same session
    rather than wait for a second (Codex on #103)."""
    sender, _ = _ids()
    app = app_factory(
        [_module(sender, router=_sender(sender))],
        db_pool_size=1,
        db_max_overflow=0,
        modules_cache_seconds=0,
    )
    async with Client(app) as client:
        sent = client.post(
            f"/api/{sender}/send", json={"bot": {"website": "", "elapsed_ms": 5_000}}
        )
        answer = await asyncio.wait_for(sent, timeout=10)
    assert answer.status_code == 200, answer.text
    assert answer.json() == {"held": None}


def test_the_section_defaults_to_the_form_check() -> None:
    assert bot.Choice().provider == bot.FORM == "form"
    with pytest.raises(ValidationError):
        bot.Choice(provider="Not A Name")
