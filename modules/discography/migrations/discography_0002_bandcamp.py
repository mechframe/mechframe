"""Bandcamp's own player (`dev plans/contracts/bandcamp-player.md` §3, decision
0075): a track's, and its release's, kept as the page's link with the
player's id in its fragment (`…/track/slug#bandcamp-track=123`), read from the
embed code an admin pasted. A track with no upload or SoundCloud link plays in
its own, else its release's.

Revision ID: discography_0002
Revises: discography_0001
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "discography_0002"
down_revision: str | Sequence[str] | None = "discography_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# True when this migration drops or rewrites data: the CLI asks before running it
# (SPEC.md section 10). Upgrading adds two empty columns; downgrading drops
# them and the players they hold.
destructive = False

#: Each table's column, the kind of player it holds, and its check's name.
COLUMNS = (
    ("discography_track", "track", "ck_discography_track_bandcamp_is_track"),
    ("discography_release", "album", "ck_discography_release_bandcamp_is_album"),
)


def upgrade() -> None:
    for table, kind, check in COLUMNS:
        op.add_column(table, sa.Column("bandcamp_url", sa.String(length=500), nullable=True))
        op.create_check_constraint(
            op.f(check),
            table,
            f"bandcamp_url IS NULL OR bandcamp_url ~ '#bandcamp-{kind}=[0-9]{{1,12}}$'",
        )


def downgrade() -> None:
    for table, _kind, check in COLUMNS:
        op.drop_constraint(op.f(check), table, type_="check")
        op.drop_column(table, "bandcamp_url")
