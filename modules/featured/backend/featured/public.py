"""What a site's own code may call, and modules that list `featured` under
requires.modules: a slot's live read, as `GET /api/featured/slots/{key}`
answers it, for a page the server composes."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from featured import service
from featured.schemas import LivePlacement, LiveSlot


async def live(db: AsyncSession, key: str) -> LiveSlot | None:
    """What's live in the slot `key` now, in order; None while there's no such slot."""
    found = await service.live_slot(db, key)
    return None if found is None else LiveSlot.model_validate(found)


__all__ = ["LivePlacement", "LiveSlot", "live"]
