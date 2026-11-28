"""reactions' settings and answers (`dev plans/contracts/reactions.md` §2).

`BUILT_IN` is every reaction the module draws, by key, with its label; the web
draws each with its icon under the same key (`web/icons.tsx`), and a test
holds the two lists equal. `Settings` is the section `reactions`: the palette,
the reactions offered in the row's order, saved through the kernel's settings
route with no screen of its own in 0.1.0 (§8, 5).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from kernel import Answer, Id

#: The reactions the module draws, by key: the three the Post board draws.
BUILT_IN: dict[str, str] = {"fire": "Fire", "love": "Love", "mind_blown": "Mind blown"}

#: The most things one read asks about.
MAX_IDS = 50


class Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    #: The reactions offered, in the row's order: built-in keys, each once.
    palette: list[str] = Field(
        default_factory=lambda: list(BUILT_IN), min_length=1, max_length=len(BUILT_IN)
    )

    @field_validator("palette")
    @classmethod
    def _built_in(cls, keys: list[str]) -> list[str]:
        unknown = [key for key in keys if key not in BUILT_IN]
        if unknown:
            raise ValueError(f"{', '.join(unknown)} isn't a reaction: use {', '.join(BUILT_IN)}.")
        if len(set(keys)) != len(keys):
            raise ValueError("Each reaction may be offered once.")
        return keys


class ReactionChoice(Answer):
    key: str
    #: The words a screen reader says for it: "Mind blown".
    label: str


class Counted(Answer):
    """One thing's reactions."""

    id: Id
    #: Each key in the palette and how many people pressed it, 0 included.
    counts: dict[str, int]
    #: The reader's own, in the palette's order; empty when signed out.
    mine: list[str]


class Reactions(Answer):
    """The palette, and the things asked about that are live now, in the order asked."""

    palette: list[ReactionChoice]
    items: list[Counted]
