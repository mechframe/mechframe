"""The AI's writing help (decision 0058; `dev plans/contracts/kernel-ai.md`):
the site's Anthropic client, and the editor's tasks.

Lifted from VybeSite (`services/ai_key_service.py`, `services/anthropic_service.py`),
reshaped to the kernel's settings service.

**The key.** `ANTHROPIC_API_KEY` on the host, typed by the owner, or one an
admin saves in Settings → AI, the settings section `kernel.ai`, sealed by
`kernel.crypto` and never answered. **A saved key wins; the host's is the
fallback** (VybeSite's order, and decision 0046's for `sign_up_mode`). A saved
key that can't be opened (`ENCRYPTION_KEYS` changed) is reported, never
quietly swapped for the host's: that would hide that the saved key is lost,
and use a key the admin meant to replace. A host value that couldn't be a key
(blank, spaces, the `.env.example` placeholder, too short or too long) counts
as none. This module is the only place a key is opened, just before a call.

**A call.** `await client(db)` is a `Writer` with the key in use, writing for
the site (its name) by its writing constitution (`kernel.writing`). Every task
sends the constitution's block first, then the chosen style's, each cached
by Anthropic for a run of tasks, then the task. Failures are plain sentences
(`kernel.ai_failed`, 502), never Anthropic's own words or the key.

A module's own AI task (a generated cover) calls `client(db)` and `write`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, cast

import anthropic
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import crypto, markdown, server_copy, writing
from kernel.errors import Problem
from kernel.ratelimit import parse_rule
from kernel.settings import settings

#: The settings section that holds a saved key.
SECTION = "kernel.ai"

Source = Literal["settings", "environment", "none"]
Effort = Literal["low", "medium", "high"]

#: Anthropic's keys are about 108 characters. These bounds only catch a paste
#: that is plainly something else; Check is the real test.
MIN_KEY_LENGTH = 20
MAX_KEY_LENGTH = 400

#: Server-side refusal fallback, routed by category; its beta header.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
#: The models that take `fallbacks` (another ANTHROPIC_MODEL simply goes without).
FALLBACK_MODELS = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)

#: How much of a text the titles, summary and search tasks read.
BODY_READ = 12_000
#: The longest a draft or a rewrite may take. Railway's edge closes a request
#: that sends nothing for 5 minutes, so the server answers first, with a reason;
#: and a long task is never tried again, which would outlive that limit.
LONG_SECONDS = 270.0

NO_KEY = (
    "No Anthropic API key is set, so the AI's writing help is off. An admin can add one in "
    "Settings → AI."
)
UNREADABLE_KEY = (
    "The saved Anthropic API key can't be read, which happens when the server's ENCRYPTION_KEYS "
    "change. An admin can save it again in Settings → AI."
)
CUT_OFF = "The AI ran out of room before it finished. Try a shorter length."
WRONG_SHAPE = "The AI's answer wasn't in the form asked for. Try again."


class KeySettings(BaseModel):
    """The settings section `kernel.ai`: a key saved in Settings → AI. A
    value that couldn't be a key is refused, in words that never repeat it."""

    model_config = ConfigDict(strict=True, extra="forbid")

    api_key: SecretStr | None = None

    @field_validator("api_key")
    @classmethod
    def _could_be_a_key(cls, key: SecretStr | None) -> SecretStr | None:
        if key is not None and (problem := key_problem(key.get_secret_value())) is not None:
            raise ValueError(problem)
        return key


@dataclass
class _Installed:
    host_key: str = ""
    model: str = "claude-opus-5-5"
    rate_rule: str = "20/1h"
    #: Tests and the harness hand in an httpx2 transport; None is the real network.
    transport: Any = None


_installed = _Installed()


def install(*, api_key: SecretStr, model: str, rate_rule: str) -> None:
    """The host's key, the model and the budget, from the config (`create_app`).
    A bad AI_RATE_LIMIT fails the start, not the first call."""
    parse_rule(rate_rule)
    _installed.host_key = api_key.get_secret_value().strip()
    _installed.model = model
    _installed.rate_rule = rate_rule


def rate_rule() -> str:
    """AI_RATE_LIMIT, the budget every AI call shares."""
    return _installed.rate_rule


def model() -> str:
    return _installed.model


def use_transport(transport: Any) -> Any:
    """Calls go through `transport` (an httpx2 one) from now on: a fake
    Anthropic, for the tests and the harness. Answers the one it replaces."""
    before = _installed.transport
    _installed.transport = transport
    return before


