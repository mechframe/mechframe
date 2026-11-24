"""audio-player's tables (`dev plans/contracts/audio-player.md` §3).

Plays are counted without keeping anyone's details:

- `audio_player_salt` holds each day's random salt, made by its first play.
- `audio_player_play` holds, for today only, who has been counted for what:
  `listener` is an HMAC of the visitor's address and browser name under that
  day's salt, so each listener counts once per item per day. The salt and
  these rows go once their day is over, and the hashes can't be traced back.
- `audio_player_play_daily` is the total per item per day, kept two years.

An item is `(source, item_id)`, where `source` is the module that handed it to
the player and what it is, such as `discography.track`. There are no foreign
keys: the source module calls `public.forget` when an item goes (SPEC 10).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import CHAR, CheckConstraint, Date, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from kernel import Base

MAX_SOURCE = 40
SALT_BYTES = 32
#: A hex SHA-256.
LISTENER_LENGTH = 64


class Salt(Base):
    __tablename__ = "audio_player_salt"
    __table_args__ = (CheckConstraint(f"octet_length(salt) = {SALT_BYTES}", name="salt_length"),)

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    salt: Mapped[bytes] = mapped_column(LargeBinary)


class Play(Base):
    """One listener counted for one item on one day."""

    __tablename__ = "audio_player_play"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    source: Mapped[str] = mapped_column(String(MAX_SOURCE), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    listener: Mapped[str] = mapped_column(CHAR(LISTENER_LENGTH), primary_key=True)


class Daily(Base):
    """An item's plays on one day."""

    __tablename__ = "audio_player_play_daily"
    __table_args__ = (
        CheckConstraint("plays >= 0", name="plays_not_negative"),
        Index("ix_audio_player_play_daily_source_day", "source", "day"),
    )

    source: Mapped[str] = mapped_column(String(MAX_SOURCE), primary_key=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    plays: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
