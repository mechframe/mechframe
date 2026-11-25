"""social: the site's published content shared to its social channels
through Buffer (`dev plans/contracts/social.md`, decision 0067).

From a published post's editor (and any module's admin page that draws the
kernel's `ShareParts`), someone holding `social.post.send` picks the channels
Buffer reaches, edits one text and chooses when it goes out. Each channel's
post is recorded before Buffer is asked, so one whose answer is lost still
counts as shared. Social imports no module: it names a thing by its content
type and id, and the kernel's `server_copy.preview` gives its link.

The token is BUFFER_ACCESS_TOKEN on the host, or one saved in Settings, sealed;
the saved one wins. Buffer is called from the server only, and the browser
loads nothing from it (the channels' pictures aren't drawn), so `CSP` is empty.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
