"""The contact form's messages (`dev plans/contracts/contact.md` §3):
`contact_message`, one row per message, in the Inbox or set apart as spam.
Admins are granted `contact.message.manage`; an owner holds every permission.

Revision ID: contact_0001
Revises:
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "contact_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("contact",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds an empty table and one grant.
destructive = False

PERMISSIONS = ("contact.message.manage",)
ROLES = ("admin",)

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "contact_message",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("email_normal", sa.String(length=254), nullable=False),
        sa.Column("topic", sa.String(length=40), nullable=False),
        sa.Column("topic_label", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("wants_news", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="new", nullable=False),
        sa.Column("held_reason", sa.String(length=40), nullable=True),
        sa.Column("status_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status IN ('new', 'replied', 'archived', 'spam')",
            name=op.f("ck_contact_message_status_known"),
        ),
        sa.CheckConstraint(
            "char_length(message) <= 5000", name=op.f("ck_contact_message_message_length")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_contact_message_user_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_message")),
    )
    op.create_index(
        "ix_contact_message_status_received_at", "contact_message", ["status", "received_at"]
    )
    op.create_index(op.f("ix_contact_message_email_normal"), "contact_message", ["email_normal"])
    op.create_index(op.f("ix_contact_message_user_id"), "contact_message", ["user_id"])
    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of it goes, a custom role's too: without the module, nothing declares it.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index(op.f("ix_contact_message_user_id"), table_name="contact_message")
    op.drop_index(op.f("ix_contact_message_email_normal"), table_name="contact_message")
    op.drop_index("ix_contact_message_status_received_at", table_name="contact_message")
    op.drop_table("contact_message")
