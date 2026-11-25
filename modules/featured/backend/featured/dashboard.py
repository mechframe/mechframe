"""Dashboard parts (hook 8, decision 0052). "Needs you" warns two days before a
Dashboard slot goes empty: something's live, all of it ends by then, and
nothing is scheduled after. Setup asks for something live in each player."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from featured import service
from kernel import attention, setup

PLACE = "featured.placement.manage"


def _day(at: Any) -> str:
    """ "Nov 17", in UTC, as the server keeps it."""
    return f"{at:%b} {at.day}"


async def _attention(db: AsyncSession, user: Any) -> list[attention.Item]:
    items: list[attention.Item] = []
    for each in await service.ending_soon(db):
        days = service.days_left(each.last_end)
        when = "in 1 day" if days == 1 else f"in {days} days"
        items.append(
            attention.Item(
                key=f"featured.ending_{each.slot.key.replace('-', '_')}",
                tone="info",
                what=f"{each.title} leaves the {each.slot.label} {when}",
                why=(
                    f"After {_day(each.last_end)} the {each.slot.label} is empty on the site "
                    "unless something else is scheduled."
                ),
                label="Schedule the next one",
                to=f"/admin/featured?slot={each.slot.key}",
                permission=PLACE,
            )
        )
    return items


ATTENTION = _attention
SETUP: tuple[Any, ...] = (
    setup.Step(
        key="featured.players",
        title="Put something in each homepage player",
        why=(
            "Each homepage player shows only what's live in it now. "
            "Choose what each one plays, in order, on Players."
        ),
        link="/admin/featured",
        permission=PLACE,
        done=service.every_slot_live,
    ),
)
