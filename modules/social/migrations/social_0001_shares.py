"""Social posting (`dev plans/contracts/social.md` §3): the channels Buffer
last listed, and each thing's shares. Admin and editor are granted
`social.post.send` (§8, 2); an owner holds every permission.

Revision ID: social_0001
Revises:
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "social_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("social",)
depends_on: str | Sequence[str] | None = "kernel_0016"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds empty tables and two grants.
destructive = False

PERMISSIONS = ("social.post.send",)
ROLES = ("admin", "editor")

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "social_channel",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=300), server_default="", nullable=False),
        sa.Column("service", sa.String(length=40), server_default="", nullable=False),
        sa.Column("descriptor", sa.String(length=300), server_default="", nullable=False),
        sa.Column("avatar", sa.String(length=600), server_default="", nullable=False),
        sa.Column("organization_id", sa.String(length=100), server_default="", nullable=False),
        sa.Column("disconnected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("locked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("queue_paused", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settings_version", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_channel")),
    )
    op.create_table(
        "social_share",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("content_id", sa.UUID(), nullable=False),
        sa.Column("admin_path", sa.String(length=300), nullable=False),
        sa.Column("channel_id", sa.String(length=100), nullable=False),
        sa.Column("channel_name", sa.String(length=300), server_default="", nullable=False),
        sa.Column("service", sa.String(length=40), server_default="", nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=600), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("buffer_post_id", sa.String(length=100), nullable=True),
        sa.Column("error", sa.Text(), server_default="", nullable=False),
        sa.Column("external_link", sa.String(length=600), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by_id", sa.UUID(), nullable=True),
        sa.Column("sent_by_name", sa.String(length=300), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "mode IN ('queue', 'now', 'at', 'draft')", name=op.f("ck_social_share_mode_known")
        ),
        sa.CheckConstraint(
            "state IN ('sending', 'queued', 'draft', 'sent', 'failed', 'refused', 'unknown', "
            "'removed')",
            name=op.f("ck_social_share_state_known"),
        ),
        sa.CheckConstraint("char_length(text) <= 5000", name=op.f("ck_social_share_text_short")),
        sa.ForeignKeyConstraint(
            ["sent_by_id"],
            ["auth_user.id"],
            name=op.f("fk_social_share_sent_by_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_social_share")),
    )
    op.create_index(
        "ix_social_share_content", "social_share", ["content_type", "content_id", "created_at"]
    )
    op.create_index("ix_social_share_state_created_at", "social_share", ["state", "created_at"])
    op.create_index(op.f("ix_social_share_sent_by_id"), "social_share", ["sent_by_id"])

    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of it goes, a custom role's too: without the module, nothing declares it.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index(op.f("ix_social_share_sent_by_id"), table_name="social_share")
    op.drop_index("ix_social_share_state_created_at", table_name="social_share")
    op.drop_index("ix_social_share_content", table_name="social_share")
    op.drop_table("social_share")
    op.drop_table("social_channel")
