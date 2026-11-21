"""The media library's answers and bodies (`dev plans/contracts/media.md` §2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kernel import Answer, Id, When
from media.models import MAX_ALT


class Use(Answer):
    """Where a module placed the image: its name for people, and a link to it."""

    label: str
    link: str


class Image(Answer):
    id: Id
    #: The file at its full size, in the public bucket.
    url: str
    #: Each smaller copy, then the file itself, for an `<img srcset>`.
    srcset: str
    width: int
    height: int
    bytes: int
    content_type: str
    filename: str
    alt: str | None
    decorative: bool
    #: Who uploaded it, by name or address; null once their account is gone.
    uploaded_by: str | None
    created_at: When
    #: Sent back with a change to the alt text, so two people's changes never cross.
    version: int
    #: Where it's placed, on the one-image read only.
    uses: list[Use] | None = None


class ImagePage(Answer):
    items: list[Image]
    next_cursor: str | None
    #: How many images in the whole library have no alt text and aren't decoration.
    missing_alt: int


class ImageChange(BaseModel):
    """A change to what an image means: its alt text, or that it's only decoration."""

    model_config = ConfigDict(strict=True, extra="forbid")

    version: int = Field(ge=1)
    alt: str | None = Field(default=None, max_length=MAX_ALT)
    decorative: bool = False
