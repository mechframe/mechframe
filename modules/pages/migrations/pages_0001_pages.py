"""The site's fixed pages (`dev plans/contracts/pages.md` §3): `pages_page`,
one row per page with the kernel's lifecycle columns, and `pages_move`, an
address a live page left. Admins and editors are granted `pages.page.write`
and `pages.page.publish`; an owner holds every permission.

Revision ID: pages_0001
Revises:
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from kernel import lifecycle

revision: str = "pages_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("pages",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds two empty tables and two grants.
destructive = False

PERMISSIONS = ("pages.page.write", "pages.page.publish")
ROLES = ("admin", "editor")
ADDRESS_RULE = "~ '^/[a-z0-9]+(-[a-z0-9]+)*$'"

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "pages_page",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=60), nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("search_title", sa.String(length=70), nullable=True),
        sa.Column("search_description", sa.String(length=160), nullable=True),
        sa.Column("in_header", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("in_footer", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("menu_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *lifecycle.columns(),
        sa.CheckConstraint(f"address {ADDRESS_RULE}", name=op.f("ck_pages_page_address_rule")),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_pages_page_titled")),
        sa.CheckConstraint("char_length(body) <= 100000", name=op.f("ck_pages_page_body_length")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_pages_page_version_positive")),
        sa.CheckConstraint(lifecycle.RULE, name=op.f("ck_pages_page_lifecycle")),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["auth_user.id"],
            name=op.f("fk_pages_page_updated_by_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pages_page")),
        sa.UniqueConstraint("address", name=op.f("uq_pages_page_address")),
    )
    op.create_index("ix_pages_page_updated_at", "pages_page", ["updated_at"])
    op.create_index("ix_pages_page_updated_by", "pages_page", ["updated_by"])
    op.create_index(
        "ix_pages_page_due",
        "pages_page",
        ["publish_at"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.create_table(
        "pages_move",
        sa.Column("address", sa.String(length=60), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"address {ADDRESS_RULE}", name=op.f("ck_pages_move_address_rule")),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["pages_page.id"],
            name=op.f("fk_pages_move_page_id_pages_page"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("address", name=op.f("pk_pages_move")),
    )
    op.create_index(op.f("ix_pages_move_page_id"), "pages_move", ["page_id"])
    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index(op.f("ix_pages_move_page_id"), table_name="pages_move")
    op.drop_table("pages_move")
    op.drop_index("ix_pages_page_due", table_name="pages_page")
    op.drop_index("ix_pages_page_updated_by", table_name="pages_page")
    op.drop_index("ix_pages_page_updated_at", table_name="pages_page")
    op.drop_table("pages_page")
