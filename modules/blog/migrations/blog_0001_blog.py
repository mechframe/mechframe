"""The blog (`dev plans/contracts/blog.md` §3): `blog_post`, one row per post
with the kernel's lifecycle columns; `blog_slug_move`, a slug a live post
left; and `blog_post_related`, the posts a post lists under its body. Its
categories are the kernel's taxonomy (`kernel_0013`), so this depends on it.
Admins and editors are granted `blog.post.write` and `blog.post.publish`; an
owner holds every permission.

Revision ID: blog_0001
Revises:
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from kernel import lifecycle

revision: str = "blog_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("blog",)
depends_on: str | Sequence[str] | None = "kernel_0013"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds three empty tables and four grants.
destructive = False

PERMISSIONS = ("blog.post.write", "blog.post.publish")
ROLES = ("admin", "editor")
SLUG_RULE = "~ '^[a-z0-9]+(-[a-z0-9]+)*$'"

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "blog_post",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.String(length=300), server_default="", nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("cover_id", sa.UUID(), nullable=True),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("search_title", sa.String(length=70), nullable=True),
        sa.Column("search_description", sa.String(length=160), nullable=True),
        sa.Column("allow_comments", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("post_to_community", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("email_subscribers", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("announced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *lifecycle.columns(),
        sa.CheckConstraint(f"slug {SLUG_RULE}", name=op.f("ck_blog_post_slug_rule")),
        sa.CheckConstraint("btrim(title) <> ''", name=op.f("ck_blog_post_titled")),
        sa.CheckConstraint("char_length(body) <= 100000", name=op.f("ck_blog_post_body_length")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_blog_post_version_positive")),
        sa.CheckConstraint(lifecycle.RULE, name=op.f("ck_blog_post_lifecycle")),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["auth_user.id"],
            name=op.f("fk_blog_post_author_id_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blog_post")),
        sa.UniqueConstraint("slug", name=op.f("uq_blog_post_slug")),
    )
    op.create_index("ix_blog_post_updated_at", "blog_post", ["updated_at"])
    op.create_index("ix_blog_post_published_at", "blog_post", ["published_at"])
    op.create_index("ix_blog_post_author_id", "blog_post", ["author_id"])
    op.create_index("ix_blog_post_cover_id", "blog_post", ["cover_id"])
    op.create_index(
        "ix_blog_post_due",
        "blog_post",
        ["publish_at"],
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.create_table(
        "blog_slug_move",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"slug {SLUG_RULE}", name=op.f("ck_blog_slug_move_slug_rule")),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["blog_post.id"],
            name=op.f("fk_blog_slug_move_post_id_blog_post"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("slug", name=op.f("pk_blog_slug_move")),
    )
    op.create_index(op.f("ix_blog_slug_move_post_id"), "blog_slug_move", ["post_id"])
    op.create_table(
        "blog_post_related",
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("related_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("post_id <> related_id", name=op.f("ck_blog_post_related_not_itself")),
        sa.CheckConstraint(
            "position >= 0 AND position < 3", name=op.f("ck_blog_post_related_position_range")
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["blog_post.id"],
            name=op.f("fk_blog_post_related_post_id_blog_post"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["related_id"],
            ["blog_post.id"],
            name=op.f("fk_blog_post_related_related_id_blog_post"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("post_id", "related_id", name=op.f("pk_blog_post_related")),
        sa.UniqueConstraint("post_id", "position", name=op.f("uq_blog_post_related_post_id")),
    )
    op.create_index(op.f("ix_blog_post_related_related_id"), "blog_post_related", ["related_id"])
    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.drop_index(op.f("ix_blog_post_related_related_id"), table_name="blog_post_related")
    op.drop_table("blog_post_related")
    op.drop_index(op.f("ix_blog_slug_move_post_id"), table_name="blog_slug_move")
    op.drop_table("blog_slug_move")
    op.drop_index("ix_blog_post_due", table_name="blog_post")
    op.drop_index("ix_blog_post_cover_id", table_name="blog_post")
    op.drop_index("ix_blog_post_author_id", table_name="blog_post")
    op.drop_index("ix_blog_post_published_at", table_name="blog_post")
    op.drop_index("ix_blog_post_updated_at", table_name="blog_post")
    op.drop_table("blog_post")
