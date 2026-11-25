"""featured (`dev plans/contracts/featured.md` §3): the site's players, its
slots, and what each holds in order, another module's item or a YouTube link,
each with optional dates. No foreign key reaches another module.

Admins and editors are granted `featured.placement.manage`, admins
`featured.slot.manage`; an owner holds every permission. No slot is made
here: an admin makes them on Players, or the site's own seed does.

Revision ID: featured_0001
Revises:
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "featured_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("featured",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds two empty tables.
destructive = False

GRANTS = (
    ("featured.placement.manage", "admin"),
    ("featured.placement.manage", "editor"),
    ("featured.slot.manage", "admin"),
)
PERMISSIONS = ("featured.placement.manage", "featured.slot.manage")

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "featured_slot",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=60), nullable=False),
        sa.Column("accepts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kinds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("on_dashboard", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_featured_slot_key_is_a_slug")
        ),
        sa.CheckConstraint(
            "char_length(label) BETWEEN 1 AND 60", name=op.f("ck_featured_slot_label_length")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(accepts) = 'array' AND jsonb_array_length(accepts) >= 1",
            name=op.f("ck_featured_slot_accepts_a_list"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(kinds) = 'array' AND jsonb_array_length(kinds) <= 12",
            name=op.f("ck_featured_slot_kinds_a_list"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_featured_slot_version_positive")),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_featured_slot")),
    )
    op.create_table(
        "featured_placement",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slot_key", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("ref_type", sa.String(length=80), nullable=True),
        sa.Column("ref_id", sa.UUID(), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("video_id", sa.CHAR(length=11), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(ref_type IS NOT NULL AND ref_id IS NOT NULL AND url IS NULL AND video_id IS NULL "
            "AND title IS NULL AND kind IS NULL) OR (ref_type IS NULL AND ref_id IS NULL "
            "AND url IS NOT NULL AND video_id IS NOT NULL AND title IS NOT NULL)",
            name=op.f("ck_featured_placement_an_item_or_a_link"),
        ),
        sa.CheckConstraint(
            "title IS NULL OR char_length(title) BETWEEN 1 AND 200",
            name=op.f("ck_featured_placement_title_length"),
        ),
        sa.CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at",
            name=op.f("ck_featured_placement_ends_after_start"),
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_featured_placement_position_not_negative")
        ),
        sa.ForeignKeyConstraint(
            ["slot_key"],
            ["featured_slot.key"],
            name=op.f("fk_featured_placement_slot_key_featured_slot"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_featured_placement")),
        sa.UniqueConstraint(
            "slot_key",
            "position",
            name=op.f("uq_featured_placement_slot_key"),
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_index(
        "ix_featured_placement_ref", "featured_placement", ["ref_type", "ref_id"], unique=False
    )
    op.bulk_insert(_grants, [{"role_id": role, "permission": key} for key, role in GRANTS])


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index("ix_featured_placement_ref", table_name="featured_placement")
    op.drop_table("featured_placement")
    op.drop_table("featured_slot")
