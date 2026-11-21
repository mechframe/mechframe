"""Consent categories (decision 0052, hook 6; contract `dev plans/contracts/hooks.md`).

A module that loads something from another host names what it's for: each
entry of its `__init__.py`'s `CSP` takes a third item, its category,

    CSP = [("frame-src", "https://www.youtube-nocookie.com", "media")]

one of `CATEGORIES`. An entry with two items is `necessary`: it needs no
consent (a payment provider's script, say). The start refuses a category
the kernel doesn't know.

**The CSP doesn't change with consent:** a host is in the policy while its
module is on, whatever anyone chose (`kernel.security`). What waits for
consent is the web app: `GET /api/kernel/site` gives `consent: {mode,
categories}`, the categories the modules on name (never `necessary`), and
the kit's `<ConsentGate category>` holds a script or iframe until the visitor
grants its category. The choice is kept in the first-party cookie
`__Host-mf_consent`, set by script, and never on the server (§6).

CONSENT_MODE is `ask` (gates hold until granted; an embed's facade click
grants `media`) or `off` (every gate open, for a site with nothing to ask).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from kernel.modules import InstalledModule

Category = Literal["necessary", "analytics", "marketing", "media"]
Mode = Literal["ask", "off"]

#: The categories, in the order the site lists them; `necessary` needs no consent.
CATEGORIES: tuple[Category, ...] = ("necessary", "analytics", "marketing", "media")
NECESSARY: Category = "necessary"

#: A CSP entry with its category: (directive, https origin, category).
Entry = tuple[str, str, Category]

_categories: dict[str, frozenset[Category]] = {}


def entries(module: InstalledModule) -> tuple[Entry, ...]:
    """The module's `CSP` entries, each with its category (`necessary` when
    it names none). ValueError, naming the module, for an entry that isn't a
    (directive, origin) or (directive, origin, category) of strings, or for
    a category the kernel doesn't know."""
    found: list[Entry] = []
    for entry in module.csp:
        if (
            not isinstance(entry, tuple)
            or len(entry) not in (2, 3)
            or not all(isinstance(part, str) for part in entry)
        ):
            raise ValueError(
                f"{module.id}'s CSP entry {entry!r} isn't (directive, https origin) "
                "or (directive, https origin, category)."
            )
        directive, source, *named = entry
        category = named[0] if named else NECESSARY
        if category not in CATEGORIES:
            raise ValueError(
                f"{module.id}'s CSP entry for {source} names the category {category!r}: "
                f"it's one of {', '.join(CATEGORIES[:-1])} or {CATEGORIES[-1]}."
            )
        found.append((directive, source, category))
    return tuple(found)


def build(installed: Iterable[InstalledModule]) -> dict[str, frozenset[Category]]:
    """The categories each module asks consent for, by module id: the ones
    its CSP entries name, other than `necessary`. A module asking none isn't
    listed. ValueError as `entries` raises it."""
    found: dict[str, frozenset[Category]] = {}
    for module in installed:
        asked = frozenset(category for _, _, category in entries(module) if category != NECESSARY)
        if asked:
            found[module.id] = asked
    return found


def install(categories: Mapping[str, frozenset[Category]]) -> None:
    """Called by `kernel.app.assemble` with `build`'s answer."""
    global _categories
    _categories = dict(categories)


def categories(on: Iterable[str]) -> list[Category]:
    """The categories the modules `on` ask consent for, in `CATEGORIES`'
    order, `necessary` never among them."""
    asked = set().union(*(_categories.get(module, frozenset()) for module in on))
    return [category for category in CATEGORIES if category in asked]
