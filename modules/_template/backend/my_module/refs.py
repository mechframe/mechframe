"""my-module: what another module may point at (kernel.refs, decision 0072).

Each type of thing another module may pick, list or show as gone (featured's
slots point at tracks and albums) gets a source here. The module that points
stores `{type, id}` and asks `kernel.refs`, so neither requires the other.
For example:

    class Items(refs.Source):
        type = "my-module.item"
        label = "Items"

        async def find(self, db, ids):
            rows = await db.scalars(select(Item).where(Item.id.in_(ids)))
            return {
                item.id: refs.Ref(
                    item.id, item.title, item.summary, None,
                    f"/my-module/{item.slug}" if item.status == "published" else None,
                    item.status == "published",
                )
                for item in rows
            }

        async def pick(self, db, q, *, cursor, limit):
            ...  # newest edit first, matching q, drafts too
            return {"items": [...], "next_cursor": None}

    REFS = (Items(),)

`find` answers drafts too, with `live` saying whether the site shows each now;
an id it leaves out is gone. A module nothing points at deletes this file.
"""

from __future__ import annotations

from kernel import refs

REFS: tuple[refs.Source, ...] = ()
