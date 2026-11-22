"""blog: its publishable content (kernel.lifecycle, hook 1, decision 0052): a
post is drafted, scheduled and published. module.json's `content_types`
names `blog.post` with `"lifecycle": true`."""

from __future__ import annotations

from blog.models import Post

PUBLISHABLE: tuple[type, ...] = (Post,)
