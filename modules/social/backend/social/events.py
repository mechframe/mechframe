"""The event social hears (SPEC.md section 11, decision 0036).

- `kernel.settings.changed` v1 `{module, version}`, for the section `social`:
  the token may have changed, so the channels the old one reached are
  forgotten, and a new token is checked before anything is shared. Clearing
  twice changes nothing more.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from kernel import events, jobs
from social import service


class SettingsChanged(BaseModel):
    """social's view of the kernel's payload."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    module: str


async def _changed(ctx: jobs.Context, event: events.Event) -> None:
    if event.parse(SettingsChanged).module != service.MODULE:
        return
    async with ctx.sessions() as db:
        await service.forget_channels(db)
        await db.commit()


CHANGED = events.on("kernel.settings.changed", "social.settings_changed")(_changed)
