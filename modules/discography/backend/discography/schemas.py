"""discography's settings, answers and bodies (`dev plans/contracts/discography.md` §2).
`Settings` is the source of truth for module.json's settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from discography.models import (
    MAX_ARTIST,
    MAX_CREDITS,
    MAX_LINE,
    MAX_LINKS,
    MAX_LYRICS,
    MAX_NAME,
    MAX_ROLE,
    MAX_ROLES,
    MAX_SLUG,
    MAX_TITLE,
    MAX_TRACKS,
    MAX_URL,
    SLUG_PATTERN,
)
from kernel import Answer, Id, When

Kind = Literal["album", "ep", "single"]
Status = Literal["draft", "scheduled", "published"]
Profile = Literal["unlinked", "collective", "member", "not_member"]
AudioState = Literal["none", "processing", "ready", "failed"]
PlaysFrom = Literal["upload", "soundcloud"]
Platform = Literal[
    "spotify",
    "apple-music",
    "youtube",
    "youtube-music",
    "amazon-music",
    "soundcloud",
    "bandcamp",
    "tidal",
    "deezer",
]


class Settings(BaseModel):
    model_config = ConfigDict(strict=True)

    #: The stream file's constant bitrate, taken to MP3's nearest standard rate.
    stream_bitrate_kbps: int = Field(default=256, ge=128, le=320)
    #: The Parental Advisory label on explicit releases and tracks.
    show_explicit_badge: bool = True
    #: Lyrics on a track's page, for tracks that have them.
    show_lyrics: bool = True


# --- what the site shows ---------------------------------------------------------------------


class MusicCover(Answer):
    """A cover as a page draws it: the media library's image."""

    id: Id
    url: str
    srcset: str
    width: int
    height: int
    alt: str | None
    decorative: bool


class MusicCredit(Answer):
    role: str
    name: str


class MusicLink(Answer):
    platform: Platform
    #: The platform's name: "Apple Music".
    label: str
    url: str


class ReleaseCard(Answer):
    """A live release as a list shows it."""

    title: str
    slug: str
    kind: Kind
    year: int | None
    artist_line: str
    credit_line: str
    summary: str
    cover: MusicCover | None
    #: Any of its tracks is explicit, while the site shows the label.
    explicit: bool
    #: Its tracks that play.
    track_count: int
    tracklist_to_come: bool
    #: Its page: /music/<slug>.
    path: str
    published_at: When


class ReleaseCards(Answer):
    items: list[ReleaseCard]
    next_cursor: str | None


class TrackLine(Answer):
    """A track as a release's tracklist shows it: only tracks that play."""

    title: str
    slug: str
    #: Its place on the release, from 1.
    number: int
    duration_ms: int | None
    explicit: bool
    #: The stream file once it's made; else the SoundCloud link.
    plays_from: PlaysFrom
    stream_url: str | None
    soundcloud_url: str | None
    soundcloud_kind: Literal["track", "set"] | None
    has_lyrics: bool
    path: str


class LiveRelease(ReleaseCard):
    """A live release as its page draws it."""

    back_cover: MusicCover | None
    tracks: list[TrackLine]
    credits: list[MusicCredit]
    links: list[MusicLink]
    updated_at: When


class ReleaseOfTrack(Answer):
    title: str
    slug: str
    kind: Kind
    path: str


class LiveTrack(TrackLine):
    """A track as its own page draws it."""

    release: ReleaseOfTrack
    artist_line: str
    cover: MusicCover | None
    #: 1,000 integers from 0 to 255, for a stream file; null for a link.
    peaks: list[int] | None
    #: Null while the site doesn't show lyrics, or the track has none.
    lyrics: str | None
    credits: list[MusicCredit]


class MusicMoved(Answer):
    """An address a live release or track left: where it is now."""

    moved: str


class ArtistLinks(Answer):
    """The artist's own links: "Listen everywhere"."""

    items: list[MusicLink]


# --- the admin -------------------------------------------------------------------------------


class AdminCredit(Answer):
    role_id: Id
    role: str
    person_id: Id
    name: str
    profile: Profile


class AdminLink(Answer):
    platform: Platform
    label: str
    url: str


class TrackAudio(Answer):
    """Where a track's sound is, and what it can do now."""

    state: AudioState
    #: What plays: the stream file, else the link; null when nothing does.
    plays_from: PlaysFrom | None
    percent: int | None
    #: Why the last processing failed: a problem code, with words for it.
    error: str | None
    error_words: str | None
    master_name: str | None
    master_bytes: int | None
    soundcloud_url: str | None
    soundcloud_kind: Literal["track", "set"] | None
    duration_ms: int | None
    #: The stream file, for staff to hear even before release day.
    stream_url: str | None


class AdminTrack(Answer):
    id: Id
    version: int
    release_id: Id
    release_title: str
    number: int
    title: str
    slug: str
    explicit: bool
    audio: TrackAudio
    has_lyrics: bool
    credit_count: int


class AdminTrackList(Answer):
    items: list[AdminTrack]
    next_cursor: str | None
    #: Every track, and on how many releases, for the board's footer.
    total: int
    releases: int


class FullTrack(AdminTrack):
    lyrics: str | None
    credits: list[AdminCredit]
    peaks: list[int] | None
    #: The release's page, where the track shows once it's live.
    path: str


class AdminRelease(Answer):
    """A release in the admin's list, with what needs doing."""

    id: Id
    version: int
    title: str
    slug: str
    kind: Kind
    year: int | None
    artist_line: str
    cover: MusicCover | None
    status: Status
    publish_at: When | None
    published_at: When | None
    track_count: int
    #: Its tracks that can't play: hidden from the site.
    unplayable: int
    tracklist_to_come: bool
    updated_at: When


