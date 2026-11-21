"""Account exports (decision 0052, hook 7; `dev plans/contracts/hooks.md` §3;
SPEC.md 14.7): one row for each copy of an account's data asked for, made by
the job `kernel.privacy_export` into private storage at `storage_key`, and
removed with its file once `expires_at` passes. An account deleted meanwhile
leaves the row, its `user_id` null, so the prune still finds the file.

Revision ID: kernel_0015
Revises: kernel_0014
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "kernel_0015"
down_revision: str | Sequence[str] | None = "kernel_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds an empty table. Downgrading drops the
# rows of copies that last 7 days at most: any file still stored under
# kernel/exports/ in the private bucket stays, and is removed by prefix (a
# bucket lifecycle rule on kernel/exports/ of 8 days covers it).
destructive = False


def upgrade() -> None:
    op.create_table(
        "kernel_export",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'ready', 'failed')", name=op.f("ck_kernel_export_status_known")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_kernel_export_user_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_kernel_export")),
    )
    op.create_index("ix_kernel_export_user_id", "kernel_export", ["user_id"])
    op.create_index("ix_kernel_export_expires_at", "kernel_export", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_kernel_export_expires_at", table_name="kernel_export")
    op.drop_index("ix_kernel_export_user_id", table_name="kernel_export")
    op.drop_table("kernel_export")
