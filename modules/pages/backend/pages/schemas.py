"""The pages' answers and bodies (`dev plans/contracts/pages.md` §2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from kernel import Answer, Id, When
from pages.models import (
    ADDRESS_PATTERN,
    MAX_ADDRESS,
    MAX_BODY,
    MAX_SEARCH_DESCRIPTION,
    MAX_SEARCH_TITLE,
    MAX_TITLE,
)

Status = Literal["draft", "scheduled", "published"]


class LivePage(Answer):
    """A live page as the site draws it."""

    title: str
    address: str
    #: The body made HTML on the server and cleaned (kernel.markdown).
    html: str
    #: The words in search results and when shared, each filled in from the
    #: title and the body when the page leaves it empty.
    search_title: str
    search_description: str
    updated_at: When


class Moved(Answer):
    """An address a live page left: where it is now."""

    moved: str


class MenuLink(Answer):
    title: str
    address: str


class Menu(Answer):
    """The live pages in one menu, in order."""

    items: list[MenuLink]


class Listed(Answer):
    """A page in the admin's list."""

    id: Id
    title: str
    address: str
    status: Status
    in_header: bool
    in_footer: bool
    menu_order: int
    #: When a scheduled page goes live.
    publish_at: When | None
    updated_at: When
    #: Who changed it last, by name or address; null once their account is gone.
    updated_by: str | None


class PageList(Answer):
    """Every page, newest edit first: a site's handful of fixed pages, not paged."""

    items: list[Listed]


class Full(Listed):
    """One page as its editor opens it."""

    body: str
    search_title: str | None
    search_description: str | None
    published_at: When | None
    #: Sent back with a save, so two people's changes never cross.
    version: int
    #: The addresses it left while live, each sending visitors on to it.
    moves: list[str]


class Preview(Answer):
    html: str


def _one_line(value: str | None) -> str | None:
    if value is None:
        return None
    if any(ord(each) < 32 or ord(each) == 127 for each in value):
        raise ValueError("One line, with no line breaks.")
    return value.strip()


class _Fields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @field_validator("title", "search_title", "search_description", check_fields=False)
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return _one_line(value)

    @field_validator("title", check_fields=False)
    @classmethod
    def _titled(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("A page needs a title.")
        return value


class NewPage(_Fields):
    title: str = Field(max_length=MAX_TITLE)
    address: str = Field(max_length=MAX_ADDRESS, pattern=ADDRESS_PATTERN)
    body: str = Field(default="", max_length=MAX_BODY)
    search_title: str | None = Field(default=None, max_length=MAX_SEARCH_TITLE)
    search_description: str | None = Field(default=None, max_length=MAX_SEARCH_DESCRIPTION)
    in_header: bool = False
    in_footer: bool = False
    menu_order: int = Field(default=0, ge=0, le=10_000)


class PageChange(_Fields):
    """What a save changes: only the fields it sends, with the `version` it read."""

    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    address: str | None = Field(default=None, max_length=MAX_ADDRESS, pattern=ADDRESS_PATTERN)
    body: str | None = Field(default=None, max_length=MAX_BODY)
    #: Null, or empty, to fall back to the title and the body's opening words.
    search_title: str | None = Field(default=None, max_length=MAX_SEARCH_TITLE)
    search_description: str | None = Field(default=None, max_length=MAX_SEARCH_DESCRIPTION)
    in_header: bool | None = None
    in_footer: bool | None = None
    menu_order: int | None = Field(default=None, ge=0, le=10_000)


class PreviewBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    body: str = Field(max_length=MAX_BODY)


class Publish(BaseModel):
    """Publish now, or at `at`, a time with its zone still to come."""

    model_config = ConfigDict(strict=True, extra="forbid")

    at: str | None = Field(default=None, max_length=40)
