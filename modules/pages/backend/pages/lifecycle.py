"""pages: its publishable content (kernel.lifecycle, hook 1, decision 0052):
a page is drafted, scheduled and published. module.json's `content_types`
names `pages.page` with `"lifecycle": true`."""

from __future__ import annotations

from pages.models import Page

PUBLISHABLE: tuple[type, ...] = (Page,)
