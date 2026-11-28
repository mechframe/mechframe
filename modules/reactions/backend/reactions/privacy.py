"""Export and erase (hook 7, decision 0052): reactions keeps each press by the
account that made it. Export lists a person's reactions; erase deletes them,
and the counts go down (`dev plans/contracts/reactions.md` §2, Hooks)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import privacy
from reactions.models import Reaction


async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
    rows = await db.scalars(
        select(Reaction)
        .where(Reaction.user_id == subject.user_id)
        .order_by(Reaction.created_at, Reaction.target_type, Reaction.target_id, Reaction.key)
    )
    return {
        "reactions": [
            {
                "thing": f"{row.target_type} {row.target_id}",
                "reaction": row.key,
                "reacted_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
    await db.execute(delete(Reaction).where(Reaction.user_id == subject.user_id))
