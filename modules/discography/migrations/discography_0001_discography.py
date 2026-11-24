"""discography (`dev plans/contracts/discography.md` §3): releases with the
kernel's lifecycle columns, their tracks, the people and roles credits name,
the credits themselves, streaming links and the addresses live releases left.
Its search documents and covers' uses live in the kernel's tables and
media's, so this depends on them.

Admins and editors are granted `discography.release.manage`, admins
`discography.settings.manage`; an owner holds every permission. The five
roles a site starts with are added here, since a site with no seed needs them.

Revision ID: discography_0001
Revises:
Create Date: 2026-11-24
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from kernel import lifecycle

revision: str = "discography_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("discography",)
#: Search (kernel_0014) and media: the downgrade takes back what the releases
#: left in their tables.
depends_on: str | Sequence[str] | None = ("kernel_0014", "media_0001")

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds seven tables, three grants and five roles.
destructive = False

GRANTS = (
    ("discography.release.manage", "admin"),
    ("discography.release.manage", "editor"),
    ("discography.settings.manage", "admin"),
)
PERMISSIONS = ("discography.release.manage", "discography.settings.manage")
ROLES = ("Artist", "Featuring", "Produced by", "Written by", "Mastered by")
_ROLE_IDS = uuid.UUID("0b7f8c1d-2e4a-4f6b-9c3d-5a1e7f2b8d90")
SLUG_RULE = "~ '^[a-z0-9]+(-[a-z0-9]+)*$'"
PLATFORMS = (
    "'spotify', 'apple-music', 'youtube', 'youtube-music', 'amazon-music', "
    "'soundcloud', 'bandcamp', 'tidal', 'deezer'"
)

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)
_roles = sa.table(
    "discography_role",
    sa.column("id", sa.UUID),
    sa.column("name", sa.String),
    sa.column("position", sa.SmallInteger),
)


def _when(name: str, nullable: bool = False) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "discography_release",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("artist_line", sa.String(length=200), server_default="", nullable=False),
        sa.Column("credit_line", sa.String(length=300), server_default="", nullable=False),
        sa.Column("summary", sa.String(length=300), server_default="", nullable=False),
        sa.Column("cover_id", sa.UUID(), nullable=True),
        sa.Column("back_cover_id", sa.UUID(), nullable=True),
        sa.Column("tracklist_to_come", sa.Boolean(), server_default="false", nullable=False),
        _when("announced_at", nullable=True),
        _when("created_at"),
        _when("updated_at"),
        *lifecycle.columns(),
        sa.CheckConstraint(f"slug {SLUG_RULE}", name=op.f("ck_discography_release_slug_rule")),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_discography_release_titled")),
        sa.CheckConstraint(
            "kind IN ('album', 'ep', 'single')", name=op.f("ck_discography_release_kind_known")
        ),
        sa.CheckConstraint(
            "year IS NULL OR (year >= 1900 AND year <= 2100)",
            name=op.f("ck_discography_release_year_range"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_discography_release_version_positive")),
        sa.CheckConstraint(lifecycle.RULE, name=op.f("ck_discography_release_lifecycle")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discography_release")),
        sa.UniqueConstraint("slug", name=op.f("uq_discography_release_slug")),
    )
    op.create_index("ix_discography_release_updated_at", "discography_release", ["updated_at"])
    op.create_index("ix_discography_release_published_at", "discography_release", ["published_at"])
    op.create_index(
        "ix_discography_release_due",
        "discography_release",
        ["publish_at"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )

    op.create_table(
        "discography_track",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("explicit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("lyrics", sa.Text(), nullable=True),
        sa.Column("soundcloud_url", sa.String(length=500), nullable=True),
        sa.Column("soundcloud_kind", sa.String(length=10), nullable=True),
        sa.Column("master_key", sa.String(length=512), nullable=True),
        sa.Column("master_name", sa.String(length=150), nullable=True),
        sa.Column("master_bytes", sa.BigInteger(), nullable=True),
        sa.Column("stream_key", sa.String(length=512), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("peaks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("audio_state", sa.String(length=12), server_default="none", nullable=False),
        sa.Column("processing_percent", sa.SmallInteger(), nullable=True),
        sa.Column("audio_error", sa.String(length=60), nullable=True),
        _when("created_at"),
        _when("updated_at"),
        sa.CheckConstraint(f"slug {SLUG_RULE}", name=op.f("ck_discography_track_slug_rule")),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_discography_track_titled")),
        sa.CheckConstraint("position >= 0", name=op.f("ck_discography_track_position_positive")),
        sa.CheckConstraint(
            "audio_state IN ('none', 'processing', 'ready', 'failed')",
            name=op.f("ck_discography_track_audio_state_known"),
        ),
        sa.CheckConstraint(
            "soundcloud_kind IS NULL OR soundcloud_kind IN ('track', 'set')",
            name=op.f("ck_discography_track_soundcloud_kind_known"),
        ),
        sa.CheckConstraint(
            "(soundcloud_url IS NULL) = (soundcloud_kind IS NULL)",
            name=op.f("ck_discography_track_soundcloud_paired"),
        ),
        sa.CheckConstraint(
            "processing_percent IS NULL OR (processing_percent >= 0 AND processing_percent <= 100)",
            name=op.f("ck_discography_track_percent_range"),
        ),
        sa.CheckConstraint(
            "char_length(lyrics) <= 20000", name=op.f("ck_discography_track_lyrics_length")
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name=op.f("ck_discography_track_duration_positive"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_discography_track_version_positive")),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["discography_release.id"],
            name=op.f("fk_discography_track_release_id_discography_release"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discography_track")),
        sa.UniqueConstraint(
            "release_id", "position", name="uq_discography_track_position", deferrable=True
        ),
        sa.UniqueConstraint("release_id", "slug", name="uq_discography_track_slug"),
    )

    op.create_table(
        "discography_person",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("profile", sa.String(length=12), server_default="unlinked", nullable=False),
        sa.Column("roster_profile_id", sa.UUID(), nullable=True),
        _when("created_at"),
        _when("updated_at"),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_discography_person_named")),
        sa.CheckConstraint(
            "profile IN ('unlinked', 'collective', 'member', 'not_member')",
            name=op.f("ck_discography_person_profile_known"),
        ),
        sa.CheckConstraint(
            "(roster_profile_id IS NOT NULL) = (profile = 'member')",
            name=op.f("ck_discography_person_member_linked"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_discography_person_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discography_person")),
    )
    op.create_index(
        "uq_discography_person_name",
        "discography_person",
        [sa.text("lower(name::text)")],
        unique=True,
    )

    op.create_table(
        "discography_role",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("btrim(name) <> ''", name=op.f("ck_discography_role_named")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discography_role")),
        sa.UniqueConstraint("name", name=op.f("uq_discography_role_name")),
    )

    op.create_table(
        "discography_credit",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=True),
        sa.Column("track_id", sa.UUID(), nullable=True),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "(release_id IS NULL) <> (track_id IS NULL)", name=op.f("ck_discography_credit_on_one")
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_discography_credit_position_positive")),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["discography_person.id"],
            name=op.f("fk_discography_credit_person_id_discography_person"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["discography_role.id"],
            name=op.f("fk_discography_credit_role_id_discography_role"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["discography_release.id"],
            name=op.f("fk_discography_credit_release_id_discography_release"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["discography_track.id"],
            name=op.f("fk_discography_credit_track_id_discography_track"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discography_credit")),
    )
    for column in ("person_id", "role_id", "release_id", "track_id"):
        op.create_index(op.f(f"ix_discography_credit_{column}"), "discography_credit", [column])

    op.create_table(
        "discography_link",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            f"platform IN ({PLATFORMS})", name=op.f("ck_discography_link_platform_known")
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_discography_link_position_positive")),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["discography_release.id"],
            name=op.f("fk_discography_link_release_id_discography_release"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discography_link")),
        sa.UniqueConstraint(
            "release_id",
            "platform",
            name="uq_discography_link_platform",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(op.f("ix_discography_link_release_id"), "discography_link", ["release_id"])

    op.create_table(
        "discography_move",
        sa.Column("old_path", sa.String(length=161), nullable=False),
        sa.Column("release_id", sa.UUID(), nullable=False),
        sa.Column("track_id", sa.UUID(), nullable=True),
        _when("created_at"),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["discography_release.id"],
            name=op.f("fk_discography_move_release_id_discography_release"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["track_id"],
            ["discography_track.id"],
            name=op.f("fk_discography_move_track_id_discography_track"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("old_path", name=op.f("pk_discography_move")),
    )
    op.create_index(op.f("ix_discography_move_release_id"), "discography_move", ["release_id"])
    op.create_index(op.f("ix_discography_move_track_id"), "discography_move", ["track_id"])

    op.bulk_insert(_grants, [{"role_id": role, "permission": key} for key, role in GRANTS])
    op.bulk_insert(
        _roles,
        [
            {"id": uuid.uuid5(_ROLE_IDS, name), "name": name, "position": position}
            for position, name in enumerate(ROLES)
        ],
    )


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    # What the releases left in the kernel's tables and media's, which hold no
    # foreign key to them: their search documents and their covers' uses.
    op.execute("DELETE FROM kernel_search_document WHERE content_type = 'discography.release'")
    op.execute("DELETE FROM media_use WHERE owner LIKE 'discography.release:%'")
    op.drop_index(op.f("ix_discography_move_track_id"), table_name="discography_move")
    op.drop_index(op.f("ix_discography_move_release_id"), table_name="discography_move")
    op.drop_table("discography_move")
    op.drop_index(op.f("ix_discography_link_release_id"), table_name="discography_link")
    op.drop_table("discography_link")
    for column in ("track_id", "release_id", "role_id", "person_id"):
        op.drop_index(op.f(f"ix_discography_credit_{column}"), table_name="discography_credit")
    op.drop_table("discography_credit")
    op.drop_table("discography_role")
    op.drop_index("uq_discography_person_name", table_name="discography_person")
    op.drop_table("discography_person")
    op.drop_table("discography_track")
    op.drop_index("ix_discography_release_due", table_name="discography_release")
    op.drop_index("ix_discography_release_published_at", table_name="discography_release")
    op.drop_index("ix_discography_release_updated_at", table_name="discography_release")
    op.drop_table("discography_release")
