"""pages: the site's fixed pages, such as About and Credits
(`dev plans/contracts/pages.md`).

A page is a title, an address and a body in Markdown, drafted and published
through the kernel's lifecycle, found by site search, answered to crawlers by
its server copy, and listed in the header's menu, the footer's or neither
(decision 0056). It loads nothing from elsewhere, so `CSP` is empty.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
