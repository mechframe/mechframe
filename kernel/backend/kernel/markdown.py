"""What a person writes in Markdown, made HTML on the server (decision 0055;
SPEC.md 15, "User HTML"; contract `dev plans/contracts/pages.md`).

A page's body, a post's, a comment: every module that takes Markdown makes
its HTML here, so a reader gets the same rules wherever they read.

- `render(text)` is python-markdown with VybeSite's extensions (`extra`, for
  tables and fenced code; `sane_lists`, so a stray line never joins two lists
  and a list can start at 3), then nh3 to the allowlist `server_copy.cleaned`
  keeps: headings from `h2`, paragraphs, lists, links, emphasis, code, quotes,
  images and tables. The page has its own `h1`, so an author's `#` heading
  becomes an `h2`. HTML typed among the Markdown is cleaned like the rest: a
  script or a style goes with its words, any other tag outside the list goes
  and keeps its words, and so do an `on…` attribute, an inline style and an
  address that isn't http, https, mailto, tel or a path on the site. Ported
  from VybeSite's `render_service.py` (its body allowlist, 2026-09-28).
- `plain(text)` is the words alone, one space between blocks, for the search
  index and a description left empty.
- `excerpt(words, limit)` cuts plain words at a word within `limit`.

A module renders per read rather than storing the HTML, so a rule changed here
reaches every body at once; it caps a body's length itself (pages and blog at
100,000 characters). The API answers the HTML for the browser to draw with the
kit's `Prose`, and the server copy passes the same through `cleaned`.
"""

from __future__ import annotations

import html
import re

import markdown as markdown_lib
import nh3

from kernel import server_copy

#: VybeSite's extensions (`render_service.MARKDOWN_EXTENSIONS`).
EXTENSIONS = ("extra", "sane_lists")

#: An h1 tag, opening or closing, with any attributes, a quoted value's `>`
#: included (CodeRabbit on #118): the page has its own.
_H1 = re.compile(r"""<(/?)h1(?:\s(?:[^>"']|"[^"]*"|'[^']*')*)?>""", re.IGNORECASE)
#: Where one block ends and the next begins, so `plain` puts a space there.
_BLOCK = re.compile(
    r"<(/?)(p|h[1-6]|li|ul|ol|blockquote|pre|table|thead|tbody|tr|td|th|hr|br|figure|figcaption"
    r"|section|article)\b",
    re.IGNORECASE,
)
_SPACES = re.compile(r"\s+")
#: What an excerpt may end on before its ellipsis is added.
_TRAILING = " \t\n,;:-" + chr(0x2013) + chr(0x2014)  # and the en and em dashes


def render(text: str) -> str:
    """The HTML a page draws for `text`, cleaned; empty for no words."""
    if not text.strip():
        return ""
    made = markdown_lib.markdown(text, extensions=list(EXTENSIONS), output_format="html")
    return str(server_copy.cleaned(_H1.sub(r"<\1h2>", made)))


def plain(text: str) -> str:
    """The words of `text` without their markup: no tags, no images, a space
    between blocks."""
    spaced = _BLOCK.sub(r" <\1\2", render(text))
    return _SPACES.sub(" ", html.unescape(nh3.clean(spaced, tags=set()))).strip()


def excerpt(words: str, limit: int = 160) -> str:
    """`words`, or as many of them as fit in `limit` with an ellipsis after,
    cut where a word ends when one does. A limit below 1 can't hold the
    ellipsis, so it's refused (CodeRabbit on #118)."""
    if limit < 1:
        raise ValueError(f"An excerpt's limit is at least 1, not {limit}.")
    words = _SPACES.sub(" ", words).strip()
    if len(words) <= limit:
        return words
    cut = words[: limit - 1]
    if not words[limit - 1].isspace() and " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(_TRAILING) + "…"
