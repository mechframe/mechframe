"""The AI's writing help (decision 0058; `dev plans/contracts/kernel-ai.md`):
the writing styles, and `kernel.ai.write` and `kernel.writing.manage` granted
to the built-in admin and editor roles, as `kernel/kernel.json` declares them.
The writing rules and the saved Anthropic key live in the settings table, as
the sections `kernel.writing` and `kernel.ai`.

Revision ID: kernel_0016
Revises: kernel_0015
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "kernel_0016"
down_revision: str | Sequence[str] | None = "kernel_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds an empty table and two grants.
destructive = False

PERMISSIONS = ("kernel.ai.write", "kernel.writing.manage")
ROLES = ("admin", "editor")

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "kernel_writing_style",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("voice_rules", sa.Text(), nullable=False),
        sa.Column("avoid", sa.Text(), nullable=False),
        sa.Column("samples", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(voice_rules) <= 6000", name=op.f("ck_kernel_writing_style_voice_rules_fit")
        ),
        sa.CheckConstraint(
            "char_length(avoid) <= 13000", name=op.f("ck_kernel_writing_style_avoid_fits")
        ),
        sa.CheckConstraint(
            "cardinality(samples) <= 3", name=op.f("ck_kernel_writing_style_samples_fit")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["auth_user.id"],
            name=op.f("fk_kernel_writing_style_created_by_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["auth_user.id"],
            name=op.f("fk_kernel_writing_style_updated_by_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kernel_writing_style")),
    )
    op.create_index(
        "uq_kernel_writing_style_name",
        "kernel_writing_style",
        [sa.text("lower(name::text)")],
        unique=True,
    )
    op.create_index(
        "ix_kernel_writing_style_created_by_id", "kernel_writing_style", ["created_by_id"]
    )
    op.create_index(
        "ix_kernel_writing_style_updated_by_id", "kernel_writing_style", ["updated_by_id"]
    )
    op.bulk_insert(
        _grants,
        [
            {"role_id": role, "permission": permission}
            for permission in PERMISSIONS
            for role in ROLES
        ],
    )


def downgrade() -> None:
    # The grants first: the kernel that the downgrade leaves behind doesn't
    # declare the permissions, so no role may hold them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index("ix_kernel_writing_style_updated_by_id", table_name="kernel_writing_style")
    op.drop_index("ix_kernel_writing_style_created_by_id", table_name="kernel_writing_style")
    op.drop_index("uq_kernel_writing_style_name", table_name="kernel_writing_style")
    op.drop_table("kernel_writing_style")
