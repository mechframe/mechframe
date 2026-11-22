"""The contact module's routes (`dev plans/contracts/contact.md` §2), mounted
by the kernel at /api/contact behind require_module("contact"). The form and
sending a message are the public's; everything under /admin needs
`contact.message.manage`."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from contact import service
from contact.schemas import (
    ContactForm,
    InboxExport,
    InboxMessage,
    InboxPage,
    MessageReceived,
    MessageStatus,
    NewContactMessage,
    Tab,
)
from kernel import get_db, optional_user, public, rate_limit, require_permission

router = APIRouter()

MANAGE = require_permission(service.PERMISSION)
#: VybeSite's limit on its contact form, from one address.
MESSAGES_PER_IP = "5/1h"


@router.get("/form", response_model=ContactForm, dependencies=[Depends(public)])
async def read_form(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The Contact page's intro and the topics a message can be about."""
    cfg = await service.current(db)
    return {
        "intro": cfg.intro,
        "topics": [{"key": topic.key, "label": topic.label} for topic in cfg.topics],
    }


@router.post(
    "/messages",
    response_model=MessageReceived,
    status_code=202,
    dependencies=[Depends(public), Depends(rate_limit(MESSAGES_PER_IP))],
)
async def send_message(
    body: NewContactMessage,
    request: Request,
    user: Any = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Received, whether it passed or was held as spam: a bot learns nothing."""
    await service.receive(db, request, body, user_id=None if user is None else user.id)
    await db.commit()
    return {"received": True}


@router.get("/admin/messages", response_model=InboxPage, dependencies=[Depends(MANAGE)])
async def list_messages(
    status: Tab = "all",
    cursor: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = service.PAGE,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A page of a tab, newest first, a first topic's new messages before the rest."""
    return await service.listed(db, status, cursor, limit)


@router.get("/admin/messages/export", response_model=InboxExport)
async def export_messages(
    status: Tab = "all",
    cursor: Annotated[str | None, Query(max_length=80)] = None,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """A page of a whole tab for the Inbox's Export, 1,000 at a time; the first is audited."""
    page = await service.exported(db, status, cursor, by=user.id)
    await db.commit()
    return page


@router.get(
    "/admin/messages/{message_id}", response_model=InboxMessage, dependencies=[Depends(MANAGE)]
)
async def read_message(message_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """One message, opened. Opening it changes nothing: it stays new until it's answered."""
    return service.full(await service.get(db, message_id))


@router.post("/admin/messages/{message_id}/status", response_model=InboxMessage)
async def change_status(
    message_id: uuid.UUID,
    body: MessageStatus,
    user: Any = Depends(MANAGE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """To another tab: Mark as replied, Archive, Spam, or Not spam (back to new)."""
    message = await service.change_status(db, message_id, body.status, by=user.id)
    shown = service.full(message)
    await db.commit()
    return shown


@router.delete("/admin/messages/{message_id}", status_code=204)
async def delete_message(
    message_id: uuid.UUID, user: Any = Depends(MANAGE), db: AsyncSession = Depends(get_db)
) -> Response:
    """Gone for good: for a sender who asks to be forgotten."""
    await service.remove(db, message_id, by=user.id)
    await db.commit()
    return Response(status_code=204)
