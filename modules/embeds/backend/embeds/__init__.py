"""embeds: a YouTube, SoundCloud, Spotify or Bandcamp link alone in its
paragraph drawn as that provider's player, the editor's Embed button, and the
YouTube playlist player (`dev plans/contracts/embeds.md`).

It has no routes and no tables: the links live in the pages' and posts' own
text, and the players are drawn by the kit's `Prose` through the slot
`prose.embed` (decision 0060). `public.py` reads the same links for an
email's card.

`CSP` is each player's one frame host, the IFrame API the playlist player
loads, and YouTube's thumbnails, every one in the consent category `media`
(hook 6): nothing loads from them until a visitor plays something.
"""

from typing import Any

from embeds.providers import FRAME_HOSTS

CSP: list[tuple[str, str] | tuple[str, str, str]] = [
    *(("frame-src", host, "media") for host in FRAME_HOSTS),
    ("script-src", "https://www.youtube.com", "media"),
    ("img-src", "https://i.ytimg.com", "media"),
]
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
