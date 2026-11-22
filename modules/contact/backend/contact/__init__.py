"""contact: the site's contact form and the admin's Inbox
(`dev plans/contracts/contact.md`).

A visitor writes from /contact; the site's people read each message in
the admin's Content, Inbox, reply from their own email, and mark it replied,
archive it or set it aside as spam. A message the bot check or the site's
filters hold is stored as spam and told to nobody. It loads nothing from
elsewhere, so `CSP` is empty.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
