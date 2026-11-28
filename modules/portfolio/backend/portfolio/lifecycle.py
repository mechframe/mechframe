"""portfolio: its publishable content (kernel.lifecycle, hook 1, decision 0052):
a piece is drafted, scheduled and published. module.json's `content_types`
names `portfolio.piece` with `"lifecycle": true`."""

from __future__ import annotations

from portfolio.models import Piece

PUBLISHABLE: tuple[type, ...] = (Piece,)
