"""The site's writing rules and styles, for the AI's writing help (decision
0058; `dev plans/contracts/kernel-ai.md`).

Lifted from VybeSite's writing constitution (`services/writing_constitution.py`)
and writing styles (`services/writing_styles.py`), without its claims list,
which waits (the owner, 2026-11-22).

**The writing constitution** is the settings section `kernel.writing`, kept in
Settings → Writing. Every AI task starts from its block (`block`), in three
parts:

1. **How the site works** (`mechanics`), fixed: who the writing is for (the
   site's name) and how a link is written so it works.
2. **The rules,** which the site chooses: the defaults (`DEFAULT_RULES`), each
   switched on or off, followed by rules of its own; or its own text in their
   place.
3. **The brief:** what the site says about itself, in labelled boxes.

The block is the same text until an admin saves, so Anthropic caches it for
a run of tasks (`kernel.ai`).

**A writing style** (`kernel_writing_style`) is a voice the AI can be asked to
write in: a name, a short description, voice rules, phrases to avoid and up
to three samples. It shapes how the writing sounds, never what it says: the
constitution comes first and wins. Editors holding `kernel.writing.manage`
keep them; anyone holding `kernel.ai.write` picks one.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import audit, clock
from kernel.errors import Problem
from kernel.models import WritingStyle

#: The settings section that holds the writing constitution.
SECTION = "kernel.writing"

#: The longest a brief's box or the added rules may be, in characters.
BOX_MAX = 4000
#: The longest the site's own text may be.
OWN_TEXT_MAX = 20000

RuleId = Literal[
    "verified_only", "no_fabrication", "illustrations", "plain_words", "ai_tells", "em_dash"
]


@dataclass(frozen=True)
class DefaultRule:
    id: RuleId
    #: The switch's words in Settings.
    label: str
    #: What the writer is told while it's on.
    text: str
    #: The switch's one-line reason.
    why: str
    #: Said when it's switched off, if anything.
    warning: str = ""


#: Said when the fabrication rule is switched off: fake reviews and
#: testimonials are illegal in the US (VybeSite checked ftc.gov, 2026-10-11).
FABRICATION_WARNING = (
    "In the US, fake reviews and testimonials, AI-written ones included, are banned by the FTC's rule "
    "on consumer reviews and testimonials (16 CFR Part 465, in force since 21 October 2024), with "
    "civil penalties for knowing violations. Switch this off only if you understand that risk."
)

#: The phrases readers now take for machine writing (VybeSite's
#: `post_checks.AI_TELLS`, their labels only: the editor doesn't flag them yet).
AI_TELLS = (
    "delve",
    "in today's fast-paced world",
    "ever-evolving",
    "landscape",
    "it's not just X, it's Y",
    "isn't just",
    "more than just",
    "not only... but also",
    "game-changer",
    "revolutionize",
    "transformative",
    "unlock potential",
    "unleash",
    "harness the power, the power of",
    "seamless",
    "cutting-edge, state-of-the-art",
    "supercharge",
    "leverage",
    "elevate",
    "empower",
    "streamline",
    "robust, holistic, synergy, paradigm",
    "myriad, plethora",
)

#: The rules every site starts with, each a switch, all on until it says otherwise.
DEFAULT_RULES: tuple[DefaultRule, ...] = (
    DefaultRule(
        "verified_only",
        "Claim only what's verified",
        "Claim nothing that isn't verified. A fact, a feature, a number or a result the task doesn't "
        "give you isn't claimable, so leave it out rather than guess.",
        "Stops the writer guessing facts about the site.",
    ),
    DefaultRule(
        "no_fabrication",
        "Never invent customers, quotes, reviews or numbers",
        "Never invent a customer, a quotation, a review, a statistic, a study, a number or a "
        "first-person experience.",
        "What's invented reads to a visitor as fact.",
        FABRICATION_WARNING,
    ),
    DefaultRule(
        "illustrations",
        "Label made-up examples",
        "When an example helps, use plainly made-up people and firms, and present it as an "
        "illustration.",
        "A reader can tell an example from a real case.",
    ),
    DefaultRule(
        "plain_words",
        "Write plainly",
        "Write like a person, not a model: plain words, specifics the reader would recognise, short "
        "paragraphs and sentences of varied length.",
        "Writing readers trust to be a person's.",
    ),
    DefaultRule(
        "ai_tells",
        "Avoid phrases that read as AI writing",
        "Readers now take these for machine writing, so never use them: "
        + "; ".join(f'"{phrase}"' for phrase in AI_TELLS)
        + ".",
        "Keeps out the phrases readers take for machine writing.",
    ),
    DefaultRule(
        "em_dash",
        "At most one em dash a piece",
        "Use an em dash at most once in a piece of writing.",
        "A run of em dashes reads as machine writing.",
    ),
)
RULE_IDS: tuple[str, ...] = tuple(rule.id for rule in DEFAULT_RULES)

#: The brief's boxes: (field, tag), in the order the block and the panel give them.
BRIEF = (
    ("about", "about_the_site"),
    ("audience", "audience"),
    ("can_say", "what_we_can_say"),
    ("never_say", "what_we_never_say"),
    ("voice", "voice"),
)


class Constitution(BaseModel):
    """The settings section `kernel.writing`. Never saved, it's every default
    rule on and no brief, as a site ships."""

    model_config = ConfigDict(strict=True, extra="forbid")

    #: `defaults`: the default rules, less those switched off, then the added
    #: ones. `own`: `own_text` in their place.
    mode: Literal["defaults", "own"] = "defaults"
    #: The default rules switched off, by id.
    rules_off: list[RuleId] = Field(default_factory=list, max_length=len(DEFAULT_RULES))
    #: The site's own rules after the defaults, one a line.
    added_rules: str = Field(default="", max_length=BOX_MAX)
    #: The site's own text, used in place of the rules in `own` mode.
    own_text: str = Field(default="", max_length=OWN_TEXT_MAX)
    about: str = Field(default="", max_length=BOX_MAX)
    audience: str = Field(default="", max_length=BOX_MAX)
    can_say: str = Field(default="", max_length=BOX_MAX)
    never_say: str = Field(default="", max_length=BOX_MAX)
    voice: str = Field(default="", max_length=BOX_MAX)

    @field_validator("rules_off")
    @classmethod
    def _in_the_catalogues_order(cls, ids: list[RuleId]) -> list[RuleId]:
        """Each once, in the catalogue's order, so a save that only reorders
        changes nothing."""
        chosen = set(ids)
        return [rule.id for rule in DEFAULT_RULES if rule.id in chosen]


_MECHANICS = (
    "This is the writing constitution: it comes before every task. You write for {name}. What you "
    "write is published on its website, under its name.\n\n"
    "Link the site's own pages by their path, such as /about, never with a domain, so every link "
    "works at whatever address the site is served from."
)


def mechanics(site_name: str) -> str:
    """How the site works: who the writing is for, and how a link is written."""
    return _MECHANICS.format(name=site_name.strip() or "this site")


def default_text() -> str:
    """The default rules as the block says them, for a site to start its own text from."""
    return "\n".join(f"- {rule.text}" for rule in DEFAULT_RULES)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _rules(saved: Constitution) -> str:
    """The rules' section's words, or "" for none."""
    if saved.mode == "own":
        return saved.own_text.strip()
    off = set(saved.rules_off)
    chosen = [f"- {rule.text}" for rule in DEFAULT_RULES if rule.id not in off]
    added = [f"- {line}" for line in _lines(saved.added_rules)]
    return "\n".join(chosen + added)


def _brief(saved: Constitution) -> str:
    boxes = []
    for name, tag in BRIEF:
        words = str(getattr(saved, name)).strip()
        if words:
            boxes.append(f"<{tag}>\n{words}\n</{tag}>")
    return "\n".join(boxes)


def block(saved: Constitution, site_name: str) -> str:
    """The first block of every AI task: the mechanics, the rules, then the brief."""
    parts = [mechanics(site_name)]
    rules = _rules(saved)
    if rules:
        parts.append(f"The site's rules for what you write:\n<rules>\n{rules}\n</rules>")
    brief = _brief(saved)
    if brief:
        parts.append(
            "What the site says about itself, for what you write about and how:\n"
            f"<brief>\n{brief}\n</brief>"
        )
    return "\n\n".join(parts)


# --- writing styles ------------------------------------------------------------------

#: What one style may hold, at most, each measured as it is stored.
NAME_MAX = 80
DESCRIPTION_MAX = 200
VOICE_RULES_MAX = 6000
AVOID_PHRASES_MAX = 100
AVOID_PHRASE_MAX = 120
SAMPLES_MAX = 3
SAMPLE_MAX = 8000

#: The most styles a site keeps, so their list (and the Style picker) stays one short read.
STYLES_MAX = 50

#: The Style picker's name for the constitution's own voice, which no style takes.
HOUSE_STYLE = "House style"


@dataclass(frozen=True)
class Style:
    """A style as an AI task reads it: its own fields only, so the same style
    is the same text and a run of tasks in it reads its block from the cache."""

    name: str
    description: str
    voice_rules: str
    avoid: tuple[str, ...]
    samples: tuple[str, ...]


def phrases(text: str) -> list[str]:
    """Phrases to avoid as a style keeps them: one a line, trimmed, without
    blanks or repeats in any case, in the order given."""
    seen: set[str] = set()
    kept: list[str] = []
    for line in _lines(text):
        if line.casefold() not in seen:
            seen.add(line.casefold())
            kept.append(line)
    return kept


def samples_kept(samples: Sequence[str]) -> list[str]:
    """Samples as a style keeps them: trimmed, blank ones dropped, in order."""
    return [sample.strip() for sample in samples if sample.strip()]


def rules_that_fit(text: str) -> str:
    """Voice rules the AI drafted, cut to what a style holds."""
    return text.strip()[:VOICE_RULES_MAX].strip()


def phrases_that_fit(found: Sequence[str]) -> str:
    """Phrases the AI drafted, as a style holds them: one a line, each short
    enough, as many as fit."""
    kept = [phrase for phrase in phrases("\n".join(found)) if len(phrase) <= AVOID_PHRASE_MAX]
    return "\n".join(kept[:AVOID_PHRASES_MAX])


def style_of(row: WritingStyle) -> Style:
    return Style(
        name=row.name,
        description=row.description,
        voice_rules=row.voice_rules,
        avoid=tuple(phrases(row.avoid)),
        samples=tuple(samples_kept(row.samples)),
    )


def view(row: WritingStyle) -> dict[str, Any]:
    """A style as the admin's routes answer it."""
    return {
        "id": str(row.id),
        "version": row.version,
        "name": row.name,
        "description": row.description,
        "voice_rules": row.voice_rules,
        "avoid": row.avoid,
        "samples": list(row.samples),
        "created_by_id": str(row.created_by_id) if row.created_by_id else None,
        "updated_by_id": str(row.updated_by_id) if row.updated_by_id else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def gone() -> Problem:
    return Problem(
        "kernel.writing_style_not_found",
        404,
        "That writing style no longer exists. Choose another.",
    )


def _taken() -> Problem:
    return Problem(
        "kernel.writing_style_name_taken",
        409,
        "Another writing style has that name. Choose another.",
    )


def _invalid(name: str, message: str) -> Problem:
    return Problem(
        "kernel.invalid_request",
        422,
        "Some of what was sent isn't valid.",
        errors={name: [message]},
    )


@dataclass(frozen=True)
class StyleFields:
    """A style's fields as a save sends them, before they're normalised."""

    name: str | None = None
    description: str | None = None
    voice_rules: str | None = None
    avoid: str | None = None
    samples: Sequence[str] | None = None


def _normalised(fields: StyleFields) -> dict[str, Any]:
    """The fields sent, as a style stores them; 422 for what it can't hold."""
    kept: dict[str, Any] = {}
    if fields.name is not None:
        name = " ".join(fields.name.split())
        if not name:
            raise _invalid("name", "A style has a name.")
        if len(name) > NAME_MAX:
            raise _invalid("name", f"At most {NAME_MAX} characters.")
        if name.casefold() == HOUSE_STYLE.casefold():
            raise _invalid("name", f"“{HOUSE_STYLE}” is the writing rules' own voice.")
        kept["name"] = name
    if fields.description is not None:
        description = fields.description.strip()
        if len(description) > DESCRIPTION_MAX:
            raise _invalid("description", f"At most {DESCRIPTION_MAX} characters.")
        kept["description"] = description
    if fields.voice_rules is not None:
        rules = fields.voice_rules.strip()
        if len(rules) > VOICE_RULES_MAX:
            raise _invalid("voice_rules", f"At most {VOICE_RULES_MAX} characters.")
        kept["voice_rules"] = rules
    if fields.avoid is not None:
        found = phrases(fields.avoid)
        if len(found) > AVOID_PHRASES_MAX:
            raise _invalid("avoid", f"At most {AVOID_PHRASES_MAX} phrases.")
        if any(len(phrase) > AVOID_PHRASE_MAX for phrase in found):
            raise _invalid("avoid", f"A phrase is at most {AVOID_PHRASE_MAX} characters.")
        kept["avoid"] = "\n".join(found)
    if fields.samples is not None:
        found = samples_kept(fields.samples)
        if len(found) > SAMPLES_MAX:
            raise _invalid("samples", f"At most {SAMPLES_MAX} samples.")
        if any(len(sample) > SAMPLE_MAX for sample in found):
            raise _invalid("samples", f"A sample is at most {SAMPLE_MAX} characters.")
        kept["samples"] = found
    return kept


async def listed(db: AsyncSession) -> list[WritingStyle]:
    """Every style, by name in any case."""
    rows = await db.scalars(
        select(WritingStyle).order_by(func.lower(WritingStyle.name), WritingStyle.id)
    )
    return list(rows)


async def find(db: AsyncSession, style_id: uuid.UUID) -> WritingStyle | None:
    return await db.get(WritingStyle, style_id, populate_existing=True)


async def chosen(db: AsyncSession, style_id: uuid.UUID | None) -> Style | None:
    """The style an AI task names, or None for the house style; 404 for one gone."""
    if style_id is None:
        return None
    row = await find(db, style_id)
    if row is None:
        raise gone()
    return style_of(row)


async def _name_free(db: AsyncSession, name: str, *, besides: uuid.UUID | None = None) -> None:
    statement = select(WritingStyle.id).where(func.lower(WritingStyle.name) == name.lower())
    if besides is not None:
        statement = statement.where(WritingStyle.id != besides)
    if (await db.scalars(statement)).first() is not None:
        raise _taken()


async def create(db: AsyncSession, fields: StyleFields, *, actor: uuid.UUID) -> WritingStyle:
    """A new style, audited as `kernel.writing_style.created`; 409 for a name
    taken in any case, and 409 `kernel.writing_styles_full` once the site keeps
    `STYLES_MAX`."""
    kept = _normalised(fields)
    if "name" not in kept:
        raise _invalid("name", "A style has a name.")
    if (await db.scalar(select(func.count()).select_from(WritingStyle)) or 0) >= STYLES_MAX:
        raise Problem(
            "kernel.writing_styles_full",
            409,
            f"The site keeps at most {STYLES_MAX} writing styles. Delete one you don't use first.",
        )
    await _name_free(db, kept["name"])
    now = clock.now()
    row = WritingStyle(
        id=uuid.uuid4(),
        version=1,
        name=kept["name"],
        description=kept.get("description", ""),
        voice_rules=kept.get("voice_rules", ""),
        avoid=kept.get("avoid", ""),
        samples=kept.get("samples", []),
        created_by_id=actor,
        updated_by_id=actor,
        created_at=now,
        updated_at=now,
    )
    try:
        async with db.begin_nested():
            db.add(row)
    except IntegrityError:
        raise _taken() from None
    audit.record(
        db, "kernel.writing_style.created", actor=actor, target=("kernel.writing_style", row.id)
    )
    return row


async def change(
    db: AsyncSession, style_id: uuid.UUID, fields: StyleFields, *, version: int, actor: uuid.UUID
) -> WritingStyle:
    """Changes the fields sent, audited as `kernel.writing_style.changed` with
    their names. 404 for a style gone; 409 `kernel.writing_style_changed`
    when someone saved it since `version`; 409 for a name taken."""
    row = await db.get(WritingStyle, style_id, with_for_update=True, populate_existing=True)
    if row is None:
        raise gone()
    if row.version != version:
        raise Problem(
            "kernel.writing_style_changed",
            409,
            "Someone changed this style since you opened it. Open it again to see their changes.",
        )
    kept = _normalised(fields)
    if "name" in kept:
        await _name_free(db, kept["name"], besides=row.id)
    changed = sorted(name for name, value in kept.items() if getattr(row, name) != value)
    if not changed:
        return row
    for name in changed:
        setattr(row, name, kept[name])
    row.version += 1
    row.updated_by_id = actor
    row.updated_at = clock.now()
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise _taken() from None
    audit.record(
        db,
        "kernel.writing_style.changed",
        actor=actor,
        target=("kernel.writing_style", row.id),
        details={"fields": changed},
    )
    return row


async def remove(db: AsyncSession, style_id: uuid.UUID, *, actor: uuid.UUID) -> None:
    """Deletes a style, audited as `kernel.writing_style.deleted`. Nothing else
    points at one (a post doesn't record the style it was written in)."""
    row = await find(db, style_id)
    if row is None:
        raise gone()
    await db.delete(row)
    audit.record(
        db, "kernel.writing_style.deleted", actor=actor, target=("kernel.writing_style", style_id)
    )


__all__ = [
    "AI_TELLS",
    "DEFAULT_RULES",
    "HOUSE_STYLE",
    "SECTION",
    "Constitution",
    "DefaultRule",
    "Style",
    "StyleFields",
    "block",
    "chosen",
    "default_text",
    "mechanics",
]
