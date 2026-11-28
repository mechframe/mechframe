"""reactions' routes (`dev plans/contracts/reactions.md` §2), mounted by the
kernel at /api/reactions behind require_module("reactions"). Reading the
counts is public; adding a reaction needs a member who may post now, and
taking one back a member. Both spend REACTIONS_RATE_LIMIT, one budget."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import answer, current_user, get_db, moderation, optional_user, rate_limit, refs
from reactions import service
from reactions.models import KEY, MAX_KEY
from reactions.schemas import MAX_IDS, Counted, Reactions

router = APIRouter()

TYPE = f"^{refs.TYPE.pattern}$"
ContentType = Annotated[str, Query(min_length=3, max_length=refs.MAX_TYPE, pattern=TYPE)]
PathType = Annotated[str, Path(min_length=3, max_length=refs.MAX_TYPE, pattern=TYPE)]
Key = Annotated[str, Path(min_length=1, max_length=MAX_KEY, pattern=KEY)]
Ids = Annotated[list[uuid.UUID], Query(alias="id", min_length=1, max_length=MAX_IDS)]


async def budget(request: Request) -> None:
    """One press against REACTIONS_RATE_LIMIT, which adding and taking back share."""
    await rate_limit(service.rate_rule(), key="account", scope="reactions.write")(request)


@router.get("", response_model=Reactions)
async def read(
    type: ContentType,
    ids: Ids,
    person: Any = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The palette, and the counts of the things asked about that are live now:
    never stored by a cache, since `mine` is the reader's own."""
    found = await service.counted(db, type, ids, person)
    return answer(Reactions, found, headers={"Cache-Control": "no-store"})


@router.put("/{type}/{id}/{key}", response_model=Counted)
async def react(
    type: PathType,
    id: uuid.UUID,
    key: Key,
    person: Any = Depends(moderation.can_post),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Adds the person's reaction: pressing twice adds one."""
    found = await service.react(db, person, type, id, key)
    await db.commit()
    return found


@router.delete("/{type}/{id}/{key}", response_model=Counted)
async def unreact(
    type: PathType,
    id: uuid.UUID,
    key: Key,
    person: Any = Depends(current_user),
    __: None = Depends(budget),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Takes the person's reaction back; one that isn't there is fine."""
    found = await service.unreact(db, person, type, id, key)
    await db.commit()
    return found
