"""All of featured's logic (`dev plans/contracts/featured.md` §2); the routes
call these with a session and typed arguments.

**What's live** is worked out at each read, with no job: a placement is live
while `starts_at <= now < ends_at`, an open end counting as always, and an
item only while its source says it's `live`. Its state on Players:

- `removed`: its source hasn't got it any more;
- `ended`: its end has passed;
- `hidden`: its item isn't on the site, or its module is off (`refs.UnknownType`);
- `live`, else `next` for the soonest to start and `scheduled` for the rest.

**A save** is the whole list, checked against the `version` it read under
the slot's lock: two saves of one slot at once make one version, and the
other answers 409 `featured.changed` with the slot as it is now. A kept
placement whose module is off is kept as it is; one whose item is gone is
left out.
"""

from __future__ import annotations

import json
import math
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from featured import youtube
from featured.events import PlacementChanged
from featured.models import (
    MAX_LABEL,
    MAX_PLACEMENTS,
    MAX_TITLE,
    YOUTUBE,
    Placement,
    Slot,
)
from featured.schemas import KindIn, PlacementIn, Settings
from kernel import Problem, audit, clock, events, refs
from kernel import settings as module_settings  # the kernel's settings store, not featured's model

MODULE = "featured"
SLOT = "featured.slot"
#: How far ahead the Dashboard warns that a slot goes empty.
WARN_AHEAD = timedelta(days=2)
#: Audit details stay under the kernel's 4 KiB with the slot's key around them.
_AUDIT_ROOM = 3600


# --- small parts -----------------------------------------------------------------------------


def _when(at: datetime | None) -> str | None:
    return at.isoformat() if at else None


def _invalid(field: str, code: str, message: str) -> Problem:
    return Problem(code, 422, message, errors={field: [message]})


def _uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise _invalid(field, "kernel.invalid_request", "That isn't an id.") from None


def _at(text: str | None, field: str) -> datetime | None:
    if text is None:
        return None
    try:
        at: datetime | None = datetime.fromisoformat(text)
    except ValueError:
        at = None
    if at is None or at.utcoffset() is None:
        raise _invalid(
            field,
            "kernel.invalid_request",
            "A time with its zone, such as 2026-12-01T00:00:00-05:00.",
        )
    return at


def _line(text: str) -> str:
    """One line, its runs of space made one."""
    return " ".join(text.split())


async def settings_of(db: AsyncSession) -> Settings:
    return cast(Settings, await module_settings.for_module(db, MODULE))


def slot_not_found() -> Problem:
    return Problem("featured.slot_not_found", 404, "There's no player with that key.")


async def get_slot(db: AsyncSession, key: str, *, lock: bool = False) -> Slot:
    statement = select(Slot).where(Slot.key == key)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    found = await db.scalar(statement)
    if found is None:
        raise slot_not_found()
    return found


async def _placements(db: AsyncSession, key: str) -> list[Placement]:
    found = await db.scalars(
        select(Placement).where(Placement.slot_key == key).order_by(Placement.position)
    )
    return list(found)


# --- what each placement is now --------------------------------------------------------------


@dataclass(frozen=True)
class _Off:
    """A placement whose module is off: its type is no module's that's on."""


OFF = _Off()
#: What `kernel.refs` answered for an item: it, None for gone, or OFF.
Found = refs.Ref | _Off | None


async def _look_up(
    db: AsyncSession, wanted: Iterable[tuple[str, uuid.UUID]]
) -> dict[tuple[str, uuid.UUID], Found]:
    """Each item through its type's source, one `refs.find` a type."""
    by_type: dict[str, list[uuid.UUID]] = defaultdict(list)
    for kind, ident in dict.fromkeys(wanted):
        by_type[kind].append(ident)
    answered: dict[tuple[str, uuid.UUID], Found] = {}
    for kind, ids in by_type.items():
        try:
            found = await refs.find(db, kind, ids)
        except refs.UnknownType:
            answered.update({(kind, each): OFF for each in ids})
            continue
        answered.update({(kind, each): found.get(each) for each in ids})
    return answered


def _timed(placement: Placement, now: datetime) -> str:
    if placement.ends_at is not None and placement.ends_at <= now:
        return "ended"
    if placement.starts_at is not None and placement.starts_at > now:
        return "upcoming"
    return "live"