def key_problem(key: str) -> str | None:
    """Why a pasted value can't be an API key, or None if it could be. The
    message never repeats the value: errors are shown, and can reach logs."""
    if any(character.isspace() for character in key):
        return "An API key has no spaces or line breaks in it. Copy it again from the Anthropic console."
    if len(key) < MIN_KEY_LENGTH:
        return "That's too short to be an Anthropic API key. Copy the whole key from the Anthropic console."
    if len(key) > MAX_KEY_LENGTH:
        return "That's too long to be an Anthropic API key. Copy just the key from the Anthropic console."
    return None


def _host_key() -> str | None:
    key = _installed.host_key
    return key if key and key_problem(key) is None else None


async def _saved_kept(db: AsyncSession) -> bool:
    """A key is saved in Settings → AI, without opening it."""
    form = await settings.form(db, SECTION)
    return bool(form["values"]["api_key"]["kept"])


async def source(db: AsyncSession) -> Source:
    """Where the key in use comes from, without opening it."""
    if await _saved_kept(db):
        return "settings"
    return "environment" if _host_key() is not None else "none"


async def _saved_key(db: AsyncSession) -> str | None:
    """The saved key opened; None when it can't be."""
    try:
        saved = cast(KeySettings, await settings.for_module(db, SECTION))
    except crypto.SealError:
        return None
    return saved.api_key.get_secret_value() if saved.api_key is not None else None


@dataclass(frozen=True)
class Readiness:
    #: A key can be used: the AI's buttons show.
    ready: bool
    #: A saved key can't be opened: the buttons say so instead.
    unreadable: bool


async def readiness(db: AsyncSession) -> Readiness:
    if await _saved_kept(db):
        readable = await _saved_key(db) is not None
        return Readiness(ready=readable, unreadable=not readable)
    return Readiness(ready=_host_key() is not None, unreadable=False)


async def key_in_use(db: AsyncSession) -> tuple[str, Source]:
    """The key to call Anthropic with, and where it came from: 503
    `kernel.ai_off` with none, `kernel.ai_key_unreadable` for a saved one that
    can't be opened."""
    if await _saved_kept(db):
        key = await _saved_key(db)
        if key is None:
            raise Problem("kernel.ai_key_unreadable", 503, UNREADABLE_KEY)
        return key, "settings"
    host = _host_key()
    if host is None:
        raise Problem("kernel.ai_off", 503, NO_KEY)
    return host, "environment"


# --- the system blocks -------------------------------------------------------------

#: What a chosen writing style is, said before its own words.
STYLE_INTRO = (
    "Write in the style below. It shapes how the writing sounds, never what it says, and wherever "
    "it seems to disagree with the writing constitution above, the constitution wins."
)
#: Said before a style's samples.
SAMPLES_INTRO = "Match how these sound; never reuse their facts, names, claims or numbers."


def _cached(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}


def style_text(style: writing.Style) -> str:
    """A chosen style, for the block after the constitution: its own fields
    only, empty parts left out."""
    parts = [f"<name>{style.name}</name>"]
    if style.description:
        parts.append(f"<description>{style.description}</description>")
    if style.voice_rules:
        parts.append(f"<voice_rules>\n{style.voice_rules}\n</voice_rules>")
    if style.avoid:
        listed = "\n".join(f"- {phrase}" for phrase in style.avoid)
        parts.append(f"<phrases_to_avoid>\nNever use these phrases:\n{listed}\n</phrases_to_avoid>")
    if style.samples:
        shown = "\n".join(f"<sample>\n{sample}\n</sample>" for sample in style.samples)
        parts.append(f"<samples>\n{SAMPLES_INTRO}\n{shown}\n</samples>")
    body = "\n".join(parts)
    return f"{STYLE_INTRO}\n\n<style>\n{body}\n</style>"


def _refusal(status: int) -> str:
    """What an error status means, in words that never include the key or Anthropic's own answer."""
    if status == 401:
        return (
            "Anthropic didn't accept the key. Check it was copied in full and hasn't been revoked."
        )
    if status == 403:
        return "Anthropic refused the key: it may not be allowed to use the API."
    if status == 429:
        return "Anthropic is busy, or the account has reached a limit. Try again in a minute."
    return f"Anthropic answered with an error ({status}). Try again in a minute."


def _failed(sentence: str) -> Problem:
    return Problem("kernel.ai_failed", 502, sentence)


