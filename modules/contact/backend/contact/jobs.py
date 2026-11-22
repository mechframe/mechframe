"""contact: its scheduled job (kernel.jobs, decision 0035).

`contact.prune` runs daily at 03:20 UTC: spam goes 30 days after it was set
apart, and every other message 2 years after its last change (the owner's
answer, `dev plans/contracts/contact.md` §8, 3). Run twice, it deletes
nothing more.
"""

from __future__ import annotations

import logging

from contact import service
from kernel import jobs

log = logging.getLogger(__name__)


@jobs.scheduled("20 3 * * *", "contact.prune")
async def prune(ctx: jobs.Context) -> None:
    async with ctx.sessions() as db:
        gone = await service.prune(db)
        await db.commit()
    if gone:
        log.info("Old contact messages deleted.", extra={"count": gone})
