"""The AI's writing help over HTTP (decision 0058; `dev plans/contracts/kernel-ai.md`),
under `/api/kernel`: the editor's tasks for anyone holding `kernel.ai.write`,
the writing styles for `kernel.writing.manage`, and the key's state and check
and the model's list and save (decision 0064) for `kernel.settings.manage`.
The key and the writing rules themselves are saved through the settings
routes (`kernel.ai`, `kernel.writing`); the model only through its own.

Every task is billed, so all of them share one budget a person
(AI_RATE_LIMIT), counted after the permission check and before the key is
read. A task may name a writing style (`style_id`); absent or null is the
house style, the writing rules' own voice; a style gone since the editor
listed them answers 404."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import ai, server_copy, writing
from kernel.answers import Answer, Id, When
from kernel.auth.dependencies import require_permission
from kernel.auth.models import User
from kernel.db import get_db
from kernel.errors import Problem
from kernel.ratelimit import rate_limit
from kernel.settings import settings

router = APIRouter(tags=["kernel"])

WRITE = "kernel.ai.write"
MANAGE_STYLES = "kernel.writing.manage"
SETTINGS = "kernel.settings.manage"

#: The longest text a task reads, in characters.
TEXT_MAX = 20_000
#: Opening Settings → AI reads Anthropic's list: free, so a budget of its own,
#: not the writing help's (the owner, 2026-11-24).
MODELS_RATE = "60/1h"
NOT_OFFERED = "Anthropic doesn't offer that model to this key now. Choose one from the list."


async def budget(request: Request) -> None:
    """One budget a person for every AI task, AI_RATE_LIMIT."""
    await rate_limit(ai.rate_rule(), key="account", scope="kernel.ai")(request)


def _invalid(name: str, message: str) -> Problem:
    return Problem(
        "kernel.invalid_request",
        422,
        "Some of what was sent isn't valid.",
        errors={name: [message]},
    )


def _style_id(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise _invalid("style_id", "A writing style's id.") from None


# --- the editor's read ---------------------------------------------------------------


class StyleCard(Answer):
    id: Id
    name: str
    description: str


class AiState(Answer):
    #: A key can be used: the editor shows its AI buttons.
    ready: bool
    #: A saved key can't be read: the editor says so instead.
    unreadable: bool
    styles: list[StyleCard]


@router.get("/ai", response_model=AiState)
async def ai_state(
    _: User = Depends(require_permission(WRITE)), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Whether the AI's buttons show, and the styles to pick from."""
    state = await ai.readiness(db)
    styles = await writing.listed(db) if state.ready else []
    return {
        "ready": state.ready,
        "unreadable": state.unreadable,
        "styles": [
            {"id": str(row.id), "name": row.name, "description": row.description} for row in styles
        ],
    }


# --- the editor's tasks --------------------------------------------------------------