class Writer:
    """Calls Anthropic with one key, for the site, by its writing constitution.
    Made per request by `client`."""

    def __init__(self, key: str, *, constitution: str, site_name: str) -> None:
        self._key = key
        self.model = _installed.model
        self.site_name = site_name
        self.constitution = constitution

    def _client(self, timeout: float, retries: int) -> AsyncAnthropic:
        transport = _installed.transport
        http_client = (
            DefaultAsyncHttpxClient(transport=transport) if transport is not None else None
        )
        return AsyncAnthropic(
            api_key=self._key, timeout=timeout, max_retries=retries, http_client=http_client
        )

    def system(self, style: writing.Style | None) -> list[dict[str, Any]]:
        """The constitution's block, then the chosen style's; the constitution alone for the house style."""
        blocks = [_cached(self.constitution)]
        if style is not None:
            blocks.append(_cached(style_text(style)))
        return blocks

    async def check(self) -> None:
        """Whether the key works, by the cheapest request Anthropic answers:
        a list of one model, which costs nothing."""
        try:
            async with self._client(timeout=15.0, retries=0) as client:
                await client.models.list(limit=1)
        except anthropic.APITimeoutError:
            raise _failed("Anthropic didn't answer in time. Try again in a minute.") from None
        except anthropic.APIConnectionError:
            raise _failed("Could not reach Anthropic from the server.") from None
        except anthropic.APIStatusError as error:
            raise _failed(_refusal(error.status_code)) from None

    async def write(
        self,
        task: str,
        *,
        style: writing.Style | None = None,
        max_tokens: int,
        effort: Effort,
        seconds: float = 60.0,
        retries: int = 2,
        schema: dict[str, Any] | None = None,
        cut_off: str = CUT_OFF,
    ) -> Any:
        """One task, after the constitution and the chosen style: its words,
        or with `schema` (a JSON Schema) the object it describes. 502
        `kernel.ai_failed` with a plain sentence otherwise; `cut_off` when the
        answer ran out of room. `seconds` is how long to wait for it."""
        output: dict[str, Any] = {"effort": effort}
        if schema is not None:
            output["format"] = {"type": "json_schema", "schema": schema}
        fallback: dict[str, Any] = (
            {"betas": [FALLBACK_BETA], "fallbacks": "default"}
            if self.model in FALLBACK_MODELS
            else {}
        )
        try:
            async with self._client(timeout=seconds, retries=retries) as client:
                reply = await client.beta.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=cast(Any, self.system(style)),
                    messages=[{"role": "user", "content": task}],
                    output_config=cast(Any, output),
                    **fallback,
                )
        except anthropic.APITimeoutError:
            raise _failed("The AI took too long to answer. Try again.") from None
        except anthropic.APIConnectionError:
            raise _failed("Could not reach the AI. Try again.") from None
        except anthropic.APIStatusError as error:
            raise _failed(_refusal(error.status_code)) from None
        if reply.stop_reason == "refusal":
            raise _failed("The AI declined this request. Try putting it another way.")
        if reply.stop_reason == "max_tokens":
            raise _failed(cut_off)
        words = "".join(
            getattr(block, "text", "") for block in reply.content if block.type == "text"
        )
        if schema is None:
            return words
        try:
            return json.loads(words)
        except ValueError:
            raise _failed(WRONG_SHAPE) from None


async def client(db: AsyncSession) -> Writer:
    """A writer with the key in use, for the site, by its writing constitution:
    503 `kernel.ai_off` or `kernel.ai_key_unreadable` without one."""
    key, _ = await key_in_use(db)
    site = await server_copy.identity(db)
    saved = cast(writing.Constitution, await settings.for_module(db, writing.SECTION))
    return Writer(key, constitution=writing.block(saved, site.name), site_name=site.name)


# --- the editor's tasks ------------------------------------------------------------

Length = Literal["short", "medium", "long"]
WORDS = {"short": "400-600", "medium": "800-1200", "long": "1500-2000"}
#: The most titles a request answers, and the longest each may be.
TITLES_MOST = 8
TITLE_MAX = 200


def _what(what: str) -> str:
    """The editor's label as a task says it: "Post body" → "post body"."""
    words = " ".join(what.split())
    return words[:1].lower() + words[1:]


