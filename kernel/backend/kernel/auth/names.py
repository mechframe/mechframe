"""The account's name, at /api/auth (decision 0061; contract
dev plans/contracts/account-name.md; SPEC.md 14.1; docs/contracts/auth-api.md).

`auth_user.display_name` is the name the site shows for a person: the
session's `name`, People, the admin's Activity, blog's bylines and the data
export read it as it is, so nothing keeps a copy to go stale and no event is
emitted.

- **`PUT /account/name`** (signed in, no step-up: a name opens nothing): the
  person's own, ten changes an hour. Answers the session's `{"user"}`.
- **`PUT /admin/users/{id}/name`** (`auth.user.manage`, step-up): someone
  else's, if the caller outranks them by decision 0013's rule
  (`permissions.outranks`), as a suspension does. A suspended person can be
  renamed, so staff can clear an offensive name. Answers the person as People
  lists them.

**The name** (`clean_name`): NFC; each run of whitespace one space, and the
ends trimmed; no control character, and no direction override, embedding or
isolate, which could make a name read as something else in a list; at most
120 characters. Empty is no name. A name that is the same once cleaned
changes nothing and isn't audited.

**Audit:** `auth.name_changed`, the actor whoever changed it and the target
the account. Its details are `{"cleared": true}` for a name removed, and
otherwise empty: the log keeps no name, as it keeps no address.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import audit
from kernel.auth import accounts
from kernel.auth.answers import Person, SessionAnswer
from kernel.auth.dependencies import (
    current_user,
    require_permission,
    require_recent_auth,
    signed_in,
)
from kernel.auth.models import User
from kernel.auth.permissions import outranks
from kernel.auth.roles import people_items
from kernel.auth.sessions import Resumed
from kernel.db import get_db
from kernel.errors import Problem
from kernel.ratelimit import rate_limit

router = APIRouter()

#: The column's length, each code point one character.
MAX_NAME = 120
#: What a request may send, before cleaning: room for spaces at the ends.
MAX_SENT = 240
#: Ten changes an hour, a person's own (the contract's limit).
CHANGES_PER_HOUR = "10/1h"
#: Direction overrides, embeddings and isolates (U+202A to U+202E, U+2066 to U+2069).
_DIRECTION = re.compile("[\u202a-\u202e\u2066-\u2069]")
_SPACES = re.compile(r"\s+")
_REFUSED = "A name is up to 120 characters, on one line."


def clean_name(text: str) -> str | None:
    """The name as it is kept, None for none; ValueError for one refused."""
    name = _SPACES.sub(" ", unicodedata.normalize("NFC", text)).strip()
    if any(unicodedata.category(each) == "Cc" for each in name) or _DIRECTION.search(name):
        raise ValueError(_REFUSED)
    if len(name) > MAX_NAME:
        raise ValueError(_REFUSED)
    return name or None


class NameBody(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str = Field(max_length=MAX_SENT)

    @field_validator("name")
    @classmethod
    def _cleaned(cls, name: str) -> str:
        clean_name(name)  # refused here, so the answer is 422 kernel.invalid_request
        return name

    @property
    def cleaned(self) -> str | None:
        return clean_name(self.name)


def _record(
    db: AsyncSession, request: Request, actor: uuid.UUID, person: uuid.UUID, name: str | None
) -> None:
    audit.record(
        db,
        "auth.name_changed",
        actor=actor,
        target=("auth.user", person),
        subject=person,
        details={"cleared": True} if name is None else {},
        request=request,
    )


@router.put(
    "/account/name",
    response_model=SessionAnswer,
    # Access before the limit (kernel.auth.dependencies): a refused request spends nothing.
    dependencies=[
        Depends(current_user),
        Depends(rate_limit(CHANGES_PER_HOUR, key="account")),
    ],
)
async def set_own_name(
    request: Request,
    body: NameBody,
    user: User = Depends(current_user),
    resumed: Resumed = Depends(signed_in),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The person's own name becomes `name`, or none when it's empty."""
    user = await accounts.held(db, user.id, resumed.session.id)
    name = body.cleaned
    if name != user.display_name:
        user.display_name = name
        _record(db, request, user.id, user.id, name)
        await db.flush()
    shown = await accounts.view(db, user, declared=request.app.state.declared_permissions)
    await db.commit()
    return {"user": shown}


@router.put(
    "/admin/users/{id}/name",
    response_model=Person,
    dependencies=[
        Depends(require_permission("auth.user.manage")),
        Depends(require_recent_auth()),
    ],
)
async def set_name(
    request: Request,
    user_id: Annotated[uuid.UUID, Path(alias="id")],
    body: NameBody,
    actor: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Someone's name becomes `name`, by staff who outrank them."""
    rows = await db.scalars(
        select(User)
        .where(User.id.in_({actor.id, user_id}))
        .order_by(User.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    found = {row.id: row for row in rows}
    person = found.get(user_id)
    if person is None or person.status == "deleted":
        await db.rollback()
        raise Problem("kernel.not_found", 404, "There's no such person.")
    acting = found.get(actor.id)
    if acting is None or acting.status != "active":
        await db.rollback()
        raise Problem("auth.account_not_active", 409, "Your account is no longer active.")
    if person.status not in {"active", "suspended"}:
        await db.rollback()
        raise Problem("auth.account_not_active", 409, "This account is being deleted.")
    if not await outranks(db, actor.id, user_id):
        await db.rollback()
        raise Problem(
            "auth.role_not_yours",
            403,
            "Only an owner changes an owner's name, and anyone else's only someone "
            "holding every permission they hold.",
        )
    name = body.cleaned
    if name != person.display_name:
        person.display_name = name
        _record(db, request, actor.id, user_id, name)
        await db.flush()
    (item,) = await people_items(db, [person])
    await db.commit()
    return item
