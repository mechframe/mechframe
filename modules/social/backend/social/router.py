"""social's routes (`dev plans/contracts/social.md` §2), mounted by the kernel
at /api/social behind require_module("social"). The token's state needs
`kernel.settings.manage`, as saving it does (§8, 5); everything else
`social.post.send`. A share and a channel check spend SOCIAL_RATE_LIMIT, after
the permission check and before the token is opened."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import get_db, rate_limit, require_permission
from social import service
from social.schemas import (
    ChannelList,
    ShareHistory,
    ShareSend,
    ShareSent,
    ShareView,
    Thing,
    TokenState,
)

router = APIRouter()

SETTINGS = require_permission("kernel.settings.manage")
SEND = require_permission(service.SEND_PERMISSION)
ContentType = Annotated[
    str, Query(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9_]*$")
]


async def budget(request: Request) -> None:
    """One call against SOCIAL_RATE_LIMIT, the budget a person's shares and checks share."""
    await rate_limit(service.rate_rule(), key="account", scope="social.buffer")(request)


@router.get("/admin/state", response_model=TokenState)
async def token_state(
    _: Any = Depends(SETTINGS), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Where the token in use comes from and the channels it reached: never the token."""
    return await service.state(db)


@router.post("/admin/channels", response_model=ChannelList)
async def check_channels(
    _: Any = Depends(SEND), __: None = Depends(budget), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Asks Buffer which channels the token reaches, and keeps them: Settings'
    Check and the Share card's Refresh."""
    found = await service.list_channels(db)
    await db.commit()
    return found


@router.get("/admin/shares", response_model=ShareView)
async def share_view(
    type: ContentType,
    id: uuid.UUID,
    _: Any = Depends(SEND),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """What the Share card opens with, from the database alone."""
    return await service.view(db, type, id)


@router.post("/admin/shares", response_model=ShareSent)
async def share(
    body: ShareSend,
    user: Any = Depends(SEND),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Shares the thing to the chosen channels: each refusal before anything leaves."""
    return await service.send(db, body, user=user)


@router.post("/admin/shares/refresh", response_model=ShareHistory)
async def refresh(
    body: Thing, _: Any = Depends(SEND), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Asks Buffer how each post still waiting there stands."""
    return await service.refresh(db, body.type, service.content_id(body.id))


@router.delete("/admin/shares/{share_id}", response_model=ShareHistory)
async def take_back(
    share_id: uuid.UUID, _: Any = Depends(SEND), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Takes a post still waiting in Buffer back out of it."""
    return await service.take_back(db, share_id)
