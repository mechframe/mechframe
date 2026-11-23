"""campaigns: its scheduled jobs (kernel.jobs, decision 0035).

- `campaigns.send`, each minute: starts a scheduled email that's due and
  queues the next copies at the send pace (`sending.run`). Send now queues one
  more run at once.
- `campaigns.bounces`, every 15 minutes while the bounce mailbox's three
  variables are set: reads its bounce and spam reports (`bounces.py`), sets
  the addresses aside, and moves each report to the folder of read ones. A
  mailbox that can't be reached ends the run quietly, a report that can't be
  read stays where it is, and the rest go on.
- `campaigns.prune`, daily at 03:40 UTC: unconfirmed sign-ups after 30 days,
  replay ids after 7.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from campaigns import bounces, sending, service
from kernel import jobs

log = logging.getLogger(__name__)


@jobs.scheduled("* * * * *", "campaigns.send", timeout=240)
async def send(ctx: jobs.Context) -> None:
    async with ctx.sessions() as db:
        queued = await sending.run(db)
        await db.commit()
    if queued:
        log.info("Newsletter copies queued.", extra={"count": queued})


Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def read_mailbox(
    sessions: Sessions,
    login: bounces.Login | None,
    opener: Callable[[bounces.Login], bounces.Mailbox] = bounces.open_mailbox,
) -> int:
    """One read of the bounce mailbox: answers the reports handled. Nothing at
    all without its login."""
    if login is None:
        return 0
    try:
        mailbox = await asyncio.to_thread(opener, login)
    except bounces.UNREACHABLE as error:
        log.warning(
            "The bounce mailbox couldn't be reached.", extra={"error": type(error).__name__}
        )
        return 0
    handled = 0
    try:
        reports = await asyncio.to_thread(mailbox.reports)
        for uid, raw in reports:
            try:
                verdicts = bounces.read_report(raw)
            except Exception as error:  # a report malformed past the parser's care
                log.warning(
                    "A bounce report couldn't be read.", extra={"error": type(error).__name__}
                )
                continue
            if verdicts is None:
                continue
            async with sessions() as db:
                await service.apply(db, verdicts)
                await db.commit()
            try:
                await asyncio.to_thread(mailbox.done, uid)
            except bounces.UNREACHABLE as error:
                # Set aside already; read again next time, which changes nothing more.
                log.warning(
                    "A bounce report couldn't be moved.", extra={"error": type(error).__name__}
                )
                continue
            handled += 1
    except bounces.UNREACHABLE as error:
        log.warning("The bounce mailbox stopped answering.", extra={"error": type(error).__name__})
    finally:
        await asyncio.to_thread(mailbox.close)
    return handled


@jobs.scheduled("*/15 * * * *", "campaigns.bounces", timeout=600)
async def read_bounces(ctx: jobs.Context) -> None:
    handled = await read_mailbox(ctx.sessions, bounces.login_from())
    if handled:
        log.info("Bounce reports read.", extra={"count": handled})


@jobs.scheduled("40 3 * * *", "campaigns.prune")
async def prune(ctx: jobs.Context) -> None:
    async with ctx.sessions() as db:
        gone = await service.prune(db)
        await db.commit()
    if gone:
        log.info("Unconfirmed sign-ups deleted.", extra={"count": gone})