async def draft(
    writer: Writer, *, what: str, topic: str, length: Length, style: writing.Style | None
) -> str:
    """A text in Markdown, drafted from a topic. Its voice is the chosen
    style's, or the constitution's own."""
    task = (
        f"You're writing the {_what(what)} for {writer.site_name}.\n\n"
        f"Topic: {topic}\n"
        f"Length: {WORDS[length]} words\n\n"
        "Write for the readers the site serves, and make one clear point. Return only the text in "
        "Markdown, with no title (the editor has a field for it), no front matter and no code fences: "
        "start with the opening paragraph and use ## for section headings."
    )
    words = await writer.write(
        task, style=style, max_tokens=16000, effort="high", seconds=LONG_SECONDS, retries=0
    )
    drafted = str(words).strip()
    if not drafted:
        raise _failed("The draft came back empty. Try again.")
    return drafted


_TITLES = {
    "type": "object",
    "properties": {"titles": {"type": "array", "items": {"type": "string"}}},
    "required": ["titles"],
    "additionalProperties": False,
}


async def titles(
    writer: Writer, *, what: str, topic: str, body: str, style: writing.Style | None
) -> list[str]:
    """Up to 8 titles, from what's written, or from the topic while nothing is."""
    about = (
        f"It reads:\n\n<text>\n{body[:BODY_READ]}\n</text>"
        if body.strip()
        else f"It's about: {topic}"
    )
    task = (
        f"Give {TITLES_MOST} title options for the {_what(what)} below, for {writer.site_name}.\n\n"
        f"{about}\n\n"
        'Plain and specific, as a person would write them: no clickbait and no "X: the Y" formula.'
    )
    found = await writer.write(task, style=style, max_tokens=2000, effort="low", schema=_TITLES)
    listed = found.get("titles") if isinstance(found, dict) else None
    if not isinstance(listed, list) or not all(isinstance(title, str) for title in listed):
        raise _failed(WRONG_SHAPE)
    kept: list[str] = []
    for title in listed:
        title = " ".join(title.split()).strip("\"'“”")
        if (
            title
            and len(title) <= TITLE_MAX
            and title.casefold() not in {t.casefold() for t in kept}
        ):
            kept.append(title)
    if not kept:
        raise _failed(WRONG_SHAPE)
    return kept[:TITLES_MOST]


_SUMMARY = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}


async def summary(
    writer: Writer, *, what: str, body: str, most: int, style: writing.Style | None
) -> str:
    """One or two sentences saying what the reader will find, at most `most` characters."""
    task = (
        f"Write the summary of this {_what(what)}: one or two plain sentences, under {most} "
        f"characters, that say what the reader will find.\n\n<text>\n{body[:BODY_READ]}\n</text>"
    )
    found = await writer.write(task, style=style, max_tokens=1000, effort="low", schema=_SUMMARY)
    words = found.get("summary") if isinstance(found, dict) else None
    if not isinstance(words, str) or not words.strip():
        raise _failed(WRONG_SHAPE)
    return markdown.excerpt(words, most)


_SEARCH = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
    "required": ["title", "description"],
    "additionalProperties": False,
}
#: As the kit's SearchFields hold them (`SEARCH_TITLE_MAX`, `SEARCH_DESCRIPTION_MAX`).
SEARCH_TITLE_MAX = 70
SEARCH_DESCRIPTION_MAX = 160


async def search_words(
    writer: Writer, *, what: str, title: str, body: str, style: writing.Style | None
) -> tuple[str, str]:
    """The title a search result shows and the description under it."""
    task = (
        f"Write the title a search result shows (at most {SEARCH_TITLE_MAX} characters) and the "
        f"description under it (at most {SEARCH_DESCRIPTION_MAX} characters) for this "
        f"{_what(what)} of {writer.site_name}.\n\nTitle: {title}\n\n<text>\n{body[:BODY_READ]}\n</text>"
    )
    found = await writer.write(task, style=style, max_tokens=1000, effort="low", schema=_SEARCH)
    if not isinstance(found, dict):
        raise _failed(WRONG_SHAPE)
    shown, under = found.get("title"), found.get("description")
    if not (isinstance(shown, str) and isinstance(under, str) and shown.strip() and under.strip()):
        raise _failed(WRONG_SHAPE)
    return markdown.excerpt(shown, SEARCH_TITLE_MAX), markdown.excerpt(
        under, SEARCH_DESCRIPTION_MAX
    )


#: What a text points at: a link's or image's target, inside `](…)`; an
#: autolink, `<https://…>`; and a bare address, without the punctuation that
#: may follow it in a sentence.
_TARGET = re.compile(r"\]\(\s*<?([^\s)>]+)")
_AUTOLINK = re.compile(r"<(https?://[^\s>]+)>", re.IGNORECASE)
_BARE = re.compile(r"https?://[^\s<>()\[\]\"'`]+", re.IGNORECASE)
_AFTER_BARE = ".,;:!?*_"
#: A rewrite answered inside the tags its text was sent in.
_IN_TEXT = re.compile(r"\A\s*<text>(.*)</text>\s*\Z", re.DOTALL)