@dataclass
class _Seen:
    placement: Placement
    found: Found
    state: str

    @property
    def title(self) -> str:
        if isinstance(self.found, refs.Ref):
            return self.found.title
        return self.placement.title or ""


def _states(
    placements: Sequence[Placement], found: Mapping[Any, Found], now: datetime
) -> list[_Seen]:
    seen: list[_Seen] = []
    for placement in placements:
        item: Found = None
        if placement.ref_type is not None and placement.ref_id is not None:
            item = found.get((placement.ref_type, placement.ref_id))
            if item is None:
                seen.append(_Seen(placement, None, "removed"))
                continue
        timed = _timed(placement, now)
        if timed == "ended":
            state = "ended"
        elif item is OFF or (isinstance(item, refs.Ref) and not item.live):
            state = "hidden"
        else:
            state = timed
        seen.append(_Seen(placement, item, state))
    upcoming = [each for each in seen if each.state == "upcoming"]
    soonest = min(
        upcoming,
        key=lambda each: cast(datetime, each.placement.starts_at),
        default=None,
    )
    for each in upcoming:
        each.state = "next" if each is soonest else "scheduled"
    return seen


async def _seen(db: AsyncSession, placements: Sequence[Placement], now: datetime) -> list[_Seen]:
    wanted = [
        (each.ref_type, each.ref_id)
        for each in placements
        if each.ref_type is not None and each.ref_id is not None
    ]
    return _states(placements, await _look_up(db, wanted), now)


# --- answers ---------------------------------------------------------------------------------


def _kinds(slot: Slot) -> list[dict[str, str]]:
    return [{"key": each["key"], "label": each["label"]} for each in slot.kinds]


def _link(placement: Placement) -> dict[str, Any] | None:
    if placement.url is None:
        return None
    return {
        "url": placement.url,
        "video_id": placement.video_id,
        "title": placement.title,
        "kind": placement.kind,
    }


def _ref(ref: refs.Ref, kind: str) -> dict[str, Any]:
    return {
        "type": kind,
        "id": str(ref.id),
        "title": ref.title,
        "line": ref.line,
        "image": ref.image,
        "path": ref.path,
    }


def _admin_ref(ref: refs.Ref, kind: str) -> dict[str, Any]:
    return {**_ref(ref, kind), "live": ref.live}


def _admin_placement(each: _Seen) -> dict[str, Any]:
    placement = each.placement
    item = (
        {"type": placement.ref_type, "id": str(placement.ref_id)}
        if placement.ref_type is not None
        else None
    )
    return {
        "id": str(placement.id),
        "item": item,
        "ref": (
            _admin_ref(each.found, cast(str, placement.ref_type))
            if isinstance(each.found, refs.Ref)
            else None
        ),
        "removed": each.state == "removed",
        "link": _link(placement),
        "starts_at": _when(placement.starts_at),
        "ends_at": _when(placement.ends_at),
        "state": each.state,
    }


def _summary(slot: Slot, seen: Sequence[_Seen]) -> dict[str, Any]:
    live = [each for each in seen if each.state == "live"]
    first = live[0] if live else None
    return {
        "key": slot.key,
        "label": slot.label,
        "accepts": list(slot.accepts),
        "kinds": _kinds(slot),
        "on_dashboard": slot.on_dashboard,
        "version": slot.version,
        "counts": {
            "live": len(live),
            "scheduled": sum(1 for each in seen if each.state in ("next", "scheduled")),
        },
        "now": (
            {
                "title": first.title,
                "starts_at": _when(first.placement.starts_at),
                "ends_at": _when(first.placement.ends_at),
            }
            if first
            else None
        ),
    }


async def full_slot(db: AsyncSession, slot: Slot) -> dict[str, Any]:
    seen = await _seen(db, await _placements(db, slot.key), clock.now())
    return {**_summary(slot, seen), "items": [_admin_placement(each) for each in seen]}


async def every_slot(db: AsyncSession) -> dict[str, Any]:
    """Every slot in the order they were made, and the types a slot may take."""
    slots = list(await db.scalars(select(Slot).order_by(Slot.position, Slot.created_at)))
    now = clock.now()
    items = [
        _summary(slot, await _seen(db, await _placements(db, slot.key), now)) for slot in slots
    ]
    types = await refs.types(db)
    return {
        "items": items,
        "types": [{"type": kind, "label": label} for kind, label in types.items()],
    }


