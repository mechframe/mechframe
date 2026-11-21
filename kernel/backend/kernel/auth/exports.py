"""The account's export (SPEC.md 14.7; hook 7, decision 0052): a copy of what
the site holds about a person, as a ZIP of JSON.

- `POST /api/auth/account/export` asks for one: a recent sign-in (step-up),
  once an hour, with storage on. It answers 202 at once; the job
  `kernel.privacy_export` makes the copy.
- **The job** collects the kernel's own `kernel.json` (the account, its
  roles and its security activity) and each exporting module's file
  (`kernel.privacy.export`), stores the ZIP in private storage at
  `kernel/exports/<id>.zip`, and mails a link to
  `GET /api/auth/account/exports/{id}`. On its last failed try the copy is
  marked failed and the person is told to ask again.
- **The link** sends the account's own signed-in owner to a 5-minute signed
  download; anyone else, or a copy that isn't ready or has gone, gets 404.
- **A copy goes after 7 days** (`kernel.prune_exports`, hourly), with its file.

Each step is in the person's security activity (`auth.data_export_*`).
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import audit as audit_log
from kernel import clock, email, jobs, privacy, storage
from kernel.answers import Answer, Id
from kernel.auth import audit, mails
from kernel.auth.dependencies import current_user, require_recent_auth
from kernel.auth.models import User
from kernel.auth.permissions import roles_of
from kernel.config import KernelConfig, storage_missing
from kernel.db import get_db
from kernel.email import queue_message
from kernel.errors import Problem
from kernel.models import AuditEvent
from kernel.models import Export as ExportRow
from kernel.ratelimit import rate_limit

log = logging.getLogger(__name__)

router = APIRouter()

#: How often an account may ask (the contract's `rate_limit("1/1h", key="account")`).
EXPORTS_PER_HOUR = "1/1h"
#: How long the signed download works, in seconds.
LINK_SECONDS = 300
#: How long a copy is kept.
KEEP = timedelta(days=7)
#: The job's tries; the last failed one marks the copy failed.
TRIES = 5

_stepped_up = require_recent_auth()


def storage_key(export_id: uuid.UUID) -> str:
    return f"kernel/exports/{export_id}.zip"


def _link(export_id: uuid.UUID) -> str:
    """The mailed link, on SITE_URL as create_app installed it (a job has no request)."""
    return f"{email.site_url()}/api/auth/account/exports/{export_id}"


async def _storage_on(request: Request) -> None:
    """503 `kernel.storage_off` while storage isn't set: there'd be nowhere to keep the copy."""
    if storage_missing(cast(KernelConfig, request.app.state.config)):
        raise Problem(
            "kernel.storage_off",
            503,
            "This site can't keep files yet, so it can't make a copy of your data.",
        )


class ExportAsked(Answer):
    """A copy asked for: the link comes by mail once it's made."""

    id: Id
    status: Literal["queued"]


