"""portfolio's event (SPEC.md section 11): `portfolio.piece.deleted` goes out
when a piece is deleted, for a module that keeps something of it (a shop's
product pointing back, a profile's list). Publishing and unpublishing are the
kernel's `kernel.content.published` and `kernel.content.unpublished`.
portfolio listens to nothing: a deleted account's credit goes by its foreign
key, and its export and erase by hook 7 (`privacy.py`)."""

from __future__ import annotations

import uuid

from kernel import events


@events.payload("portfolio.piece.deleted", v=1)
class PieceDeleted(events.Payload):
    """A piece is gone."""

    id: uuid.UUID
