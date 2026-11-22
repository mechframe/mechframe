"""Dashboard cards (hook 8, decision 0052): "n new messages are waiting"
while any message is new, for those who may read the Inbox. It's a warning
once the oldest has waited 2 days. The Inbox shows the same item at its top."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from contact import service
from kernel import attention


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    item = await service.waiting(db)
    return [] if item is None else [item]


ATTENTION = _attention
SETUP: tuple[Any, ...] = ()
