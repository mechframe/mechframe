"""audio-player's one route (`dev plans/contracts/audio-player.md` §2), mounted
by the kernel at /api/audio-player behind require_module("audio-player").

Plays aren't counted here: the module that handed the player an item counts
it through `public.count`, from its own route, once it has checked the item.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from audio_player import service
from audio_player.schemas import PlayerSettings
from kernel import answer, get_db, public

router = APIRouter()

#: The player reads its settings once a page; a minute old is fine.
CACHE = "public, max-age=60"


@router.get("/settings", response_model=PlayerSettings, dependencies=[Depends(public)])
async def read_settings(db: AsyncSession = Depends(get_db)) -> Response:
    """Whether the next track plays when one ends, and how long a play takes to count.
    Built with `answer`, as a route that sets a header is (SPEC 7)."""
    cfg = await service.current(db)
    content = {"autoplay_next": cfg.autoplay_next, "count_after_seconds": cfg.count_after_seconds}
    return answer(PlayerSettings, content, headers={"Cache-Control": CACHE})