async def live_slot(db: AsyncSession, key: str) -> dict[str, Any] | None:
    """What `GET /slots/{key}` answers: what's live now, in order; None for no slot."""
    slot = await db.scalar(select(Slot).where(Slot.key == key))
    if slot is None:
        return None
    seen = await _seen(db, await _placements(db, key), clock.now())
    items: list[dict[str, Any]] = []
    for each in seen:
        if each.state != "live":
            continue
        placement = each.placement
        items.append(
            {
                "id": str(placement.id),
                "ref": (
                    _ref(each.found, cast(str, placement.ref_type))
                    if isinstance(each.found, refs.Ref)
                    else None
                ),
                "link": _link(placement),
            }
        )
    return {"key": slot.key, "label": slot.label, "kinds": _kinds(slot), "items": items}


def _changed(extra: dict[str, Any]) -> Problem:
    return Problem(
        "featured.changed",
        409,
        "Someone saved this player since you opened it. Here is how it reads now.",
        extra=extra,
    )


async def _said(db: AsyncSession, key: str) -> None:
    await events.emit(db, "featured.placement.changed", PlacementChanged(slot_key=key))


# --- slots -----------------------------------------------------------------------------------


def _check_kinds(kinds: Sequence[KindIn], field: str) -> list[dict[str, str]]:
    made: list[dict[str, str]] = []
    keys: set[str] = set()
    for index, each in enumerate(kinds):
        label = _line(each.label)
        if not label:
            raise _invalid(
                f"{field}.{index}.label", "kernel.invalid_request", "A kind needs a name."
            )
        if each.key in keys:
            raise _invalid(
                f"{field}.{index}.key", "kernel.invalid_request", "Each kind has its own key."
            )
        keys.add(each.key)
        made.append({"key": each.key, "label": label})
    return made


async def _check_accepts(
    db: AsyncSession, accepts: Sequence[str], *, kept: Iterable[str] = ()
) -> list[str]:
    """`accepts` with each given once: every one a type a module on gives,
    or "youtube", or one the slot took already (its module may be off now)."""
    known = set(await refs.types(db)) | {YOUTUBE} | set(kept)
    wanted = list(dict.fromkeys(accepts))
    for index, kind in enumerate(wanted):
        if kind not in known:
            raise _invalid(
                f"accepts.{index}",
                "featured.unknown_type",
                f"No module that's on gives {kind}, so a player can't take it.",
            )
    return wanted


def _label(text: str, field: str = "label") -> str:
    label = _line(text)
    if not 1 <= len(label) <= MAX_LABEL:
        raise _invalid(
            field, "kernel.invalid_request", "A player needs a name of 1 to 60 characters."
        )
    return label


async def create_slot(
    db: AsyncSession,
    key: str,
    label: str,
    accepts: Sequence[str],
    kinds: Sequence[KindIn],
    on_dashboard: bool | None,
    *,
    by: uuid.UUID | None,
) -> Slot:
    """A new slot, its tab after the others'. 409 `featured.key_taken`."""
    name = _label(label)
    taken = await _check_accepts(db, accepts)
    made_kinds = _check_kinds(kinds, "kinds")
    if await db.scalar(select(Slot.key).where(Slot.key == key)) is not None:
        raise _taken()
    last = await db.scalar(select(func.max(Slot.position)))
    first = last is None
    now = clock.now()
    slot = Slot(
        key=key,
        label=name,
        accepts=taken,
        kinds=made_kinds,
        on_dashboard=first if on_dashboard is None else on_dashboard,
        position=0 if last is None else last + 1,
        version=1,
        created_at=now,
        updated_at=now,
    )
    try:
        async with db.begin_nested():
            db.add(slot)
            await db.flush()
    except IntegrityError:
        raise _taken() from None
    audit.record(
        db,
        "featured.slot.created",
        actor=by,
        target=(SLOT, key),
        # Never the label: a name may hold an `@`, which the audit refuses as an
        # address (Codex on #157). The key, its target, is a slug.
        details={
            "accepts": taken,
            "kinds": [each["key"] for each in made_kinds],
            "on_dashboard": slot.on_dashboard,
        },
    )
    return slot