@router.post(
    "/account/export",
    status_code=202,
    response_model=ExportAsked,
    # Access before the limit (kernel.auth.dependencies): a refused step-up spends nothing.
    dependencies=[
        Depends(_stepped_up),
        Depends(_storage_on),
        Depends(rate_limit(EXPORTS_PER_HOUR, key="account")),
    ],
)
async def ask_for_export(
    request: Request,
    user: User = Depends(_stepped_up),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Asks for a copy of the account's data, mailed as a link once it's made."""
    now = clock.now()
    row = ExportRow(user_id=user.id, status="queued", created_at=now, expires_at=now + KEEP)
    db.add(row)
    await db.flush()
    await jobs.enqueue(db, MAKE.name, {"export_id": str(row.id)})
    audit.record(
        db,
        request,
        "auth.data_export_requested",
        "success",
        actor=user.id,
        subject=user.id,
        details={"export_id": str(row.id)},
    )
    await db.commit()
    return {"id": str(row.id), "status": "queued"}


@router.get(
    "/account/exports/{export_id}",
    response_class=RedirectResponse,
    status_code=303,
    responses={303: {"description": "To a 5-minute signed download of the ZIP"}},
)
async def download_export(
    export_id: uuid.UUID,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Sends the account's own owner to the copy, for 5 minutes; 404 for
    anyone else's, one not made yet, or one that has gone."""
    row = await db.get(ExportRow, export_id)
    if (
        row is None
        or row.user_id != user.id
        or row.status != "ready"
        or row.storage_key is None
        or row.expires_at <= clock.now()
    ):
        raise Problem(
            "auth.export_not_found",
            404,
            "That copy isn't here: a copy goes after 7 days. Ask for a new one on your account page.",
        )
    url = await storage.signed_url(
        row.storage_key,
        expires_in=LINK_SECONDS,
        filename=f"your-data-{row.created_at:%Y-%m-%d}.zip",
    )
    audit.record(
        db,
        request,
        "auth.data_export_downloaded",
        "success",
        actor=user.id,
        subject=user.id,
        details={"export_id": str(row.id)},
    )
    await db.commit()
    return RedirectResponse(url, status_code=303)


# --- the job ---------------------------------------------------------------------------------


async def own_data(db: AsyncSession, user: User) -> privacy.Exported:
    """The kernel's own `kernel.json`: the account, its roles, and its
    security activity as the person reads it (`GET /api/auth/activity`)."""
    activity: list[dict[str, Any]] = []
    where = [AuditEvent.subject_id == user.id, AuditEvent.action.startswith("auth.")]
    cursor = None
    while True:
        page = await audit_log.read(db, where=where, cursor=cursor, limit=500)
        activity.extend(audit_log.own_item(entry, user.id) for entry in page.entries)
        if page.next is None:
            break
        cursor = page.next
    return {
        "account": [
            {
                "id": user.id,
                "email": user.email,
                "name": user.display_name,
                "email_verified_at": user.email_verified_at,
                "created_at": user.created_at,
                "last_sign_in_at": user.last_sign_in_at,
                "status": user.status,
            }
        ],
        "roles": [{"name": name} for name in sorted(await roles_of(db, user.id))],
        "activity": activity,
    }


async def _mail(db: AsyncSession, user: User, name: str, **context: str | int) -> None:
    subject, text, html = mails.rendered(name, **context)
    await queue_message(db, user.email, subject, text, html)


async def _make(ctx: jobs.Context, payload: dict[str, Any]) -> None:
    export_id = uuid.UUID(str(payload["export_id"]))
    try:
        async with ctx.sessions() as db:
            row = await db.get(ExportRow, export_id)
            if row is None or row.status != "queued":
                return  # its account went, or a run before this one finished it
            user = await db.get(User, row.user_id)
            if user is None:
                return  # the row goes with its account
            files = {
                "kernel": await own_data(db, user),
                **await privacy.export(db, privacy.Subject(user.id, user.email)),
            }
            data = privacy.archive(files, at=clock.now())
        # Stored outside any session: an upload holds no connection.
        key = storage_key(export_id)
        await storage.put(key, data, content_type="application/zip", filename="your-data.zip")
        async with ctx.sessions() as db:
            row = await db.get(ExportRow, export_id, with_for_update=True)
            user = await db.get(User, row.user_id) if row is not None else None
            if row is None or user is None:
                await storage.delete(key)  # its account went while it was made
                return
            now = clock.now()
            row.status, row.storage_key, row.expires_at = "ready", key, now + KEEP
            await _mail(
                db,
                user,
                "kernel.data_export_ready",
                link=_link(export_id),
                until=mails.when(row.expires_at),
            )
            audit.record_by_kernel(
                db,
                "auth.data_export_ready",
                "success",
                subject=user.id,
                details={"export_id": str(export_id), "modules": len(files) - 1},
            )
            await db.commit()
    except Exception:
        if ctx.try_number >= TRIES:
            await _failed(ctx, export_id)
        raise


async def _failed(ctx: jobs.Context, export_id: uuid.UUID) -> None:
    """The last try failed: the copy is marked failed and its owner told."""
    async with ctx.sessions() as db:
        row = await db.get(ExportRow, export_id, with_for_update=True)
        if row is None or row.status != "queued":
            return
        user = await db.get(User, row.user_id)
        if user is None:
            return
        row.status = "failed"
        await _mail(db, user, "kernel.data_export_failed")
        audit.record_by_kernel(
            db,
            "auth.data_export_ready",
            "failed",
            subject=user.id,
            details={"export_id": str(export_id)},
        )
        await db.commit()


MAKE = jobs.handler("kernel.privacy_export", tries=TRIES, timeout=1800)(_make)


async def _prune(ctx: jobs.Context) -> None:
    """Deletes the copies past their 7 days, with their files."""
    async with ctx.sessions() as db:
        gone = list(
            (
                await db.execute(
                    select(ExportRow.id, ExportRow.storage_key).where(
                        ExportRow.expires_at <= clock.now()
                    )
                )
            ).all()
        )
    for export_id, key in gone:
        if key is not None:
            await storage.delete(key)
        async with ctx.sessions() as db:
            await db.execute(delete(ExportRow).where(ExportRow.id == export_id))
            await db.commit()


PRUNE = jobs.scheduled("23 * * * *", "kernel.prune_exports")(_prune)
