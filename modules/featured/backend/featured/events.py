"""featured's event (SPEC.md section 11): `featured.placement.changed` goes out
on each save of a slot's list, a slot's change and its delete, for a
homepage's cache. A placement's start or end needs none: what's live is worked
out at each read. featured listens to nothing: an item that's gone shows as
removed, read through `kernel.refs`."""

from __future__ import annotations

from kernel import events


@events.payload("featured.placement.changed", v=1)
class PlacementChanged(events.Payload):
    """What a slot holds, or the slot itself, changed."""

    slot_key: str
