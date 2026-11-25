"""audio-player's settings and its one answer (`dev plans/contracts/audio-player.md` §2).

`Settings` is the section `audio-player`, edited on Settings, Site, under
"Player"; the public player reads the same two values from `GET /settings`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kernel import Answer

MIN_COUNT_AFTER = 5
MAX_COUNT_AFTER = 120


class Settings(BaseModel):
    model_config = ConfigDict(strict=True)

    #: Play the next track in the queue when one ends.
    autoplay_next: bool = True
    #: Seconds really heard before a play counts (or the whole of a shorter track).
    count_after_seconds: int = Field(default=30, ge=MIN_COUNT_AFTER, le=MAX_COUNT_AFTER)


class PlayerSettings(Answer):
    """What the public player needs to know, read once per page."""

    autoplay_next: bool
    count_after_seconds: int
