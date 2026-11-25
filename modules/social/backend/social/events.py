"""The event social hears (SPEC.md section 11, decision 0036).

- `kernel.settings.changed` v1 `{module, version}`, for the section `social`:
  the token may have changed, so the channels checked before `version` are
  forgotten, and a new token is checked before anything is shared. A list
  checked at `version` or since is kept, so a late or second delivery never
  takes a fresh check away (Codex on #152).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from kernel import events, jobs
from social import service


class SettingsChanged(BaseModel):
    """social's view of the kernel's payload."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    module: str
    version: int


async def _changed(ctx: jobs.Context, event: events.Event) -> None:
    heard = event.parse(SettingsChanged)
    if heard.module != service.MODULE:
        return
    async with ctx.sessions() as db:
        await service.forget_channels(db, heard.version)
        await db.commit()


CHANGED = events.on("kernel.settings.changed", "social.settings_changed")(_changed)
