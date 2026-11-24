"""audio-player as the kernel loads it: SoundCloud's two hosts wait for media
consent, and the manifest's settings are the schema's (`dev plans/contracts/audio-player.md` §2)."""

from __future__ import annotations

import json
from pathlib import Path

import audio_player
import pytest
from audio_player.schemas import Settings
from pydantic import ValidationError

MANIFEST = json.loads(
    (Path(__file__).resolve().parents[2] / "module.json").read_text(encoding="utf-8")
)


def test_soundcloud_waits_for_media_consent() -> None:
    """Nothing loads from SoundCloud before a visitor plays a SoundCloud track (hook 6)."""
    assert audio_player.CSP == [
        ("frame-src", "https://w.soundcloud.com", "media"),
        ("script-src", "https://w.soundcloud.com", "media"),
    ]


def test_the_manifests_settings_are_the_schemas() -> None:
    defaults = Settings().model_dump()
    assert {each["key"]: each["default"] for each in MANIFEST["settings"]} == defaults


@pytest.mark.parametrize("seconds", [4, 121])
def test_a_count_after_out_of_range_is_refused(seconds: int) -> None:
    with pytest.raises(ValidationError):
        Settings(count_after_seconds=seconds)
