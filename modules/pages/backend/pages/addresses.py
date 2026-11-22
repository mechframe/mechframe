"""A page's address (`dev plans/contracts/pages.md` §2): one segment of
lowercase letters, digits and single hyphens, and never one the site already
answers otherwise.

The start's route table (`app.state.public_routes`, `server_copy.Routes`)
decides who answers an address: a page can't take one that the kernel, the
site's own pages or another module answers, whether or not that module is on,
so turning it on never hides a page. `pages`' own `/:address` is the least
fixed pattern there is, so every other pattern that meets an address wins it.
"""

from __future__ import annotations

import re

from kernel import server_copy
from pages.models import ADDRESS_PATTERN, MAX_ADDRESS

_ADDRESS = re.compile(ADDRESS_PATTERN)
#: First segments the kernel keeps: its API, the admin, the built app's files,
#: and those its own pages start with (/account, /auth/verify, /notifications/...).
_KEPT = frozenset(
    {"api", "admin", "assets"} | {page.path.split("/")[1] for page in server_copy.KERNEL_PAGES}
)


def valid(address: str) -> bool:
    """Whether `address` is one a page may have: `/about`, `/press-kit`."""
    return len(address) <= MAX_ADDRESS and _ADDRESS.fullmatch(address) is not None


def answered_by(address: str, routes: server_copy.Routes | None) -> str | None:
    """Who answers `address` other than a page, by name, or None when it's free
    for one: "the kernel", "the site's own pages" or a module's name."""
    if address[1:] in _KEPT or address in server_copy.KERNEL_FILES:
        return "the kernel"
    found = routes.resolve(address) if routes is not None else None
    if found is None or found.module == "pages":
        return None
    if found.module == server_copy.SITE:
        return "the site's own pages"
    return routes.name(found.module) if routes is not None else found.module
