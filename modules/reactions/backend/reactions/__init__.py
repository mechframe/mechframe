"""reactions: Fire, Love and Mind blown under any module's live things
(`dev plans/contracts/reactions.md`, decision 0068).

A signed-in member with a verified address presses a reaction under a thing,
and everyone reading sees the count of each. Reactions imports no module: it
names a thing by its content type and id, as item references do (hook 11),
and asks `kernel.refs` whether it's there and live. The web's row fills the
kernel's `content.reactions` slot, which a module's public page draws with
`ReactionParts`, so neither module requires the other.

The browser loads nothing from another host, so `CSP` is empty.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
