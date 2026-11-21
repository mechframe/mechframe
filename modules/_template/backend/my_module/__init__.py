"""my-module: the backend package. The id's hyphens become underscores here.

`CSP` lists the hosts this module adds to the site's Content-Security-Policy
while it's on, as (directive, https origin) pairs, such as
("frame-src", "https://player.vimeo.com"). Leave it empty when the module
loads nothing from elsewhere (decision 0009).

`BOT_PROVIDER` is a bot check for every public form on the site, which the
settings section `kernel.bot` can name (hook 5, decision 0052): an object
with `async def verify(request, proof, form) -> bot.Pass | bot.Held`. Only a
module that is one (bot-shield) gives it; leave it None. A module with a
public form doesn't add one: its service calls `bot.verify`.
"""

from typing import Any

CSP: list[tuple[str, str]] = []
BOT_PROVIDER: Any = None
