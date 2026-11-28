"""reactions' scheduled job (kernel.jobs, decision 0035).

`reactions.sweep` runs weekly, Sundays at 03:40 UTC. It deletes the reactions
of things that are gone, asking `kernel.refs` 200 at a time; a thing that's
only hidden keeps them, and a type that's off is skipped
(`dev plans/contracts/reactions.md` §2, Jobs). Run twice, it deletes nothing more.
"""

from __future__ import annotations

import logging

from kernel import jobs
from reactions import service

log = logging.getLogger(__name__)


@jobs.scheduled("40 3 * * 0", "reactions.sweep")
async def sweep(ctx: jobs.Context) -> None:
    async with ctx.sessions() as db:
        gone = await service.sweep(db)
        await db.commit()
    if gone:
        log.info("Reactions of things that are gone deleted.", extra={"count": gone})
