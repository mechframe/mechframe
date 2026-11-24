"""discography's tables (`dev plans/contracts/discography.md` §3).

`discography_release` is an album, an EP or a single: its title, its address
under /music (its slug), its lines, its front and back covers (media's image
ids, no foreign key across modules), drafted, scheduled and published through
the kernel's lifecycle. `discography_track` is one track on one release, in
order, playing from its stream file once a job has made it from the uploaded
master, else from its SoundCloud link, else not at all.

`discography_person` is a name credited anywhere, once; `discography_role` is
the list of roles a credit names (Artist, Featuring, Produced by and the
rest), which whoever manages releases edits; `discography_credit` is a person
in a role on a release or on a track. `discography_link` is a release's
streaming link, or the artist's own when it names no release.
`discography_move` is an address a live release or track left: it sends
visitors on, wherever the release is now, so a move never chains.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base, lifecycle

#: A slug: lowercase letters and digits, single hyphens between them.
SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_SLUG = 80
MAX_TITLE = 200
MAX_ARTIST = 200
#: The credit line and the summary: one line each.
MAX_LINE = 300
MAX_LYRICS = 20_000
MAX_URL = 500
MAX_NAME = 120
MAX_ROLE = 60
MAX_FILENAME = 150
#: An old address: `<release>` or `<release>/<track>`.
MAX_PATH = MAX_SLUG * 2 + 1
#: The waveform's slices.
PEAKS = 1000
#: The most tracks a release holds, credits a release or track names, and
#: links a release lists.
MAX_TRACKS = 100
MAX_CREDITS = 60
MAX_LINKS = 12
MAX_ROLES = 40

KINDS = ("album", "ep", "single")
PROFILES = ("unlinked", "collective", "member", "not_member")
AUDIO_STATES = ("none", "processing", "ready", "failed")
SOUNDCLOUD_KINDS = ("track", "set")
#: The platforms a streaming link may be on, in the order a page lists them.
PLATFORMS = (
    "spotify",
    "apple-music",
    "youtube",
    "youtube-music",
    "amazon-music",
    "soundcloud",
    "bandcamp",
    "tidal",
    "deezer",
)


def slug_rule(column: str) -> str:
    return f"{column} ~ '{SLUG_PATTERN}'"


def one_of(column: str, values: tuple[str, ...]) -> str:
    listed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({listed})"


class Release(lifecycle.Publishable, Base):
    __tablename__ = "discography_release"
    __content_type__ = "discography.release"
    __table_args__ = (
        CheckConstraint(slug_rule("slug"), name="slug_rule"),
        CheckConstraint("btrim(title) <> ''", name="titled"),
        CheckConstraint(one_of("kind", KINDS), name="kind_known"),
        CheckConstraint("year IS NULL OR (year >= 1900 AND year <= 2100)", name="year_range"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_discography_release_updated_at", "updated_at"),
        Index("ix_discography_release_published_at", "published_at"),
        *lifecycle.table_args("discography_release"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: The row's edits: one more on each save, sent back with the next so two never cross.
    version: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(10), default="album")
    title: Mapped[str] = mapped_column(String(MAX_TITLE))
    #: Where the site shows it: /music/<slug>.
    slug: Mapped[str] = mapped_column(String(MAX_SLUG), unique=True)
    year: Mapped[int | None] = mapped_column(SmallInteger)
    #: Who it's by, as a page names them: "petro and J Tone, featuring Vibrant Mindz".
    artist_line: Mapped[str] = mapped_column(String(MAX_ARTIST), default="", server_default="")
    #: "Produced by Vibrant Mindz."
    credit_line: Mapped[str] = mapped_column(String(MAX_LINE), default="", server_default="")
    #: One line for its card and for sharing: "On CD and most streaming platforms."
    summary: Mapped[str] = mapped_column(String(MAX_LINE), default="", server_default="")
    #: The media library's images (`media.public`).
    cover_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    back_cover_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    #: "Tracklist to come": its tracks so far stand in for the rest.
    tracklist_to_come: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: When `discography.release.published` went out: once a release, on its first publish.
    announced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Track(Base):
    __tablename__ = "discography_track"
    __table_args__ = (
        CheckConstraint(slug_rule("slug"), name="slug_rule"),
        CheckConstraint("btrim(title) <> ''", name="titled"),
        CheckConstraint("position >= 0", name="position_positive"),
        CheckConstraint(one_of("audio_state", AUDIO_STATES), name="audio_state_known"),
        CheckConstraint(
            f"soundcloud_kind IS NULL OR {one_of('soundcloud_kind', SOUNDCLOUD_KINDS)}",
            name="soundcloud_kind_known",
        ),
        CheckConstraint(
            "(soundcloud_url IS NULL) = (soundcloud_kind IS NULL)", name="soundcloud_paired"
        ),
        CheckConstraint(
            "processing_percent IS NULL OR (processing_percent >= 0 AND processing_percent <= 100)",
            name="percent_range",
        ),
        CheckConstraint(f"char_length(lyrics) <= {MAX_LYRICS}", name="lyrics_length"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="duration_positive"),
        CheckConstraint("version >= 1", name="version_positive"),
        UniqueConstraint(
            "release_id", "position", name="uq_discography_track_position", deferrable=True
        ),
        UniqueConstraint("release_id", "slug", name="uq_discography_track_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, default=1)
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_release.id", ondelete="CASCADE")
    )
    #: Its place on the release, from 0.
    position: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str] = mapped_column(String(MAX_TITLE))
    #: Where the site shows it: /music/<release>/<slug>.
    slug: Mapped[str] = mapped_column(String(MAX_SLUG))
    explicit: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    lyrics: Mapped[str | None] = mapped_column(Text)
    #: The link in its plain form, and whether it's a track or a playlist.
    soundcloud_url: Mapped[str | None] = mapped_column(String(MAX_URL))
    soundcloud_kind: Mapped[str | None] = mapped_column(String(10))
    #: The uploaded master, in the private bucket; its name a label only.
    master_key: Mapped[str | None] = mapped_column(String(512))
    master_name: Mapped[str | None] = mapped_column(String(MAX_FILENAME))
    master_bytes: Mapped[int | None] = mapped_column(BigInteger)
    #: The MP3 a job made from it, in the public bucket under an unguessable name.
    stream_key: Mapped[str | None] = mapped_column(String(512))
    #: From the stream file once it's made; typed by staff for a link alone.
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    #: 1,000 integers from 0 to 255: the loudest sample in each slice.
    peaks: Mapped[list[int] | None] = mapped_column(JSONB)
    audio_state: Mapped[str] = mapped_column(String(12), default="none", server_default="none")
    processing_percent: Mapped[int | None] = mapped_column(SmallInteger)
    #: Why the last processing failed: a problem code.
    audio_error: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Person(Base):
    """A name credited anywhere, once. `profile` says what it is to the site:
    not linked yet, the collective itself, a member (with roster's profile id,
    from step 3), or not a member (which stops the Credits board asking)."""

    __tablename__ = "discography_person"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="named"),
        CheckConstraint(one_of("profile", PROFILES), name="profile_known"),
        CheckConstraint(
            "(roster_profile_id IS NOT NULL) = (profile = 'member')", name="member_linked"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("uq_discography_person_name", text("lower(name::text)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(MAX_NAME))
    profile: Mapped[str] = mapped_column(String(12), default="unlinked", server_default="unlinked")
    roster_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Role(Base):
    __tablename__ = "discography_role"
    __table_args__ = (CheckConstraint("btrim(name) <> ''", name="named"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(MAX_ROLE), unique=True)
    position: Mapped[int] = mapped_column(SmallInteger)


class Credit(Base):
    """A person in a role, on a release or on one of its tracks, at `position`."""

    __tablename__ = "discography_credit"
    __table_args__ = (
        CheckConstraint("(release_id IS NULL) <> (track_id IS NULL)", name="on_one"),
        CheckConstraint("position >= 0", name="position_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_person.id", ondelete="RESTRICT"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_role.id", ondelete="RESTRICT"), index=True
    )
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_release.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_track.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)


class Link(Base):
    """A streaming link: a release's, or the artist's own when `release_id` is null."""

    __tablename__ = "discography_link"
    __table_args__ = (
        CheckConstraint(one_of("platform", PLATFORMS), name="platform_known"),
        CheckConstraint("position >= 0", name="position_positive"),
        UniqueConstraint(
            "release_id",
            "platform",
            name="uq_discography_link_platform",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_release.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(String(MAX_URL))
    position: Mapped[int] = mapped_column(SmallInteger)


class Move(Base):
    """An address a live release or track left: `<release>` or `<release>/<track>`,
    sending visitors on (a 301). A live one at the same address wins."""

    __tablename__ = "discography_move"

    old_path: Mapped[str] = mapped_column(String(MAX_PATH), primary_key=True)
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_release.id", ondelete="CASCADE"), index=True
    )
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discography_track.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
