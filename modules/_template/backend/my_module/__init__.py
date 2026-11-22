"""my-module: the backend package. The id's hyphens become underscores here.

`CSP` lists the hosts this module adds to the site's Content-Security-Policy
while it's on, as (directive, https origin) pairs, such as
("script-src", "https://js.stripe.com"). Leave it empty when the module
loads nothing from elsewhere (decision 0009). A host a visitor consents to
takes a third item, its category (hook 6, decision 0052): `analytics`,
`marketing` or `media`, as in ("frame-src", "https://player.vimeo.com",
"media"); two items mean `necessary`. Its page then holds what loads from
the host in the kit's `<ConsentGate category>`.

`BOT_PROVIDER` is a bot check for every public form on the site, which the
settings section `kernel.bot` can name (hook 5, decision 0052): an object
with `async def verify(request, proof, form) -> bot.Pass | bot.Held`. Only a
module that is one (bot-shield) gives it; leave it None. A module with a
public form doesn't add one: its service calls `bot.verify`.

`BODY_LIMITS` names the routes that take a larger body than the site's
MAX_BODY_BYTES (1 MB) while the module is on, such as an upload: (method,
path under /api/<id>, bytes), at most 64 MB (decision 0054). Most modules
leave it empty.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
