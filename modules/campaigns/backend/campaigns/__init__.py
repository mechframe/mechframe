"""campaigns: the site's newsletter and release announcements
(`dev plans/contracts/campaigns.md`).

People ask for the news from a sign-up form, from the contact form's "Send me
news and releases too", or when a writer publishes a post with "Email it to
subscribers", and confirm by email. The site's people write an email in
Markdown in Admin, Content, Newsletter, send themselves a test, and send it
now or at a set time: every subscriber gets their own copy, with a one-click
unsubscribe. An address that bounces, complains or unsubscribes is set aside
and never emailed again. It loads nothing from elsewhere, so `CSP` is empty.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
