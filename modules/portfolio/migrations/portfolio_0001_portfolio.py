"""portfolio (`dev plans/contracts/portfolio.md` §3): `portfolio_piece`, one
row per piece with the kernel's lifecycle columns. Its disciplines, search
documents and pictures' uses live in the kernel's tables (`kernel_0013`,
`kernel_0014`) and media's, so this depends on them. Admins and editors are
granted `portfolio.piece.add` and `portfolio.piece.manage`; an owner holds
every permission.

Revision ID: portfolio_0001
Revises:
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from kernel import lifecycle

revision: str = "portfolio_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("portfolio",)
#: The taxonomy (kernel_0013) and search (kernel_0014), and media: the
#: downgrade takes back what the pieces left in their tables.
depends_on: str | Sequence[str] | None = ("kernel_0014", "media_0001")

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds one empty table and four grants.
destructive = False

PERMISSIONS = ("portfolio.piece.add", "portfolio.piece.manage")
ROLES = ("admin", "editor")
SLUG_RULE = "~ '^[a-z0-9]+(-[a-z0-9]+)*$'"

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "portfolio_piece",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("artist_id", sa.UUID(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("about", sa.Text(), server_default="", nullable=False),
        sa.Column("image_id", sa.UUID(), nullable=False),
        sa.Column("video_url", sa.String(length=500), nullable=True),
        sa.Column("video_id", sa.String(length=11), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *lifecycle.columns(),
        sa.CheckConstraint(f"slug {SLUG_RULE}", name=op.f("ck_portfolio_piece_slug_rule")),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_portfolio_piece_titled")),
        sa.CheckConstraint(
            "char_length(about) <= 2000", name=op.f("ck_portfolio_piece_about_length")
        ),
        sa.CheckConstraint(
            "year IS NULL OR year >= 1000", name=op.f("ck_portfolio_piece_year_range")
        ),
        sa.CheckConstraint(
            "(video_url IS NULL) = (video_id IS NULL)", name=op.f("ck_portfolio_piece_video_whole")
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_portfolio_piece_version_positive")),
        sa.CheckConstraint(lifecycle.RULE, name=op.f("ck_portfolio_piece_lifecycle")),
        sa.ForeignKeyConstraint(
            ["artist_id"],
            ["auth_user.id"],
            name=op.f("fk_portfolio_piece_artist_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_piece")),
        sa.UniqueConstraint("slug", name=op.f("uq_portfolio_piece_slug")),
    )
    op.create_index("ix_portfolio_piece_live", "portfolio_piece", ["status", "published_at"])
    op.create_index("ix_portfolio_piece_updated_at", "portfolio_piece", ["updated_at"])
    op.create_index("ix_portfolio_piece_artist_id", "portfolio_piece", ["artist_id"])
    op.create_index(
        "ix_portfolio_piece_due",
        "portfolio_piece",
        ["publish_at"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    # What the pieces left in the kernel's tables and media's, which hold no
    # foreign key to them: their disciplines, their search documents and their
    # pictures' uses.
    op.execute("DELETE FROM kernel_term_link WHERE content_type = 'portfolio.piece'")
    op.execute("DELETE FROM kernel_search_document WHERE content_type = 'portfolio.piece'")
    op.execute("DELETE FROM media_use WHERE owner LIKE 'portfolio.piece:%'")
    op.drop_index("ix_portfolio_piece_due", table_name="portfolio_piece")
    op.drop_index("ix_portfolio_piece_artist_id", table_name="portfolio_piece")
    op.drop_index("ix_portfolio_piece_updated_at", table_name="portfolio_piece")
    op.drop_index("ix_portfolio_piece_live", table_name="portfolio_piece")
    op.drop_table("portfolio_piece")