def _taken() -> Problem:
    return Problem(
        "featured.key_taken",
        409,
        "Another player has that key.",
        errors={"key": ["Another player has that key."]},
    )


async def change_slot(
    db: AsyncSession,
    key: str,
    version: int,
    fields: Mapping[str, Any],
    *,
    by: uuid.UUID | None,
) -> Slot:
    """Saves the fields sent. 409 `featured.changed` on a stale `version`, and
    `featured.in_use` for a type or a kind a placement still uses."""
    slot = await get_slot(db, key, lock=True)
    if version != slot.version:
        raise _changed({"slot": await full_slot(db, slot)})
    placements = await _placements(db, key)
    changed: dict[str, Any] = {}
    if fields.get("label") is not None:
        slot.label = _label(fields["label"])
        changed["label"] = True  # that it changed, not to what (see create_slot)
    if fields.get("accepts") is not None:
        accepts = await _check_accepts(db, fields["accepts"], kept=slot.accepts)
        for kind in set(slot.accepts) - set(accepts):
            used = any(
                (each.url is not None) if kind == YOUTUBE else each.ref_type == kind
                for each in placements
            )
            if used:
                raise _in_use(
                    "accepts",
                    "YouTube links" if kind == YOUTUBE else kind,
                )
        slot.accepts = accepts
        changed["accepts"] = accepts
    if fields.get("kinds") is not None:
        kinds = _check_kinds([KindIn.model_validate(each) for each in fields["kinds"]], "kinds")
        left = {each["key"] for each in kinds}
        for each in placements:
            if each.kind is not None and each.kind not in left:
                raise _in_use("kinds", f"the kind {each.kind}")
        slot.kinds = kinds
        changed["kinds"] = [each["key"] for each in kinds]
    if fields.get("on_dashboard") is not None:
        slot.on_dashboard = bool(fields["on_dashboard"])
        changed["on_dashboard"] = slot.on_dashboard
    slot.version += 1
    slot.updated_at = clock.now()
    await db.flush()
    await _said(db, key)
    audit.record(db, "featured.slot.changed", actor=by, target=(SLOT, key), details=changed)
    return slot


def _in_use(field: str, what: str) -> Problem:
    message = f"Something in this player is still {what}. Remove it from the list first."
    return Problem("featured.in_use", 409, message, errors={field: [message]})


async def remove_slot(db: AsyncSession, key: str, *, by: uuid.UUID | None) -> None:
    """Gone, with its placements."""
    slot = await get_slot(db, key, lock=True)
    await db.execute(delete(Placement).where(Placement.slot_key == key))
    await db.delete(slot)
    await db.flush()
    await _said(db, key)
    audit.record(db, "featured.slot.deleted", actor=by, target=(SLOT, key))


# --- the list --------------------------------------------------------------------------------


@dataclass
class _Wanted:
    """One row of a save, checked: what it will hold, and where it was."""

    index: int
    kept: Placement | None
    ref: tuple[str, uuid.UUID] | None
    link: tuple[str, str, str, str | None] | None
    starts_at: datetime | None
    ends_at: datetime | None

    @property
    def same_item(self) -> bool:
        """It keeps the item its placement already held."""
        return (
            self.kept is not None
            and self.ref is not None
            and (self.kept.ref_type, self.kept.ref_id) == self.ref
        )


