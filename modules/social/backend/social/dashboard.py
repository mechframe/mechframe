"""Dashboard cards (hook 8, decision 0052):

- `social.troubled`, while a share failed in Buffer or wasn't confirmed in the
  last 14 days, for those who share, sending them to its admin page;
- the setup step `social.connect_buffer`, done once a token in use has listed
  a channel.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kernel import attention
from social import service


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    item = await service.troubled_item(db)
    return [] if item is None else [item]


ATTENTION = _attention
SETUP = (service.CONNECT_BUFFER,)
