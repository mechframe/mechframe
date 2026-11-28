"""portfolio's answers, bodies and settings (`dev plans/contracts/portfolio.md` §2).
`Settings` is the source of truth for module.json's settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from kernel import Answer, Id, When
from portfolio.models import MAX_ABOUT, MAX_SLUG, MAX_TITLE, MAX_VIDEO_URL, SLUG_PATTERN

Status = Literal["draft", "scheduled", "published"]

#: The most a commission link may hold.
MAX_LINK = 500
MAX_LEAD = 300

#: What breaks a line besides a control character: NEL and the line and
#: paragraph separators, which str.splitlines() reads as line ends.
_BREAKS = frozenset(chr(code) for code in (0x85, 0x2028, 0x2029))


def one_line(value: str) -> str:
    """`value` on one line, stripped: a control character or a line break is refused."""
    if any(ord(each) < 32 or ord(each) == 127 or each in _BREAKS for each in value):
        raise ValueError("One line, with no line breaks.")
    return value.strip()


def words(value: str) -> str:
    """A few words about a piece: its line breaks kept as \\n, any other
    control character refused, and the ends stripped."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    for each in _BREAKS:
        value = value.replace(each, "\n")
    if any((ord(each) < 32 and each not in "\n\t") or ord(each) == 127 for each in value):
        raise ValueError("Words, with no control characters.")
    return value.strip()


def link(value: str) -> str:
    """A commission link: empty, a path on the site such as /contact, or an https address."""
    value = one_line(value)
    if not value:
        return value
    if value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    if value.lower().startswith("https://") and len(value) > len("https://"):
        return value
    raise ValueError("A path on the site, such as /contact, or an address starting https://.")


class Settings(BaseModel):
    model_config = ConfigDict(strict=True)

    #: Pieces on each page of the Art page.
    pieces_per_page: int = Field(default=24, ge=6, le=60)
    #: The line under the Art page's title.
    lead: str = Field(default="", max_length=MAX_LEAD)
    #: Where "Commission work like this" goes; empty hides it.
    commission_link: str = Field(default="", max_length=MAX_LINK)

    @field_validator("lead")
    @classmethod
    def _lead(cls, value: str) -> str:
        return one_line(value)

    @field_validator("commission_link")
    @classmethod
    def _link(cls, value: str) -> str:
        return link(value)


# --- what the site shows ---------------------------------------------------------------------


class PiecePicture(Answer):
    """A piece's picture as a page draws it: the media library's image."""

    id: Id
    url: str
    srcset: str
    width: int
    height: int
    #: Empty for a picture that's only decoration; null while nobody has written any.
    alt: str | None
    decorative: bool


class Discipline(Answer):
    slug: str
    label: str


class PieceVideo(Answer):
    """A piece's YouTube video: its watch address and its id."""

    url: str
    video_id: str


class PieceCard(Answer):
    """A live piece as a grid shows it: never its words."""

    id: Id
    title: str
    slug: str
    #: Null when the discipline it had was deleted.
    discipline: Discipline | None
    #: The name its artist goes by on the site; null when they have none, or none is credited.
    artist: str | None
    year: int | None
    #: Null only when the media library lost the image.
    picture: PiecePicture | None
    #: Whether its page plays a video.
    has_video: bool
    #: Its page on the site: /art/piece/<slug>.
    path: str


class PieceCards(Answer):
    """A page of live pieces, newest first."""

    items: list[PieceCard]
    next_cursor: str | None


class LivePiece(PieceCard):
    """A live piece as its page draws it."""

    about: str
    video: PieceVideo | None


class ArtPage(Answer):
    """What the Art page says besides its pieces: the settings' lead and commission link."""

    #: The line under the title; empty for none.
    lead: str
    #: Where "Commission work like this" goes; empty hides it.
    commission_link: str


class DisciplineList(Answer):
    """The disciplines with a live piece, in staff's order."""

    items: list[Discipline]


# --- the admin -------------------------------------------------------------------------------


class PortfolioPerson(Answer):
    id: Id
    #: Their display name, else their address: staff see who it is.
    name: str


class AdminPiece(Answer):
    """A piece as the admin's grid and editor show it."""

    id: Id
    title: str
    slug: str
    discipline: Discipline | None
    #: Who it's credited to; null for no one, or once their account is gone.
    artist: PortfolioPerson | None
    year: int | None
    about: str
    image_id: Id
    picture: PiecePicture | None
    video: PieceVideo | None
    status: Status
    #: When a scheduled piece goes live.
    publish_at: When | None
    #: When it first went live; kept when it's unpublished.
    published_at: When | None
    #: Sent back with a save, so two people's changes never cross.
    version: int
    updated_at: When
    #: Its page on the site while it's live, else null.
    path: str | None


class AdminPieceList(Answer):
    """A page of pieces, newest edit first: every piece for `portfolio.piece.manage`,
    else the ones credited to you."""

    items: list[AdminPiece]
    next_cursor: str | None
    #: The pieces credited to no one, for the page's note; null without `manage`.
    no_artist: int | None


class ArtistList(Answer):
    """Who a piece may be credited to: every active account that may add pieces."""

    items: list[PortfolioPerson]


class AdminDiscipline(Answer):
    id: Id
    slug: str
    label: str
    position: int
    #: Its pieces, drafts and scheduled ones included.
    pieces: int


class AdminDisciplineList(Answer):
    items: list[AdminDiscipline]


# --- bodies ----------------------------------------------------------------------------------


class _PieceFields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @field_validator("title", check_fields=False)
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = one_line(value)
        if not value:
            raise ValueError("A piece needs a title.")
        return value

    @field_validator("about", check_fields=False)
    @classmethod
    def _about(cls, value: str | None) -> str | None:
        return None if value is None else words(value)

    @field_validator("video_url", check_fields=False)
    @classmethod
    def _video(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return one_line(value) or None


class NewPiece(_PieceFields):
    title: str = Field(max_length=MAX_TITLE)
    #: A `portfolio_discipline` term's slug.
    discipline: str = Field(max_length=80)
    #: The media library's image id.
    image_id: str = Field(max_length=36)
    #: Left out, it's made from the title, with a number when another piece has it.
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    #: Left out, whoever adds it; null, no one (`portfolio.piece.manage` only).
    artist_id: str | None = Field(default=None, max_length=36)
    year: int | None = None
    about: str = Field(default="", max_length=MAX_ABOUT)
    #: A YouTube video's address.
    video_url: str | None = Field(default=None, max_length=MAX_VIDEO_URL)


class PieceChange(_PieceFields):
    """What a save changes: only the fields it sends, with the `version` it read.
    `artist_id`, `year` and `video_url` sent as null clear them; the others,
    sent as null, are left as they are."""

    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    discipline: str | None = Field(default=None, max_length=80)
    image_id: str | None = Field(default=None, max_length=36)
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    artist_id: str | None = Field(default=None, max_length=36)
    year: int | None = None
    about: str | None = Field(default=None, max_length=MAX_ABOUT)
    video_url: str | None = Field(default=None, max_length=MAX_VIDEO_URL)


class PublishPiece(BaseModel):
    """Publish now, or at `at`, a time with its zone still to come."""

    model_config = ConfigDict(strict=True, extra="forbid")

    at: str | None = Field(default=None, max_length=40)