class AdminReleaseList(Answer):
    items: list[AdminRelease]


class FullRelease(AdminRelease):
    credit_line: str
    summary: str
    back_cover: MusicCover | None
    tracks: list[AdminTrack]
    credits: list[AdminCredit]
    links: list[AdminLink]
    #: The addresses it left, which send visitors on.
    moves: list[str]
    path: str


class AdminPerson(Answer):
    id: Id
    version: int
    name: str
    profile: Profile
    roster_profile_id: Id | None
    #: "Artist and producer, Unified Vibration; featured on Catalyst".
    credited_for: str
    credits: int


class AdminPersonList(Answer):
    items: list[AdminPerson]
    #: Names not linked yet: the board's note.
    unlinked: int


class AdminRole(Answer):
    id: Id
    name: str
    credits: int


class AdminRoleList(Answer):
    items: list[AdminRole]


class AdminArtistLinks(Answer):
    items: list[AdminLink]


# --- bodies ----------------------------------------------------------------------------------

_BREAKS = frozenset(chr(code) for code in (0x85, 0x2028, 0x2029))


def _one_line(value: str | None) -> str | None:
    if value is None:
        return None
    if any(ord(each) < 32 or ord(each) == 127 or each in _BREAKS for each in value):
        raise ValueError("One line, with no line breaks.")
    return value.strip()


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class CreditIn(_Strict):
    role_id: str = Field(max_length=36)
    name: str = Field(min_length=1, max_length=MAX_NAME)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        line = _one_line(value) or ""
        if not line:
            raise ValueError("A credit names someone.")
        return line


class _ReleaseFields(_Strict):
    @field_validator("title", "artist_line", "credit_line", "summary", check_fields=False)
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return _one_line(value)

    @field_validator("title", check_fields=False)
    @classmethod
    def _titled(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("A release needs a title.")
        return value


class NewRelease(_ReleaseFields):
    title: str = Field(max_length=MAX_TITLE)
    kind: Kind = "album"
    #: Left out, it's made from the title, with a number when another release has it.
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    year: int | None = Field(default=None, ge=1900, le=2100)
    artist_line: str = Field(default="", max_length=MAX_ARTIST)
    credit_line: str = Field(default="", max_length=MAX_LINE)
    summary: str = Field(default="", max_length=MAX_LINE)
    cover_id: str | None = Field(default=None, max_length=36)
    back_cover_id: str | None = Field(default=None, max_length=36)
    tracklist_to_come: bool = False


class ReleaseChange(_ReleaseFields):
    """What a save changes: only the fields it sends, with the `version` it read.
    `year`, `cover_id` and `back_cover_id` sent as null clear them. `credits`,
    `links` and `track_ids` replace the whole list."""

    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    kind: Kind | None = None
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    year: int | None = Field(default=None, ge=1900, le=2100)
    artist_line: str | None = Field(default=None, max_length=MAX_ARTIST)
    credit_line: str | None = Field(default=None, max_length=MAX_LINE)
    summary: str | None = Field(default=None, max_length=MAX_LINE)
    cover_id: str | None = Field(default=None, max_length=36)
    back_cover_id: str | None = Field(default=None, max_length=36)
    tracklist_to_come: bool | None = None
    credits: list[CreditIn] | None = Field(default=None, max_length=MAX_CREDITS)
    links: list[str] | None = Field(default=None, max_length=MAX_LINKS)
    #: Every track's id, in the order they play.
    track_ids: list[str] | None = Field(default=None, max_length=MAX_TRACKS)


class PublishRelease(_Strict):
    """Live now, or at `at`, a time with its zone still to come."""

    at: str | None = Field(default=None, max_length=40)


class NewTrack(_Strict):
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    soundcloud_url: str | None = Field(default=None, max_length=MAX_URL)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        line = _one_line(value) or ""
        if not line:
            raise ValueError("A track needs a title.")
        return line


class TrackChange(_Strict):
    """What a save changes, with the `version` it read. `soundcloud_url`,
    `lyrics` and `duration_ms` sent as null clear them; `duration_ms` is for a
    track that plays from its link alone."""

    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    slug: str | None = Field(default=None, max_length=MAX_SLUG, pattern=SLUG_PATTERN)
    explicit: bool | None = None
    lyrics: str | None = Field(default=None, max_length=MAX_LYRICS)
    soundcloud_url: str | None = Field(default=None, max_length=MAX_URL)
    duration_ms: int | None = Field(default=None, ge=0, le=6 * 60 * 60 * 1000)
    credits: list[CreditIn] | None = Field(default=None, max_length=MAX_CREDITS)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        line = _one_line(value)
        if value is not None and not line:
            raise ValueError("A track needs a title.")
        return line

    @field_validator("lyrics")
    @classmethod
    def _lyrics(cls, value: str | None) -> str | None:
        if value is not None and chr(0) in value:
            raise ValueError("Lyrics can't hold a NUL character.")
        return value


class PersonChange(_Strict):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    #: `member` waits for roster (step 3), which sets the profile it links to.
    profile: Literal["unlinked", "collective", "not_member"] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        line = _one_line(value)
        if value is not None and not line:
            raise ValueError("A name can't be empty.")
        return line


class RoleIn(_Strict):
    #: A role there now; left out, a new one.
    id: str | None = Field(default=None, max_length=36)
    name: str = Field(min_length=1, max_length=MAX_ROLE)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        line = _one_line(value) or ""
        if not line:
            raise ValueError("A role needs a name.")
        return line


class RolesPut(_Strict):
    """The whole list, in order: a role left out goes, unless a credit names it."""

    items: list[RoleIn] = Field(min_length=1, max_length=MAX_ROLES)


class LinksPut(_Strict):
    links: list[str] = Field(max_length=MAX_LINKS)