class _Task(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    #: The editor's label, "Post body": what the task writes.
    what: str = Field(min_length=1, max_length=80)
    style_id: str | None = None

    @field_validator("what")
    @classmethod
    def _has_words(cls, what: str) -> str:
        if not what.strip():
            raise ValueError("Say what the editor holds.")
        return what


class DraftAsk(_Task):
    topic: str = Field(min_length=1, max_length=300)
    length: ai.Length = "medium"


class Drafted(Answer):
    markdown: str


async def _ready(body: _Task, db: AsyncSession) -> tuple[ai.Writer, writing.Style | None]:
    """The writer, with the style the task names: 404 for a style gone, 503 without a key."""
    style = await writing.chosen(db, _style_id(body.style_id))
    return await ai.client(db), style


@router.post("/ai/draft", response_model=Drafted)
async def ai_draft(
    body: DraftAsk,
    _: User = Depends(require_permission(WRITE)),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A text drafted from a topic, in Markdown, for the editor to insert."""
    if not body.topic.strip():
        raise _invalid("topic", "Say what to write about.")
    writer, style = await _ready(body, db)
    text = await ai.draft(
        writer, what=body.what, topic=body.topic.strip(), length=body.length, style=style
    )
    return {"markdown": text}


class TitlesAsk(_Task):
    topic: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=TEXT_MAX)


class Titled(Answer):
    titles: list[str]


@router.post("/ai/titles", response_model=Titled)
async def ai_titles(
    body: TitlesAsk,
    _: User = Depends(require_permission(WRITE)),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Up to 8 titles, from what's written, or from the topic while nothing is."""
    if not body.body.strip() and not body.topic.strip():
        raise _invalid("topic", "Write something first, or say what it's about.")
    writer, style = await _ready(body, db)
    found = await ai.titles(
        writer, what=body.what, topic=body.topic.strip(), body=body.body, style=style
    )
    return {"titles": found}


class SummaryAsk(_Task):
    body: str = Field(min_length=1, max_length=TEXT_MAX)
    #: The summary field's own limit: blog's is 300.
    max: int = Field(ge=50, le=500)


class Summarised(Answer):
    summary: str


@router.post("/ai/summary", response_model=Summarised)
async def ai_summary(
    body: SummaryAsk,
    _: User = Depends(require_permission(WRITE)),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A summary of what's written, at most `max` characters."""
    if not body.body.strip():
        raise _invalid("body", "Write something first.")
    writer, style = await _ready(body, db)
    return {
        "summary": await ai.summary(
            writer, what=body.what, body=body.body, most=body.max, style=style
        )
    }


class SearchAsk(_Task):
    title: str = Field(default="", max_length=300)
    body: str = Field(min_length=1, max_length=TEXT_MAX)


class SearchWords(Answer):
    title: str
    description: str


@router.post("/ai/search", response_model=SearchWords)
async def ai_search(
    body: SearchAsk,
    _: User = Depends(require_permission(WRITE)),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The title a search result shows (at most 70) and the description under it (at most 160)."""
    if not body.body.strip():
        raise _invalid("body", "Write something first.")
    writer, style = await _ready(body, db)
    shown, under = await ai.search_words(
        writer, what=body.what, title=body.title, body=body.body, style=style
    )
    return {"title": shown, "description": under}


class RewriteAsk(_Task):
    markdown: str = Field(min_length=1, max_length=TEXT_MAX)


@router.post("/ai/rewrite", response_model=Drafted)
async def ai_rewrite(
    body: RewriteAsk,
    _: User = Depends(require_permission(WRITE)),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The text rewritten, saying what it said: 502 `kernel.ai_rewrite_lost`
    when a link or image went missing, and the editor keeps its text."""
    if not body.markdown.strip():
        raise _invalid("markdown", "Write something first.")
    writer, style = await _ready(body, db)
    return {"markdown": await ai.rewrite(writer, what=body.what, text=body.markdown, style=style)}


class StyleRulesAsk(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    samples: list[str] = Field(min_length=1, max_length=writing.SAMPLES_MAX)

    @field_validator("samples")
    @classmethod
    def _fit(cls, samples: list[str]) -> list[str]:
        kept = writing.samples_kept(samples)
        if not kept:
            raise ValueError("Add a sample of writing to draft the rules from.")
        if any(len(sample) > writing.SAMPLE_MAX for sample in kept):
            raise ValueError(f"A sample is at most {writing.SAMPLE_MAX} characters.")
        return kept


class StyleRules(Answer):
    voice_rules: str
    #: One phrase a line.
    avoid: str


@router.post("/ai/style-rules", response_model=StyleRules)
async def ai_style_rules(
    body: StyleRulesAsk,
    _: User = Depends(require_permission(MANAGE_STYLES)),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Voice rules and phrases to avoid drafted from a style's samples, fitted
    to what a style holds, for an editor to change before the save."""
    writer = await ai.client(db)
    voice_rules, avoid = await ai.style_rules(writer, body.samples)
    return {"voice_rules": voice_rules, "avoid": avoid}


# --- Settings → AI -----------------------------------------------------------------


class AiKey(Answer):
    #: Where the key in use comes from: saved in Settings, the host's, or none.
    source: ai.Source
    #: The model in use, and where it comes from (decision 0064).
    model: str
    model_source: ai.ModelSource
    unreadable: bool


@router.get("/admin/ai", response_model=AiKey)
async def ai_key(
    _: User = Depends(require_permission(SETTINGS)), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The key's state, never the key."""
    state = await ai.readiness(db)
    model, model_source = await ai.model_in_use(db)
    return {
        "source": await ai.source(db),
        "model": model,
        "model_source": model_source,
        "unreadable": state.unreadable,
    }


class ModelOffered(Answer):
    id: str
    #: Anthropic's display name: Claude Opus 5.5.
    name: str


class ModelInUse(Answer):
    id: str
    #: None when Anthropic doesn't list it for the key.
    name: str | None
    source: ai.ModelSource
    #: False for a retired model, or a host value with a typo.
    listed: bool


class AiModels(Answer):
    #: The newest Opus, Sonnet and Haiku, in that order.
    models: list[ModelOffered]
    in_use: ModelInUse


async def models_budget(request: Request) -> None:
    await rate_limit(MODELS_RATE, key="account", scope="kernel.ai.models")(request)


async def _offer(db: AsyncSession) -> dict[str, Any]:
    """Anthropic's list read now, with the key in use: 503 without a working
    key, 502 when Anthropic can't be read."""
    listed = await (await ai.client(db)).models()
    model, source = await ai.model_in_use(db)
    return ai.offer(listed, model, source)


@router.get("/admin/ai/models", response_model=AiModels)
async def ai_models(
    _: User = Depends(require_permission(SETTINGS)),
    __: None = Depends(models_budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The models Settings → AI offers, read from Anthropic each time: never cached."""
    return await _offer(db)


class ModelPick(BaseModel):
    """`{version, model}`: the section's version as the form read it; null is the host's model."""

    model_config = ConfigDict(strict=True, extra="forbid")

    version: int = Field(ge=0)
    model: str | None = Field(max_length=ai.MAX_MODEL_LENGTH)


class ModelSaved(Answer):
    version: int
    changed: list[str]
    merged: list[str]


@router.put("/admin/ai/model", response_model=ModelSaved)
async def ai_model(
    body: ModelPick,
    user: User = Depends(require_permission(SETTINGS)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves the model picked, once Anthropic's list, read now, offers it;
    null goes back to the host's. Nothing is saved when the list can't be read."""
    if body.model is not None:
        offered = {each["id"] for each in (await _offer(db))["models"]}
        if body.model not in offered:
            raise Problem(
                "kernel.invalid_request", 422, NOT_OFFERED, errors={"model": [NOT_OFFERED]}
            )
    saved = await settings.save(
        db, ai.SECTION, {"model": body.model}, version=body.version, by=user.id, via="ai.model"
    )
    return {"version": saved.version, "changed": saved.changed, "merged": saved.merged}


class Checked(Answer):
    works: Literal[True]
    source: ai.Source


@router.post("/admin/ai/check", response_model=Checked)
async def ai_check(
    _: User = Depends(require_permission(SETTINGS)), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Asks Anthropic whether the key in use works. A refusal is 502
    `kernel.ai_failed`, never a 401, which the admin would take for its own
    session ending."""
    _key, source = await ai.key_in_use(db)
    await (await ai.client(db)).check()
    return {"works": True, "source": source}


# --- Settings → Writing --------------------------------------------------------------


class RuleShown(Answer):
    id: str
    label: str
    text: str
    why: str
    warning: str


class WritingRules(Answer):
    #: How the site works, fixed: what every task starts from.
    mechanics: str
    rules: list[RuleShown]
    #: The default rules as text, for the site's own to start from.
    default_text: str


@router.get("/admin/writing/rules", response_model=WritingRules)
async def writing_rules(
    _: User = Depends(require_permission(SETTINGS)), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The default rules the Writing tab offers as switches, read-only."""
    site = await server_copy.identity(db)
    return {
        "mechanics": writing.mechanics(site.name),
        "rules": [
            {
                "id": rule.id,
                "label": rule.label,
                "text": rule.text,
                "why": rule.why,
                "warning": rule.warning,
            }
            for rule in writing.DEFAULT_RULES
        ],
        "default_text": writing.default_text(),
    }


class StyleShown(Answer):
    id: Id
    version: int
    name: str
    description: str
    voice_rules: str
    #: One phrase a line.
    avoid: str
    samples: list[str]
    created_by_id: Id | None
    updated_by_id: Id | None
    created_at: When
    updated_at: When


class Styles(Answer):
    items: list[StyleShown]


@router.get("/admin/writing/styles", response_model=Styles)
async def writing_styles(
    _: User = Depends(require_permission(WRITE)), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Every style, by name."""
    return {"items": [writing.view(row) for row in await writing.listed(db)]}


class NewStyle(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1, max_length=writing.NAME_MAX)
    description: str = Field(default="", max_length=writing.DESCRIPTION_MAX)
    voice_rules: str = Field(default="", max_length=writing.VOICE_RULES_MAX)
    avoid: str = Field(
        default="", max_length=writing.AVOID_PHRASES_MAX * (writing.AVOID_PHRASE_MAX + 2)
    )
    samples: list[str] = Field(default_factory=list, max_length=writing.SAMPLES_MAX)


class StyleChanges(BaseModel):
    """The fields to change, at the `version` the form was read at."""

    model_config = ConfigDict(strict=True, extra="forbid")

    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=writing.NAME_MAX)
    description: str | None = Field(default=None, max_length=writing.DESCRIPTION_MAX)
    voice_rules: str | None = Field(default=None, max_length=writing.VOICE_RULES_MAX)
    avoid: str | None = Field(
        default=None, max_length=writing.AVOID_PHRASES_MAX * (writing.AVOID_PHRASE_MAX + 2)
    )
    samples: list[str] | None = Field(default=None, max_length=writing.SAMPLES_MAX)


@router.post("/admin/writing/styles", status_code=201, response_model=StyleShown)
async def new_style(
    body: NewStyle,
    user: User = Depends(require_permission(MANAGE_STYLES)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A new style: 409 `kernel.writing_style_name_taken` for a name another has, in any case."""
    row = await writing.create(
        db,
        writing.StyleFields(
            name=body.name,
            description=body.description,
            voice_rules=body.voice_rules,
            avoid=body.avoid,
            samples=body.samples,
        ),
        actor=user.id,
    )
    await db.commit()
    return writing.view(row)


STYLE = "/admin/writing/styles/{style_id}"


@router.get(STYLE, response_model=StyleShown)
async def one_style(
    style_id: uuid.UUID,
    _: User = Depends(require_permission(MANAGE_STYLES)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await writing.find(db, style_id)
    if row is None:
        raise writing.gone()
    return writing.view(row)


@router.patch(STYLE, response_model=StyleShown)
async def change_style(
    style_id: uuid.UUID,
    body: StyleChanges,
    user: User = Depends(require_permission(MANAGE_STYLES)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Changes the fields sent: 409 `kernel.writing_style_changed` when it was saved since `version`."""
    sent = body.model_fields_set - {"version"}
    for name in sorted(sent):
        if name == "name" and getattr(body, name) is None:
            raise _invalid(name, "A style has a name.")
    row = await writing.change(
        db,
        style_id,
        writing.StyleFields(
            **{name: getattr(body, name) for name in sent if getattr(body, name) is not None}
        ),
        version=body.version,
        actor=user.id,
    )
    await db.commit()
    return writing.view(row)


@router.delete(STYLE, status_code=204)
async def delete_style(
    style_id: uuid.UUID,
    user: User = Depends(require_permission(MANAGE_STYLES)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await writing.remove(db, style_id, actor=user.id)
    await db.commit()
    return Response(status_code=204)
