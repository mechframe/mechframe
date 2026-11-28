"""The blog's answers and bodies (`dev plans/contracts/blog.md` §2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blog.models import (
    MAX_BODY,
    MAX_RELATED,
    MAX_SEARCH_DESCRIPTION,
    MAX_SEARCH_TITLE,
    MAX_SLUG,
    MAX_SUMMARY,
    MAX_TITLE,
    SLUG_PATTERN,
)
from kernel import Answer, Id, When

Status = Literal["draft", "scheduled", "published"]

# --- what the site shows ---------------------------------------------------------------------


class PostCover(Answer):
    """The post's cover as a page draws it: the media library's image."""

    id: Id
    url: str
    srcset: str
    width: int
    height: int
    #: Empty for a picture that's only decoration; null while nobody has written any.
    alt: str | None
    decorative: bool


class BlogCategory(Answer):
    slug: str
    label: str


class PostCard(Answer):
    """A live post as a list shows it: never its body."""

    title: str
    slug: str
    summary: str
    cover: PostCover | None
    category: BlogCategory | None
    #: The name its writer goes by on the site; null when they have none, or are gone.
    author: str | None
    published_at: When
    #: How long the body takes to read, in whole minutes, at least 1.
    reading_minutes: int


class PostCards(Answer):
    """A page of live posts, newest first: 12 a page."""

    items: list[PostCard]
    next_cursor: str | None


class RelatedPostLink(Answer):
    title: str
    slug: str


class LivePost(PostCard):
    """A live post as its page draws it."""

    #: Its id, as item references name it (`blog.post`): what reactions' row is given.
    id: Id
    #: The body made HTML on the server and cleaned (kernel.markdown).
    html: str
    updated_at: When
    #: The words in search results and when shared, each filled in from the
    #: title, the summary and the body when the post leaves it empty.
    search_title: str
    search_description: str
    #: The live posts it lists under its body, in its writer's order.
    related: list[RelatedPostLink]
    allow_comments: bool


class PostMoved(Answer):
    """A slug a live post left: where it is now, such as /blog/new-words."""

    moved: str


class BlogCategoryCount(Answer):
    slug: str
    label: str
    #: Its live posts.
    posts: int


class BlogCategoryList(Answer):
    """Every category, in the order staff set, with its live posts."""

    items: list[BlogCategoryCount]


# --- the admin -------------------------------------------------------------------------------


class BlogPerson(Answer):
    id: Id
    #: Their display name, else their address: staff see who it is.
    name: str


class ListedPost(Answer):
    """A post in the admin's list."""

    id: Id
    title: str
    slug: str
    status: Status
    category: BlogCategory | None
    #: Who wrote it; null once their account is gone.
    author: BlogPerson | None
    #: When a scheduled post goes live.
    publish_at: When | None
    #: When it first went live; kept when it's unpublished.
    published_at: When | None
    updated_at: When
    has_cover: bool


class NeedsCover(Answer):
    """The soonest scheduled post with no cover, for the board's note."""

    id: Id
    title: str
    publish_at: When


class PostList(Answer):
    """A page of posts, newest edit first: 50 a page."""

    items: list[ListedPost]
    next_cursor: str | None
    needs_cover: NeedsCover | None


class RelatedPost(Answer):
    id: Id
    title: str
    slug: str


class FullPost(ListedPost):
    """One post as its editor opens it."""

    summary: str
    body: str
    cover_id: Id | None
    cover: PostCover | None
    search_title: str | None
    search_description: str | None
    allow_comments: bool
    post_to_community: bool
    email_subscribers: bool
    #: Sent back with a save, so two people's changes never cross.
    version: int
    #: The slugs it left while live, each sending visitors on to it.
    moves: list[str]
    #: The live posts it lists, in order: one unpublished since isn't here.
    related: list[RelatedPost]


class PostPreview(Answer):
    html: str


class BlogAdminCategory(Answer):
    id: Id
    slug: str
    label: str
    position: int
    #: Its posts, drafts and scheduled ones included.
    posts: int


class BlogAdminCategoryList(Answer):
    items: list[BlogAdminCategory]


class BlogAuthorList(Answer):
    """Who a post may name as its author: every active account that may write posts."""

    items: list[BlogPerson]


# --- bodies ----------------------------------------------------------------------------------

#: What breaks a line besides a control character: NEL and the line and
#: paragraph separators, which str.splitlines() reads as line ends.
_BREAKS = frozenset(chr(code) for code in (0x85, 0x2028, 0x2029))


def _one_line(value: str | None) -> str | None:
    if value is None:
        return None
    if any(ord(each) < 32 or ord(each) == 127 or each in _BREAKS for each in value):
        raise ValueError("One line, with no line breaks.")
    return value.strip()