def _check_row(slot: Slot, index: int, item: PlacementIn, kept: Placement | None) -> _Wanted:
    where = f"items.{index}"
    if (item.ref is None) == (item.link is None):
        raise _invalid(where, "kernel.invalid_request", "Each one is an item or a link.")
    starts_at = _at(item.starts_at, f"{where}.starts_at")
    ends_at = _at(item.ends_at, f"{where}.ends_at")
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise _invalid(
            f"{where}.ends_at", "featured.bad_dates", "Its end has to be after its start."
        )
    if item.ref is not None:
        kind = item.ref.type
        if kind == YOUTUBE or kind not in slot.accepts:
            raise _invalid(
                f"{where}.ref", "featured.not_accepted", f"This player doesn't take {kind}."
            )
        return _Wanted(
            index, kept, (kind, _uuid(item.ref.id, f"{where}.ref.id")), None, starts_at, ends_at
        )
    link = cast(Any, item.link)
    if YOUTUBE not in slot.accepts:
        raise _invalid(f"{where}.link", "featured.not_accepted", "This player doesn't take links.")
    ident = youtube.video_id(link.url.strip())
    if ident is None:
        raise _invalid(
            f"{where}.link.url", "featured.not_youtube", "That isn't a YouTube video's link."
        )
    title = _line(link.title)
    if not 1 <= len(title) <= MAX_TITLE:
        raise _invalid(
            f"{where}.link.title",
            "featured.no_title",
            "A video needs a title of 1 to 200 characters.",
        )
    if link.kind is not None and link.kind not in {each["key"] for each in slot.kinds}:
        raise _invalid(
            f"{where}.link.kind", "featured.unknown_kind", "This player has no kind by that key."
        )
    return _Wanted(
        index, kept, None, (youtube.watch(ident), ident, title, link.kind), starts_at, ends_at
    )


async def _check_items(db: AsyncSession, wanted: list[_Wanted]) -> list[_Wanted]:
    """The rows whose items are there, looked up through `kernel.refs`. A kept
    item whose module is off stays as it is, and one that's gone is left out;
    a new one must be there: `featured.not_accepted` while its module is off,
    `featured.not_found` once its source hasn't got it."""
    found = await _look_up(db, [each.ref for each in wanted if each.ref is not None])
    kept: list[_Wanted] = []
    for each in wanted:
        if each.ref is None:
            kept.append(each)
            continue
        item = found[each.ref]
        if item is OFF:
            if not each.same_item:
                raise _invalid(
                    f"items.{each.index}.ref",
                    "featured.not_accepted",
                    f"{each.ref[0]}'s module is off, so it can't be added now.",
                )
        elif item is None:
            if each.same_item:
                continue
            raise _invalid(
                f"items.{each.index}.ref.id",
                "featured.not_found",
                "That item isn't there any more.",
            )
        kept.append(each)
    return kept


def _audit_list(rows: Sequence[Placement]) -> dict[str, Any]:
    """The saved list as the audit log keeps it, cut short to fit its 4 KiB."""
    listed: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = (
            {"ref": f"{row.ref_type}:{row.ref_id}"}
            if row.ref_type is not None
            else {"video": row.video_id}
        )
        if row.starts_at is not None:
            entry["starts_at"] = row.starts_at.isoformat()
        if row.ends_at is not None:
            entry["ends_at"] = row.ends_at.isoformat()
        if len(json.dumps([*listed, entry])) > _AUDIT_ROOM:
            break
        listed.append(entry)
    details: dict[str, Any] = {"count": len(rows), "items": listed}
    if len(listed) < len(rows):
        details["more"] = len(rows) - len(listed)
    return details


async def save_placements(
    db: AsyncSession,
    key: str,
    version: int,
    items: Sequence[PlacementIn],
    *,
    by: uuid.UUID | None,
) -> Slot:
    """The whole list in one save, live at once."""
    if len(items) > MAX_PLACEMENTS:
        raise _invalid(
            "items", "featured.too_many", f"A player holds {MAX_PLACEMENTS} things at most."
        )
    slot = await get_slot(db, key, lock=True)
    if version != slot.version:
        raise _changed({"slot": await full_slot(db, slot)})
    there = {each.id: each for each in await _placements(db, key)}
    wanted: list[_Wanted] = []
    claimed: set[uuid.UUID] = set()
    for index, item in enumerate(items):
        kept = None
        if item.id is not None:
            ident = _uuid(item.id, f"items.{index}.id")
            kept = there.get(ident)
            if kept is None or ident in claimed:
                raise _invalid(
                    f"items.{index}.id",
                    "kernel.invalid_request",
                    "That placement isn't in this player, or is listed twice.",
                )
            claimed.add(ident)
        wanted.append(_check_row(slot, index, item, kept))
    wanted = await _check_items(db, wanted)
    now = clock.now()
    keep_ids = {each.kept.id for each in wanted if each.kept is not None}
    gone = [ident for ident in there if ident not in keep_ids]
    if gone:
        await db.execute(delete(Placement).where(Placement.id.in_(gone)))
    rows: list[Placement] = []
    for position, each in enumerate(wanted):
        row = each.kept or Placement(id=uuid.uuid4(), slot_key=key, created_at=now)
        if each.same_item:
            pass  # the same item: its type and id stay as they are
        elif each.ref is not None:
            row.ref_type, row.ref_id = each.ref
            row.url = row.video_id = row.title = row.kind = None
        else:
            url, video, title, kind = cast(tuple[str, str, str, str | None], each.link)
            row.ref_type, row.ref_id = None, None
            row.url, row.video_id, row.title, row.kind = url, video, title, kind
        row.position = position
        row.starts_at, row.ends_at = each.starts_at, each.ends_at
        row.updated_at = now
        if each.kept is None:
            db.add(row)
        rows.append(row)
    slot.version += 1
    slot.updated_at = now
    await db.flush()
    await _said(db, key)
    audit.record(db, "featured.slot.saved", actor=by, target=(SLOT, key), details=_audit_list(rows))
    return slot


