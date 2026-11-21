"""my-module: its Dashboard parts (kernel.attention and kernel.setup, hook 8, decision 0052).

`SETUP` lists what an admin sets up before the module works, each a
`setup.Step`: the Dashboard's Set up card shows them while any is open, each
`done` checked as the card is read. `ATTENTION` adds the module's items to
"Needs you": what's wrong, why it matters and the page that fixes it, each
naming the permission a person needs to see it. For example:

    from kernel import attention, setup

    async def _connected(db: AsyncSession) -> bool:
        return bool((await settings.for_module(db, "my-module")).api_key)

    SETUP = (
        setup.Step(
            key="my-module.connect",
            title="Connect the service",
            why="Until it's connected, nothing is sent.",
            link="/admin/settings/my-module",
            permission="kernel.settings.manage",
            done=_connected,
        ),
    )

    async def _attention(db: AsyncSession, user: User) -> list[attention.Item]:
        waiting = await db.scalar(select(func.count()).select_from(Item).where(Item.held))
        if not waiting:
            return []
        return [attention.Item(key="my-module.held", tone="warning", what=f"{waiting} items held",
                               why="Nobody sees them until someone looks.", label="Review them",
                               to="/admin/my-module", permission="my-module.item.manage")]

    ATTENTION = _attention

A module with nothing to set up or flag leaves both as they are, or deletes
this file.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

ATTENTION: Callable[[Any, Any], Awaitable[list[Any]]] | None = None
SETUP: tuple[Any, ...] = ()
