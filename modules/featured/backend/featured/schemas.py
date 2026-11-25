"""featured's settings, answers and bodies (`dev plans/contracts/featured.md` §2).
`Settings` is the source of truth for module.json's settings."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from featured.models import KEY_PATTERN, MAX_KEY, MAX_KIND, MAX_KINDS, MAX_LABEL, MAX_TYPE, MAX_URL
from kernel import Answer, Id, When

#: A placement as Players shows it: live now, the soonest to start, later,
#: over, its item not on the site (or its module off), or its item gone.
State = Literal["live", "next", "scheduled", "ended", "hidden", "removed"]
#: The links one paste takes.
MAX_PASTE = 20
#: A type, or "youtube", in what a slot takes; a pasted link.
TypeName = Annotated[str, Field(min_length=1, max_length=MAX_TYPE)]
Pasted = Annotated[str, Field(max_length=MAX_URL)]
#: The words a body may carry where featured checks the length itself, so a
#: title past 200 is `featured.no_title`, not a malformed body.
_ROOM = 1000


class Settings(BaseModel):
    model_config = ConfigDict(strict=True)

    #: Fill a pasted YouTube link's title from YouTube's oEmbed.
    oembed_titles: bool = True


# --- what the site reads ---------------------------------------------------------------------


class Kind(Answer):
    """A kind a slot's links may be: `{key: "music-video", label: "Music video"}`."""

    key: str
    label: str


class RefShown(Answer):
    """Another module's item as the site draws it."""

    type: str
    id: Id
    title: str
    line: str
    image: str | None
    path: str | None


class LinkShown(Answer):
    """A YouTube video: its watch address, its id, its title and its kind's key."""

    url: str
    video_id: str
    title: str
    kind: str | None


class LivePlacement(Answer):
    id: Id
    ref: RefShown | None
    link: LinkShown | None


class LiveSlot(Answer):
    """What a slot holds that's live now, in order, and its kinds' labels."""

    key: str
    label: str
    kinds: list[Kind]
    items: list[LivePlacement]


# --- what Players shows ----------------------------------------------------------------------


class TypeLabel(Answer):
    """A type the modules on give, by its label: `discography.track`, "Tracks"."""

    type: str
    label: str


class ItemKey(Answer):
    type: str
    id: Id


class AdminRef(RefShown):
    #: On the site now.
    live: bool


class AdminPlacement(Answer):
    """A placement with its state. An item's `item` is always there; its `ref`
    is None while its module is off (`hidden`) or once it's gone (`removed`)."""

    id: Id
    item: ItemKey | None
    ref: AdminRef | None
    removed: bool
    link: LinkShown | None
    starts_at: When | None
    ends_at: When | None
    state: State


class SlotCounts(Answer):
    live: int
    #: `next` and `scheduled`.
    scheduled: int


class NowPlaying(Answer):
    """The first thing live: the Dashboard's card and the strip."""

    title: str
    starts_at: When | None
    ends_at: When | None


class AdminSlot(Answer):
    key: str
    label: str
    accepts: list[str]
    kinds: list[Kind]
    on_dashboard: bool
    version: int
    counts: SlotCounts
    now: NowPlaying | None


class AdminSlots(Answer):
    """Every slot in the order they were made, and the types a slot may take."""

    items: list[AdminSlot]
    types: list[TypeLabel]


class FullSlot(AdminSlot):
    """A slot and every placement in it, live, scheduled and ended, in order."""

    items: list[AdminPlacement]


class RefChoices(Answer):
    """A page of the picker: `kernel.refs.pick`'s answer."""

    items: list[AdminRef]
    next_cursor: str | None


class FoundVideo(Answer):
    url: str
    video_id: str
    title: str | None


class RefusedLink(Answer):
    url: str
    #: `featured.not_youtube`.
    reason: str


class PastedLinks(Answer):
    items: list[FoundVideo]
    refused: list[RefusedLink]


# --- bodies ----------------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class RefIn(_Strict):
    type: str = Field(min_length=1, max_length=MAX_TYPE)
    id: str = Field(max_length=36)


class LinkIn(_Strict):
    url: str = Field(min_length=1, max_length=MAX_URL)
    title: str = Field(max_length=_ROOM)
    kind: str | None = Field(default=None, max_length=MAX_KIND)


class PlacementIn(_Strict):
    """One thing in the list: an item or a link. `id` keeps a placement that's
    there; one without is new."""

    id: str | None = Field(default=None, max_length=36)
    ref: RefIn | None = None
    link: LinkIn | None = None
    starts_at: str | None = Field(default=None, max_length=40)
    ends_at: str | None = Field(default=None, max_length=40)


class PlacementsPut(_Strict):
    """The whole list in one save, with the `version` it read."""

    version: int = Field(ge=1)
    items: list[PlacementIn] = Field(max_length=_ROOM)


class KindIn(_Strict):
    key: str = Field(min_length=1, max_length=MAX_KIND, pattern=KEY_PATTERN)
    label: str = Field(min_length=1, max_length=MAX_LABEL)


class NewSlot(_Strict):
    key: str = Field(min_length=1, max_length=MAX_KEY, pattern=KEY_PATTERN)
    label: str = Field(min_length=1, max_length=MAX_LABEL)
    accepts: list[TypeName] = Field(min_length=1, max_length=20)
    kinds: list[KindIn] = Field(default_factory=list, max_length=MAX_KINDS)
    #: Marked by default only for the first slot made.
    on_dashboard: bool | None = None


class SlotChange(_Strict):
    """What a slot's settings change: only the fields sent, with the `version` it read."""

    version: int = Field(ge=1)
    label: str | None = Field(default=None, min_length=1, max_length=MAX_LABEL)
    accepts: list[TypeName] | None = Field(default=None, min_length=1, max_length=20)
    kinds: list[KindIn] | None = Field(default=None, max_length=MAX_KINDS)
    on_dashboard: bool | None = None


class PastedIn(_Strict):
    urls: list[Pasted] = Field(min_length=1, max_length=MAX_PASTE)
