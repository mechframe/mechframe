"""What other modules may call (SPEC 7), and only those that list
`audio-player` under requires.modules (`dev plans/contracts/audio-player.md` §2).

A module that hands the player its items counts their plays from its own
public route, which has checked the item is live and playable:

    @router.post("/tracks/{id}/plays", status_code=204, dependencies=[Depends(public), ...])
    async def played(id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
        if await is_playable(db, id):
            await audio_player.count(db, request, source="discography.track", item_id=id)
            await db.commit()

It calls `forget` in the transaction that deletes an item, and reads `plays`
for its own figures. `source` is always `<module>.<type>`.
"""

from __future__ import annotations

from audio_player.service import add_daily, count, forget, plays

__all__ = ["add_daily", "count", "forget", "plays"]
