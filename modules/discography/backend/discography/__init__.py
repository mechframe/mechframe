"""discography: the site's music library (`dev plans/contracts/discography.md`).

Releases (albums, EPs and singles) with their tracks in order, credits,
streaming links and covers from the media library (`media.public`), drafted,
scheduled for release day and published through the kernel's lifecycle. A
track plays from a stream file a job makes from its uploaded master
(`audio`, soundfile, decision 0070), else from its SoundCloud link (read by
`embeds.public.recognise`). `audio-player` and `featured` read the library
through `public.py`.

`CSP` is empty: the stream files are the public bucket's, whose origin the
kernel lets `<audio>` play while it's set (decision 0070), and nothing loads
from SoundCloud until `audio-player` brings its widget.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
#: The upload routes take a master past the site's MAX_BODY_BYTES, up to the
#: kernel's ceiling: a 60 MB file and the form's own bytes (decision 0054).
BODY_LIMITS: tuple[tuple[str, str, int], ...] = (
    ("POST", "/admin/releases/{release_id}/tracks/upload", 64 * 1024 * 1024),
    ("PUT", "/admin/tracks/{track_id}/audio", 64 * 1024 * 1024),
)
