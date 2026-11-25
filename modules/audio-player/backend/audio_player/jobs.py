"""audio-player's scheduled job (kernel.jobs, decision 0035).

`audio-player.prune` runs daily at 03:15 UTC. It deletes the salts and the
counted listeners of days before today, so no hash can be traced back, and
daily totals older than two years (`dev plans/contracts/audio-player.md` §8, 3).
Run twice, it deletes nothing more.
"""

from __future__ import annotations

import logging

from audio_player import service
from kernel import jobs

log = logging.getLogger(__name__)


@jobs.scheduled("15 3 * * *", "audio-player.prune")
async def prune(ctx: jobs.Context) -> None:
    async with ctx.sessions() as db:
        gone = await service.prune(db)
        await db.commit()
    if gone:
        log.info("Old plays pruned.", extra={"count": gone})
