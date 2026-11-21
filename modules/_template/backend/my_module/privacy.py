"""my-module: what it holds about a person (kernel.privacy, hook 7, decision 0052).

The kernel calls these for the account's export (SPEC.md 14.7: a ZIP of
JSON, one file per module) and, once K2's step 11 lands, for its deletion.
module.json's `data_hooks` says which this module gives: the start refuses
a manifest and a file that disagree. A module that holds nothing about
anyone deletes this file and sets both to false.

`subject` is `kernel.privacy.Subject`, `{user_id, email}`: match by
`user_id` for what an account made, and by `email` (case-insensitively)
for what was sent by address, such as a contact form's inquiry. For example:

    async def export_user_data(db: AsyncSession, subject: privacy.Subject) -> privacy.Exported:
        items = await db.scalars(select(Item).where(Item.author_id == subject.user_id))
        return {"items": [{"id": str(item.id), "title": item.title} for item in items]}

    async def delete_user_data(db: AsyncSession, subject: privacy.Subject) -> None:
        await db.execute(delete(Item).where(Item.author_id == subject.user_id))

An export answers lists of JSON objects by name. A deletion removes or
anonymises the rows in the caller's transaction, and never commits.
"""

from __future__ import annotations

from typing import Any

from kernel import privacy


async def export_user_data(db: Any, subject: privacy.Subject) -> privacy.Exported:
    return {"items": []}


async def delete_user_data(db: Any, subject: privacy.Subject) -> None:
    return None
