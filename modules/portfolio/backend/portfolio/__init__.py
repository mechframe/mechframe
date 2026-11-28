"""portfolio: the site's visual work by discipline (`dev plans/contracts/portfolio.md`).

A piece is a title, an address under /art/piece, a picture from the media
library (`media.public`), the account it's credited to, a year, a few words
and, for a video, a YouTube link read by `embeds.public`, filed under one of
the kernel's `portfolio_discipline` terms (hook 2), drafted, scheduled and
published through the kernel's lifecycle, found by site search, pointed at
through `kernel.refs`, and answered to crawlers by its server copy. Its
artist adds and edits it; staff holding `portfolio.piece.manage` edit every
piece (decision 0074). It loads nothing from elsewhere itself, so `CSP` is
empty: a picture is media's to serve, and YouTube's player embeds'.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