# --- the picker and the links ----------------------------------------------------------------


async def choices(
    db: AsyncSession, key: str, kind: str, q: str | None, cursor: str | None
) -> dict[str, Any]:
    """A page of `kind`'s things to add, through `kernel.refs.pick`."""
    slot = await get_slot(db, key)
    refused = _invalid("type", "featured.not_accepted", f"This player doesn't take {kind}.")
    if kind == YOUTUBE or kind not in slot.accepts:
        raise refused
    try:
        page = await refs.pick(db, kind, q, cursor=cursor)
    except refs.UnknownType:
        raise refused from None
    except ValueError:
        raise _invalid("cursor", "kernel.invalid_request", "Not a page of these things.") from None
    return {
        "items": [_admin_ref(each, kind) for each in page["items"]],
        "next_cursor": page["next_cursor"],
    }


async def pasted(db: AsyncSession, urls: Sequence[str]) -> dict[str, Any]:
    """Each link read as a YouTube video, titled from YouTube while
    `oembed_titles` is on; the others refused."""
    found: list[tuple[str, str]] = []
    refused: list[dict[str, str]] = []
    for url in urls:
        ident = youtube.video_id(url.strip())
        if ident is None:
            refused.append({"url": url, "reason": "featured.not_youtube"})
        else:
            found.append((url, ident))
    titled: dict[str, str | None] = {}
    if found and (await settings_of(db)).oembed_titles:
        titled = await youtube.titles(ident for _, ident in found)
    return {
        "items": [
            {"url": youtube.watch(ident), "video_id": ident, "title": titled.get(ident)}
            for _, ident in found
        ],
        "refused": refused,
    }


# --- the Dashboard ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ending:
    """A Dashboard slot that goes empty soon: the first live thing, the last
    end among what's live, and the slot."""

    slot: Slot
    title: str
    last_end: datetime


async def ending_soon(db: AsyncSession) -> list[Ending]:
    """Each Dashboard slot with something live, whose live things all end within
    two days, with nothing scheduled after."""
    now = clock.now()
    found: list[Ending] = []
    for slot in await db.scalars(
        select(Slot).where(Slot.on_dashboard.is_(True)).order_by(Slot.position)
    ):
        seen = await _seen(db, await _placements(db, slot.key), now)
        live = [each for each in seen if each.state == "live"]
        if not live or any(each.state in ("next", "scheduled") for each in seen):
            continue
        ends = [each.placement.ends_at for each in live]
        if any(end is None for end in ends):
            continue
        last = max(cast(list[datetime], ends))
        if last - now <= WARN_AHEAD:
            found.append(Ending(slot, live[0].title, last))
    return found


def days_left(until: datetime) -> int:
    """Whole days to `until`, from now, at least one."""
    return max(1, math.ceil((until - clock.now()) / timedelta(days=1)))


async def every_slot_live(db: AsyncSession) -> bool:
    """There's a slot, and every slot has something live."""
    slots = list(await db.scalars(select(Slot)))
    if not slots:
        return False
    now = clock.now()
    for slot in slots:
        seen = await _seen(db, await _placements(db, slot.key), now)
        if not any(each.state == "live" for each in seen):
            return False
    return True
