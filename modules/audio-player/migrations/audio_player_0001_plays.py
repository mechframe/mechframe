"""audio-player's plays (`dev plans/contracts/audio-player.md` §3): the day's
salt, today's listeners counted for each item, and each item's daily totals.
No permissions: the Dashboard's card is the source module's.

Revision ID: audio_player_0001
Revises:
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "audio_player_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("audio_player",)
depends_on: str | Sequence[str] | None = "kernel_0002"

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds three empty tables.
destructive = False


def upgrade() -> None:
    op.create_table(
        "audio_player_salt",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("salt", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "octet_length(salt) = 32", name=op.f("ck_audio_player_salt_salt_length")
        ),
        sa.PrimaryKeyConstraint("day", name=op.f("pk_audio_player_salt")),
    )
    op.create_table(
        "audio_player_play",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("listener", sa.CHAR(length=64), nullable=False),
        sa.PrimaryKeyConstraint(
            "day", "source", "item_id", "listener", name=op.f("pk_audio_player_play")
        ),
    )
    op.create_table(
        "audio_player_play_daily",
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("plays", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "plays >= 0", name=op.f("ck_audio_player_play_daily_plays_not_negative")
        ),
        sa.PrimaryKeyConstraint(
            "source", "item_id", "day", name=op.f("pk_audio_player_play_daily")
        ),
    )
    op.create_index(
        "ix_audio_player_play_daily_source_day", "audio_player_play_daily", ["source", "day"]
    )


def downgrade() -> None:
    op.drop_index("ix_audio_player_play_daily_source_day", table_name="audio_player_play_daily")
    op.drop_table("audio_player_play_daily")
    op.drop_table("audio_player_play")
    op.drop_table("audio_player_salt")