def addresses(text: str) -> set[str]:
    """Every address a text's links and images point at."""
    found = set(_TARGET.findall(text)) | set(_AUTOLINK.findall(text))
    found |= {address.rstrip(_AFTER_BARE) for address in _BARE.findall(text)}
    found.discard("")
    return found


async def rewrite(writer: Writer, *, what: str, text: str, style: writing.Style | None) -> str:
    """The text rewritten in the chosen style, or the house style, saying what
    it said. Every address its links and images point at must come back, or
    nothing does (502 `kernel.ai_rewrite_lost`): the editor keeps its text."""
    voice = (
        "in the style set out above"
        if style is not None
        else "in the house style, the voice the writing constitution above describes"
    )
    task = (
        f"Here is part of the {_what(what)} of {writer.site_name}:\n\n<text>\n{text}\n</text>\n\n"
        f"Rewrite it {voice}. Change how it is written, never what it says:\n"
        "- Keep every fact, claim, number, name and example, and add nothing it doesn't say: no "
        "claim, example, statistic or quotation of your own.\n"
        "- Keep every link's address and every image's Markdown exactly as they are, each with the "
        "text it belongs to.\n"
        "- Keep its structure: the same ## sections, in the same order.\n"
        "- Return only the rewritten text in Markdown: no title or # heading, no front matter, no "
        "code fences, and nothing before or after it."
    )
    unchanged = "so the text wasn't changed. Try again."
    words = await writer.write(
        task,
        style=style,
        max_tokens=16000,
        effort="high",
        seconds=LONG_SECONDS,
        retries=0,
        cut_off=f"The AI ran out of room before it finished the rewrite, {unchanged}",
    )
    answer = str(words)
    inside = _IN_TEXT.match(answer)
    rewritten = (inside.group(1) if inside else answer).strip()
    if not rewritten:
        raise _failed(f"The rewrite came back empty, {unchanged}")
    left_out = len(addresses(text) - addresses(rewritten))
    if left_out:
        things = "link or image" if left_out == 1 else "links or images"
        raise Problem(
            "kernel.ai_rewrite_lost", 502, f"The rewrite left out {left_out} {things}, {unchanged}"
        )
    return rewritten


_STYLE_RULES = {
    "type": "object",
    "properties": {
        "voice_rules": {"type": "string"},
        "avoid": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["voice_rules", "avoid"],
    "additionalProperties": False,
}


async def style_rules(writer: Writer, samples: list[str]) -> tuple[str, str]:
    """Voice rules and phrases to avoid drafted from a style's samples, fitted
    to what a style holds, for an editor to change before the save. After the
    constitution alone, so the model leaves out what it already bans."""
    shown = "\n\n".join(f"<sample>\n{sample}\n</sample>" for sample in samples)
    task = (
        f"{shown}\n\n"
        "The samples above are writing in a voice someone wants the site to use. This time you aren't "
        "writing for the site: describe how the samples sound, so that a writer could match the voice "
        "on other subjects.\n\n"
        'In voice_rules, give 6 to 12 short rules, one per line, each starting "- ". Cover sentence '
        "length and rhythm, word choice, how the reader is addressed, how paragraphs open and close, "
        "structure and punctuation. Describe the voice only: never a fact, name, claim, number or "
        "topic from the samples.\n\n"
        "In avoid, give up to 15 short phrases a writer of this voice would never use. Leave out the "
        "ones the writing constitution above already bans."
    )
    found = await writer.write(
        task,
        max_tokens=8000,
        effort="medium",
        seconds=180.0,
        retries=0,
        schema=_STYLE_RULES,
        cut_off="The AI ran out of room before it finished the rules. Try again.",
    )
    if not (
        isinstance(found, dict)
        and isinstance(found.get("voice_rules"), str)
        and isinstance(found.get("avoid"), list)
        and all(isinstance(phrase, str) for phrase in found["avoid"])
    ):
        raise _failed(WRONG_SHAPE)
    return writing.rules_that_fit(found["voice_rules"]), writing.phrases_that_fit(found["avoid"])


__all__ = [
    "SECTION",
    "KeySettings",
    "Readiness",
    "Source",
    "Writer",
    "client",
    "key_in_use",
    "readiness",
    "source",
]
