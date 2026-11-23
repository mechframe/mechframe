"""The newsletter's routes (`dev plans/contracts/campaigns.md` §2), mounted by
the kernel at /api/campaigns behind require_module("campaigns"). Signing up,
the confirm and unsubscribe links and Resend's webhook are the public's (the
webhook signed); the emails need `campaigns.email.manage`, the people
`campaigns.subscriber.manage`."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import service, webhooks
from campaigns.schemas import (
    CampaignEmail,
    CampaignEmailChange,
    CampaignEmailsPage,
    CampaignPreview,
    CampaignPreviewBody,
    CampaignSend,
    CampaignTestSent,
    CampaignWebhookTaken,
    EmailTab,
    NewCampaignEmail,
    NewsletterConfirm,
    NewsletterSetAside,
    NewsletterSubscribers,
    NewSubscription,
    SetAsideAddresses,
    SignupReceived,
    SignupState,
    SubscriberTab,
    SubscriptionLink,
)
from kernel import Problem, clock, get_db, optional_user, public, rate_limit, require_permission

router = APIRouter()

EMAILS = require_permission(service.EMAIL_PERMISSION)
PEOPLE = require_permission(service.SUBSCRIBER_PERMISSION)
#: Sign-ups from one address.
SIGNUPS_PER_IP = "5/1h"
#: Tests from one person.
TESTS_PER_PERSON = "10/1h"
Cursor = Annotated[str | None, Query(max_length=120)]
Limit = Annotated[int, Query(ge=1, le=100)]
Token = Annotated[str, Query(min_length=1, max_length=200)]


# --- the public ------------------------------------------------------------------------------


@router.get("/signup", response_model=SignupState, dependencies=[Depends(public)])
async def signup_state(db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    """Whether sign-ups are open, for a site's forms (`useNewsletterOn()`)."""
    return {"open": (await service.current(db)).signups_open}


