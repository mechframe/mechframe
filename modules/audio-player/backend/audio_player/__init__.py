"""audio-player: the site's one player for its own audio
(`dev plans/contracts/audio-player.md`, decision 0071).

Modules hand it items to play: its web gives the player, its bars and its
one-thing-at-a-time store; its backend counts plays for the module that
checked the item (`public.py`). It has no pages and no events.

`CSP` is SoundCloud's widget and the Widget API script that drives it, both in
the consent category `media` (hook 6): nothing loads from SoundCloud until a
visitor plays a SoundCloud track.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = [
    ("frame-src", "https://w.soundcloud.com", "media"),
    ("script-src", "https://w.soundcloud.com", "media"),
]
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
