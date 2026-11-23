"""Dashboard cards (hook 8, decision 0052):

- `campaigns.set_aside`, "n addresses bounced and were set aside", while an
  address bounced in the last 7 days, for those who see the Set aside tab;
- `campaigns.no_address`, while the postal address is missing and someone is
  subscribed, for those who send: nothing sends until it's set.

The Newsletter page shows the first at its top.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import service
from kernel import attention


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    found = [await service.bounced_item(db), await service.no_address_item(db)]
    return [item for item in found if item is not None]


ATTENTION = _attention
SETUP: tuple[Any, ...] = ()
