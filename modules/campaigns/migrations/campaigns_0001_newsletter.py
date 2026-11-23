"""The newsletter (`dev plans/contracts/campaigns.md` §3): its subscribers,
the addresses set aside, its emails, each send's deliveries and Resend's
webhook ids seen. Owner and admin are granted both permissions (§8, 4); an
owner holds every permission, so the grant is admin's.

Revision ID: campaigns_0001
Revises:
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "campaigns_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("campaigns",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds empty tables and two grants.
destructive = False

PERMISSIONS = ("campaigns.email.manage", "campaigns.subscriber.manage")
ROLES = ("admin",)

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "campaigns_subscriber",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("email_normal", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_sealed", sa.Text(), nullable=False),
        sa.Column("confirm_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'subscribed', 'unsubscribed')",
            name=op.f("ck_campaigns_subscriber_status_known"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth_user.id"],
            name=op.f("fk_campaigns_subscriber_user_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns_subscriber")),
        sa.UniqueConstraint("email_normal", name=op.f("uq_campaigns_subscriber_email_normal")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_campaigns_subscriber_token_hash")),
    )
    op.create_index(
        "ix_campaigns_subscriber_status_created_at",
        "campaigns_subscriber",
        ["status", "created_at"],
    )
    op.create_index(op.f("ix_campaigns_subscriber_user_id"), "campaigns_subscriber", ["user_id"])

    op.create_table(
        "campaigns_set_aside",
        sa.Column("email_normal", sa.String(length=254), nullable=False),
        sa.Column("why", sa.String(length=16), nullable=False),
        sa.Column("detail", sa.String(length=300), server_default="", nullable=False),
        sa.Column("since", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "why IN ('bounced', 'complained', 'unsubscribed')",
            name=op.f("ck_campaigns_set_aside_why_known"),
        ),
        sa.PrimaryKeyConstraint("email_normal", name=op.f("pk_campaigns_set_aside")),
    )
    op.create_index("ix_campaigns_set_aside_why_since", "campaigns_set_aside", ["why", "since"])

    op.create_table(
        "campaigns_email",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=150), nullable=False),
        sa.Column("preview", sa.String(length=150), server_default="", nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to", sa.Integer(), server_default="0", nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('newsletter', 'release')", name=op.f("ck_campaigns_email_kind_known")
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'scheduled', 'sending', 'sent')",
            name=op.f("ck_campaigns_email_status_known"),
        ),
        sa.CheckConstraint(
            "char_length(body) <= 100000", name=op.f("ck_campaigns_email_body_length")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["auth_user.id"],
            name=op.f("fk_campaigns_email_created_by_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns_email")),
        sa.UniqueConstraint("post_id", name=op.f("uq_campaigns_email_post_id")),
    )
    op.create_index("ix_campaigns_email_status_send_at", "campaigns_email", ["status", "send_at"])
    op.create_index(op.f("ix_campaigns_email_created_by"), "campaigns_email", ["created_by"])

    op.create_table(
        "campaigns_delivery",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email_id", sa.UUID(), nullable=False),
        sa.Column("subscriber_id", sa.UUID(), nullable=True),
        sa.Column("email_normal", sa.String(length=254), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["campaigns_email.id"],
            name=op.f("fk_campaigns_delivery_email_id_campaigns_email"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"],
            ["campaigns_subscriber.id"],
            name=op.f("fk_campaigns_delivery_subscriber_id_campaigns_subscriber"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns_delivery")),
        sa.UniqueConstraint(
            "email_id", "email_normal", name=op.f("uq_campaigns_delivery_email_id")
        ),
    )
    op.create_index(
        "ix_campaigns_delivery_waiting",
        "campaigns_delivery",
        ["email_id"],
        postgresql_where=sa.text("queued_at IS NULL"),
    )
    op.create_index("ix_campaigns_delivery_queued_at", "campaigns_delivery", ["queued_at"])
    op.create_index(
        op.f("ix_campaigns_delivery_subscriber_id"), "campaigns_delivery", ["subscriber_id"]
    )

    op.create_table(
        "campaigns_webhook_seen",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns_webhook_seen")),
    )
    op.create_index(
        op.f("ix_campaigns_webhook_seen_seen_at"), "campaigns_webhook_seen", ["seen_at"]
    )

    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index(op.f("ix_campaigns_webhook_seen_seen_at"), table_name="campaigns_webhook_seen")
    op.drop_table("campaigns_webhook_seen")
    op.drop_index(op.f("ix_campaigns_delivery_subscriber_id"), table_name="campaigns_delivery")
    op.drop_index("ix_campaigns_delivery_queued_at", table_name="campaigns_delivery")
    op.drop_index("ix_campaigns_delivery_waiting", table_name="campaigns_delivery")
    op.drop_table("campaigns_delivery")
    op.drop_index(op.f("ix_campaigns_email_created_by"), table_name="campaigns_email")
    op.drop_index("ix_campaigns_email_status_send_at", table_name="campaigns_email")
    op.drop_table("campaigns_email")
    op.drop_index("ix_campaigns_set_aside_why_since", table_name="campaigns_set_aside")
    op.drop_table("campaigns_set_aside")
    op.drop_index(op.f("ix_campaigns_subscriber_user_id"), table_name="campaigns_subscriber")
    op.drop_index("ix_campaigns_subscriber_status_created_at", table_name="campaigns_subscriber")
    op.drop_table("campaigns_subscriber")