class _PostFields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @field_validator("title", "summary", "search_title", "search_description", check_fields=False)
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return _one_line(value)

    @field_validator("title", check_fields=False)
    @classmethod
    def _titled(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("A post needs a title.")
        return value

    @field_validator("body", check_fields=False)
    @classmethod
    def _storable(cls, value: str | None) -> str | None:
        # Postgres's text holds no NUL: refused here, a field's error, not at the flush.
        if value is not None and chr(0) in value:
            raise ValueError("A post's words can't hold a NUL character.")
        return value


class NewPost(_PostFields):
    title: str = Field(max_length=MAX_TITLE)
    #: Left out, it's made from the title, with a number when another post has it.
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    summary: str = Field(default="", max_length=MAX_SUMMARY)
    body: str = Field(default="", max_length=MAX_BODY)
    #: The media library's image id.
    cover_id: str | None = Field(default=None, max_length=36)
    #: A `blog_category` term's slug.
    category: str | None = Field(default=None, max_length=80)
    #: Left out, whoever writes it.
    author_id: str | None = Field(default=None, max_length=36)
    search_title: str | None = Field(default=None, max_length=MAX_SEARCH_TITLE)
    search_description: str | None = Field(default=None, max_length=MAX_SEARCH_DESCRIPTION)
    allow_comments: bool = True
    post_to_community: bool = False
    email_subscribers: bool = False
    #: Live posts' ids, in the order shown.
    related: list[str] = Field(default_factory=list, max_length=MAX_RELATED)


class PostChange(_PostFields):
    """What a save changes: only the fields it sends, with the `version` it read.
    `cover_id`, `category` and `author_id` sent as null clear them."""

    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    summary: str | None = Field(default=None, max_length=MAX_SUMMARY)
    body: str | None = Field(default=None, max_length=MAX_BODY)
    cover_id: str | None = Field(default=None, max_length=36)
    category: str | None = Field(default=None, max_length=80)
    author_id: str | None = Field(default=None, max_length=36)
    #: Null, or empty, to fall back to the title, the summary and the body.
    search_title: str | None = Field(default=None, max_length=MAX_SEARCH_TITLE)
    search_description: str | None = Field(default=None, max_length=MAX_SEARCH_DESCRIPTION)
    allow_comments: bool | None = None
    post_to_community: bool | None = None
    email_subscribers: bool | None = None
    related: list[str] | None = Field(default=None, max_length=MAX_RELATED)


class PostPreviewBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    body: str = Field(max_length=MAX_BODY)


class PublishPost(BaseModel):
    """PublishPost now, or at `at`, a time with its zone still to come."""

    model_config = ConfigDict(strict=True, extra="forbid")

    at: str | None = Field(default=None, max_length=40)


# --- generated covers (decision 0065, `dev plans/contracts/blog-covers.md` §2) ----------------

#: A colour as the editor reads it from the theme.
HEX_COLOUR = r"^#[0-9a-fA-F]{6}$"
#: The most a drawing sent back holds: the kernel's SVG limit, 100 KB.
MAX_DRAWING = 100_000


class CoverColours(BaseModel):
    """The site's colours, from the theme's surface, text and accent tokens."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ground: str = Field(pattern=HEX_COLOUR)
    ink: str = Field(pattern=HEX_COLOUR)
    accent: str = Field(pattern=HEX_COLOUR)


class CoverAsk(BaseModel):
    """What to draw: the editor's fields as they stand, so a post not yet
    saved can have a cover; for a revision, the cover shown and the changes."""

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str = Field(default="", max_length=MAX_TITLE)
    summary: str = Field(default="", max_length=MAX_SUMMARY)
    body: str = Field(default="", max_length=MAX_BODY)
    style: Literal["editorial", "signal", "minimal", "custom"]
    #: What to draw, for Custom.
    description: str = Field(default="", max_length=600)
    #: The site's colours: always for the house styles; for Custom only "In the site's colours".
    colours: CoverColours | None = None
    #: The site's name in the top-left corner.
    wordmark: bool = False
    #: The cover shown, to change.
    current: str | None = Field(default=None, max_length=MAX_DRAWING)
    #: What to change in it.
    changes: str = Field(default="", max_length=600)


class CoverDrawn(Answer):
    """A cover drawn and cleaned: the SVG to keep or change, its alt text, and
    its preview, the kernel's own render of it as the PNG kept will be."""

    svg: str
    alt: str
    #: A `data:image/png;base64,` address at the card's size, drawn with the
    #: kernel's Inter: a browser draws an SVG's words in its own fonts (Codex on #147).
    preview: str


class CoverUse(BaseModel):
    """The cover shown, to keep with its alt text: cleaned again on the server."""

    model_config = ConfigDict(strict=True, extra="forbid")

    svg: str = Field(min_length=1, max_length=MAX_DRAWING)
    alt: str = Field(default="", max_length=250)


class CoverStored(Answer):
    """The cover kept in the media library, as the post's Cover field holds it."""

    cover: PostCover


class CoverState(Answer):
    """Whether a drawn cover could be kept now: media's storage is on."""

    storage: bool
