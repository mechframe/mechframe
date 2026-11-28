"""Reactions (`dev plans/contracts/reactions.md` §3): one row for each
person's reaction to a thing, the thing named by its content type and id.

Revision ID: reactions_0001
Revises:
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "reactions_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("reactions",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds one empty table.
destructive = False


def upgrade() -> None:
    op.create_table(
        "reactions_reaction",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_type ~ '^[a-z][a-z0-9-]*\\.[a-z][a-z0-9_]*$'",
            name=op.f("ck_reactions_reaction_target_type_known"),
        ),
        sa.CheckConstraint(
            "key ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_reactions_reaction_key_known")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_reactions_reaction_user_id_auth_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reactions_reaction")),
        sa.UniqueConstraint(
            "target_type",
            "target_id",
            "user_id",
            "key",
            name=op.f("uq_reactions_reaction_one_each"),
        ),
    )
    op.create_index(op.f("ix_reactions_reaction_user_id"), "reactions_reaction", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_reactions_reaction_user_id"), table_name="reactions_reaction")
    op.drop_table("reactions_reaction")
