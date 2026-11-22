"""blog: dated posts written in Markdown (`dev plans/contracts/blog.md`).

A post is a title, an address under /blog, a summary and a body in Markdown,
filed under one of the kernel's `blog_category` terms (hook 2), given a cover
from the media library (`media.public`), drafted, scheduled and published
through the kernel's lifecycle, found by site search, answered to crawlers by
its server copy, and followed by up to three related posts. It loads nothing
from elsewhere, so `CSP` is empty: a cover is media's to serve.
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
BODY_LIMITS: tuple[tuple[str, str, int], ...] = ()
