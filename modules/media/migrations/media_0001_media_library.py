"""The media library (`dev plans/contracts/media.md` §3): `media_image`, one
row per image of the library, its files in the kernel's public bucket, and
`media_use`, where a module placed one. Admins and editors are granted
`media.image.upload` and `media.image.manage`; an owner holds every permission.

Revision ID: media_0001
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "media_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("media",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds two empty tables, a sequence and two grants.
destructive = False

PERMISSIONS = ("media.image.upload", "media.image.manage")
ROLES = ("admin", "editor")

_grants = sa.table(
    "auth_role_permission", sa.column("role_id", sa.String), sa.column("permission", sa.String)
)


def upgrade() -> None:
    op.create_table(
        "media_image",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("file_version", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=150), nullable=False),
        sa.Column("alt", sa.String(length=250), nullable=True),
        sa.Column("decorative", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("uploaded_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'image/webp')",
            name=op.f("ck_media_image_content_type_known"),
        ),
        sa.CheckConstraint(
            "alt !~ '[[:cntrl:]]' AND strpos(alt, chr(133)) = 0 AND strpos(alt, chr(8232)) = 0 "
            "AND strpos(alt, chr(8233)) = 0",
            name=op.f("ck_media_image_alt_one_line"),
        ),
        sa.CheckConstraint(
            "NOT decorative OR alt IS NULL OR btrim(alt) = ''",
            name=op.f("ck_media_image_decorative_unsaid"),
        ),
        sa.CheckConstraint(
            "version >= 1 AND file_version >= 1", name=op.f("ck_media_image_versions_positive")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["auth_user.id"],
            name=op.f("fk_media_image_uploaded_by_auth_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_image")),
        sa.UniqueConstraint("sha256", name=op.f("uq_media_image_sha256")),
    )
    op.create_index("ix_media_image_created_at", "media_image", ["created_at"])
    op.create_index("ix_media_image_uploaded_by", "media_image", ["uploaded_by"])
    op.create_table(
        "media_use",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("image_id", sa.UUID(), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["media_image.id"],
            name=op.f("fk_media_use_image_id_media_image"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_use")),
        sa.UniqueConstraint("image_id", "owner", name="uq_media_use_image_id_owner"),
    )
    op.create_index(op.f("ix_media_use_owner"), "media_use", ["owner"])
    # Each replace's file version: never reused, since nextval isn't rolled back.
    op.execute(sa.schema.CreateSequence(sa.Sequence("media_file_version_seq", start=2)))
    op.bulk_insert(
        _grants,
        [{"role_id": role, "permission": key} for key in PERMISSIONS for role in ROLES],
    )


def downgrade() -> None:
    # Every grant of them goes, a custom role's too: without the module, nothing declares them.
    op.execute(sa.delete(_grants).where(_grants.c.permission.in_(PERMISSIONS)))
    op.execute(sa.schema.DropSequence(sa.Sequence("media_file_version_seq")))
    op.drop_index(op.f("ix_media_use_owner"), table_name="media_use")
    op.drop_table("media_use")
    op.drop_index("ix_media_image_uploaded_by", table_name="media_image")
    op.drop_index("ix_media_image_created_at", table_name="media_image")
    op.drop_table("media_image")