@router.post(
    "/subscribe",
    response_model=SignupReceived,
    status_code=202,
    dependencies=[Depends(public), Depends(rate_limit(SIGNUPS_PER_IP))],
)
async def subscribe(
    body: NewSubscription,
    request: Request,
    user: Any = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Received, whatever the address's state: nobody learns who's subscribed."""
    await service.subscribe(db, request, body, user_id=service.owner_of(user, body.email))
    await db.commit()
    return {"received": True}


@router.post("/confirm", response_model=SubscriptionLink, dependencies=[Depends(public)])
async def confirm(body: NewsletterConfirm, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The subscription confirmed; 404 for a link the site doesn't know."""
    shown = await service.confirm(db, body.token)
    await db.commit()
    return shown


@router.get("/unsubscribe", response_model=SubscriptionLink, dependencies=[Depends(public)])
async def unsubscribe_link(token: Token, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """What the link would unsubscribe, changing nothing: link scanners open links."""
    return await service.looked_up(db, token)


@router.post("/unsubscribe", response_model=SubscriptionLink, dependencies=[Depends(public)])
async def unsubscribe(token: Token, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """The page's button and RFC 8058's one-click POST alike (no session, no
    Origin: the token is the proof); a second time answers the same."""
    shown = await service.unsubscribe(db, token)
    await db.commit()
    return shown


@router.post(
    "/webhooks/resend", response_model=CampaignWebhookTaken, dependencies=[Depends(public)]
)
async def resend_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    """Resend's bounces and complaints, signed; refused without the secret, or replayed."""
    body = await request.body()
    delivery = webhooks.verified(webhooks.secret_from(), request.headers, body, clock.now())
    if delivery is None:
        raise Problem("campaigns.bad_signature", 401, "This delivery isn't signed by Resend.")
    if not await service.first_time(db, f"resend:{delivery}"):
        raise Problem("campaigns.replayed", 409, "This delivery was taken already.")
    event = webhooks.parsed(body)
    found = webhooks.verdicts(event)
    copies = await service.sent_copies(
        db, webhooks.subject_of(event), [address for address, _ in found]
    )
    await service.apply(db, found, copies)
    await db.commit()
    return {"received": True}


# --- the emails -------------------------------------------------------------------------------


@router.get("/admin/emails", response_model=CampaignEmailsPage, dependencies=[Depends(EMAILS)])
async def list_emails(
    status: EmailTab = "all",
    cursor: Cursor = None,
    limit: Limit = service.PAGE,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The Emails tab, newest first, with the cards and the attention card."""
    return await service.emails_page(db, status, cursor, limit)


@router.post("/admin/emails", response_model=CampaignEmail, status_code=201)
async def create_email(
    body: NewCampaignEmail, user: Any = Depends(EMAILS), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    row = await service.create(db, body, by=user.id)
    shown = await service.full(db, row)
    await db.commit()
    return shown


@router.get(
    "/admin/emails/{email_id}", response_model=CampaignEmail, dependencies=[Depends(EMAILS)]
)
async def read_email(email_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await service.full(db, await service.get(db, email_id))


@router.patch("/admin/emails/{email_id}", response_model=CampaignEmail)
async def change_email(
    email_id: uuid.UUID,
    body: CampaignEmailChange,
    user: Any = Depends(EMAILS),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Saves the fields sent; 409 `campaigns.changed` with the email now when another save came first."""
    row = await service.change(db, email_id, body, by=user.id)
    shown = await service.full(db, row)
    await db.commit()
    return shown


@router.post(
    "/admin/emails/{email_id}/preview",
    response_model=CampaignPreview,
    dependencies=[Depends(EMAILS)],
)
async def preview_email(
    email_id: uuid.UUID, body: CampaignPreviewBody, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """The words and the footer as a subscriber reads them, unsaved words included."""
    row = await service.get(db, email_id)
    return {"html": await service.preview(db, body.body, row.subject, row.preview)}


@router.post(
    "/admin/emails/{email_id}/test",
    response_model=CampaignTestSent,
    dependencies=[Depends(rate_limit(TESTS_PER_PERSON, key="account"))],
)
async def send_test_email(
    email_id: uuid.UUID, user: Any = Depends(EMAILS), db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """To the person asking only, marked [Test], counted nowhere."""
    await service.send_test(db, email_id, to=user.email)
    await db.commit()
    return {"to": user.email}


@router.post("/admin/emails/{email_id}/send", response_model=CampaignEmail)
async def send_email(
    email_id: uuid.UUID,
    body: CampaignSend,
    user: Any = Depends(EMAILS),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Now, or scheduled for `at`; 409 without the postal address or anyone subscribed."""
    row = await service.send(db, email_id, body.at, by=user.id)
    shown = await service.full(db, row)
    await db.commit()
    return shown


@router.post("/admin/emails/{email_id}/cancel", response_model=CampaignEmail)
async def cancel_email(
    email_id: uuid.UUID, user: Any = Depends(EMAILS), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """A scheduled email back to a draft; a sending one stops queueing the rest."""
    row = await service.cancel(db, email_id, by=user.id)
    shown = await service.full(db, row)
    await db.commit()
    return shown


@router.delete("/admin/emails/{email_id}", status_code=204)
async def delete_email(
    email_id: uuid.UUID, user: Any = Depends(EMAILS), db: AsyncSession = Depends(get_db)
) -> Response:
    await service.remove(db, email_id, by=user.id)
    await db.commit()
    return Response(status_code=204)


# --- the people -------------------------------------------------------------------------------


@router.get(
    "/admin/subscribers", response_model=NewsletterSubscribers, dependencies=[Depends(PEOPLE)]
)
async def list_subscribers(
    status: SubscriberTab = "all",
    cursor: Cursor = None,
    limit: Limit = service.PAGE,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await service.subscribers_page(db, status, cursor, limit)


@router.post("/admin/subscribers/{subscriber_id}/set-aside", status_code=204)
async def set_aside(
    subscriber_id: uuid.UUID,
    body: NewsletterSetAside,
    user: Any = Depends(PEOPLE),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """By hand: a bounce nothing reads, or a person who asked to stop some other way."""
    await service.set_aside_by_hand(db, subscriber_id, body.why, body.detail, by=user.id)
    await db.commit()
    return Response(status_code=204)


@router.delete("/admin/subscribers/{subscriber_id}", status_code=204)
async def delete_subscriber(
    subscriber_id: uuid.UUID, user: Any = Depends(PEOPLE), db: AsyncSession = Depends(get_db)
) -> Response:
    """For a person who asks to be forgotten: their address stays set aside."""
    await service.remove_subscriber(db, subscriber_id, by=user.id)
    await db.commit()
    return Response(status_code=204)


@router.get("/admin/set-aside", response_model=SetAsideAddresses, dependencies=[Depends(PEOPLE)])
async def list_set_aside(
    cursor: Cursor = None, limit: Limit = service.PAGE, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await service.set_aside_page(db, cursor, limit)
