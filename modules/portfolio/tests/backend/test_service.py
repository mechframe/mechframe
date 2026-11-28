"""portfolio's rules on the database (`dev plans/contracts/portfolio.md` §2,
§3, §7): who may change a piece (decision 0074), each refusal, saves that
cross, disciplines, pictures, videos, the lists, publishing and deleting."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from portfolio import service
from portfolio.models import Piece
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, clock, lifecycle
from kernel.models import SearchDocument

from ..conftest import make_image, make_person, make_role, new_discipline, slug

pytestmark = pytest.mark.db

ADD, MANAGE = service.ADD, service.MANAGE


async def _artist(db: AsyncSession, name: str = "petro") -> uuid.UUID:
    """Someone whose role holds `add` alone, as a site's artist role does."""
    return await make_person(db, name, role=await make_role(db, ADD))


async def _new(
    db: AsyncSession,
    by: uuid.UUID,
    *,
    manages: bool = False,
    discipline: str | None = None,
    **fields: Any,
) -> Piece:
    piece = await service.create(
        db,
        {
            "title": "Harbour at dusk",
            "slug": slug(),
            "discipline": discipline or await new_discipline(db),
            "image_id": str(await make_image(db)),
            **fields,
        },
        by=by,
        manages=manages,
    )
    await db.commit()
    return piece


async def _live(db: AsyncSession, by: uuid.UUID, **fields: Any) -> Piece:
    piece = await _new(db, by, manages=True, **fields)
    await service.publish(db, piece.id, None, by=by, manages=True, adds=True)
    await db.commit()
    return piece


async def _problem(call: Any) -> Problem:
    with pytest.raises(Problem) as raised:
        await call
    return raised.value


# --- adding, and who it's by ------------------------------------------------------------------


async def test_an_artist_adds_a_draft_credited_to_them(db: AsyncSession) -> None:
    artist = await _artist(db)
    piece = await _new(db, artist, title="Sunburst sticker", slug=None)
    assert piece.artist_id == artist
    assert piece.status == lifecycle.DRAFT
    assert piece.slug.startswith("sunburst-sticker")
    uses = await db.scalar(
        text("SELECT count(*) FROM media_use WHERE owner = :owner AND image_id = :image"),
        {"owner": service.owner(piece.id), "image": piece.image_id},
    )
    assert uses == 1
    audited = await db.scalar(
        text(
            "SELECT count(*) FROM kernel_audit_event WHERE action = 'portfolio.piece.created' "
            "AND target_id = :id"
        ),
        {"id": str(piece.id)},
    )
    assert audited == 1


async def test_only_staff_who_manage_credit_a_piece_to_someone_else_or_no_one(
    db: AsyncSession,
) -> None:
    artist, other = await _artist(db), await _artist(db, "J Tone")
    for credited in (str(other), None):
        refused = await _problem(_new(db, artist, artist_id=credited))
        await db.rollback()
        assert (refused.code, refused.status) == ("kernel.forbidden", 403)
    editor = await make_person(db, "Ed", role="editor")
    piece = await _new(db, editor, manages=True, artist_id=str(other))
    assert piece.artist_id == other
    nobody = await _new(db, editor, manages=True, artist_id=None)
    assert nobody.artist_id is None


async def test_a_piece_is_credited_only_to_someone_who_may_add_pieces(db: AsyncSession) -> None:
    editor = await make_person(db, "Ed", role="editor")
    member = await make_person(db, "Mo", role="member")
    refused = await _problem(_new(db, editor, manages=True, artist_id=str(member)))
    assert (refused.code, refused.status) == ("portfolio.not_an_artist", 422)
    names = {each["id"]: each["name"] for each in await service.artists(db)}
    assert str(editor) in names
    assert str(member) not in names


async def test_the_artists_list_names_people_never_by_address_for_the_public(
    db: AsyncSession,
) -> None:
    unnamed = await _artist(db, name="")
    piece = await _live(db, unnamed, artist_id=str(unnamed))
    (card,) = await service.cards(db, [piece])
    assert card["artist"] is None
    shown = await service.one(db, piece)
    assert "@" in shown["artist"]["name"]  # staff see who it is


# --- who may change a piece -------------------------------------------------------------------


async def test_an_artist_changes_their_own_pieces_and_no_one_elses(db: AsyncSession) -> None:
    artist, other = await _artist(db), await _artist(db, "J Tone")
    mine = await _new(db, artist)
    theirs = (await _new(db, other)).id
    changed = await service.change(
        db, mine.id, mine.version, {"title": "Harbour, again"}, by=artist, manages=False, adds=True
    )
    await db.commit()
    assert changed.title == "Harbour, again"
    calls = (
        lambda: service.change(
            db, theirs, 1, {"title": "Mine now"}, by=artist, manages=False, adds=True
        ),
        lambda: service.publish(db, theirs, None, by=artist, manages=False, adds=True),
        lambda: service.unpublish(db, theirs, by=artist, manages=False, adds=True),
        lambda: service.remove(db, theirs, by=artist, manages=False, adds=True),
    )
    for call in calls:
        refused = await _problem(call())
        await db.rollback()
        assert refused.status == 403


async def test_an_artist_who_no_longer_may_add_keeps_no_hold_on_their_pieces(
    db: AsyncSession,
) -> None:
    artist = await _artist(db)
    piece = await _new(db, artist)
    refused = await _problem(
        service.change(
            db,
            piece.id,
            piece.version,
            {"title": "Still mine?"},
            by=artist,
            manages=False,
            adds=False,
        )
    )
    assert refused.status == 403


async def test_staff_who_manage_change_every_piece_and_its_credit(db: AsyncSession) -> None:
    artist, other = await _artist(db), await _artist(db, "J Tone")
    editor = await make_person(db, "Ed", role="editor")
    piece = await _new(db, artist)
    changed = await service.change(
        db,
        piece.id,
        piece.version,
        {"artist_id": str(other)},
        by=editor,
        manages=True,
        adds=True,
    )
    await db.commit()
    assert changed.artist_id == other
    refused = await _problem(
        service.change(
            db,
            piece.id,
            changed.version,
            {"artist_id": str(artist)},
            by=other,
            manages=False,
            adds=True,
        )
    )
    assert refused.status == 403


# --- saving -----------------------------------------------------------------------------------


async def test_a_stale_version_is_refused_with_the_piece_as_it_is(db: AsyncSession) -> None:
    artist = await _artist(db)
    piece = await _new(db, artist)
    await service.change(db, piece.id, 1, {"title": "First"}, by=artist, manages=False, adds=True)
    await db.commit()
    refused = await _problem(
        service.change(db, piece.id, 1, {"title": "Second"}, by=artist, manages=False, adds=True)
    )
    assert (refused.code, refused.status) == ("portfolio.changed", 409)
    assert refused.extra["piece"]["title"] == "First"


async def test_a_slug_another_piece_has_is_refused(db: AsyncSession) -> None:
    artist = await _artist(db)
    taken = (await _new(db, artist)).slug
    second = await _new(db, artist)
    refused = await _problem(
        service.change(
            db,
            second.id,
            second.version,
            {"slug": taken},
            by=artist,
            manages=False,
            adds=True,
        )
    )
    assert (refused.code, refused.status) == ("portfolio.slug_taken", 409)
    await db.rollback()
    again = await _problem(_new(db, artist, slug=taken))
    assert again.code == "portfolio.slug_taken"


async def test_each_field_refused_names_itself(db: AsyncSession) -> None:
    artist = await _artist(db)
    piece_id = (await _new(db, artist)).id
    next_year = clock.now().year + 1
    cases = [
        ({"discipline": "no-such-discipline"}, "portfolio.unknown_discipline", "discipline"),
        ({"image_id": str(uuid.uuid4())}, "portfolio.image_not_found", "image_id"),
        ({"image_id": "not-an-id"}, "kernel.invalid_request", "image_id"),
        ({"video_url": "https://vimeo.com/76979871"}, "portfolio.not_youtube", "video_url"),
        (
            {"video_url": "https://www.youtube.com/playlist?list=PL1"},
            "portfolio.not_youtube",
            "video_url",
        ),
        ({"year": 999}, "portfolio.bad_year", "year"),
        ({"year": next_year + 1}, "portfolio.bad_year", "year"),
    ]
    for fields, code, field in cases:
        refused = await _problem(
            service.change(db, piece_id, 1, fields, by=artist, manages=False, adds=True)
        )
        await db.rollback()
        assert (refused.code, refused.status) == (code, 422), fields
        assert field in refused.errors, fields
    kept = await service.change(
        db, piece_id, 1, {"year": next_year}, by=artist, manages=False, adds=True
    )
    assert kept.year == next_year


async def test_a_youtube_link_is_kept_as_its_watch_address_and_can_be_cleared(
    db: AsyncSession,
) -> None:
    artist = await _artist(db)
    piece = await _new(db, artist, video_url="https://youtu.be/dQw4w9WgXcQ?t=42")
    assert (piece.video_url, piece.video_id) == (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    )
    cleared = await service.change(
        db,
        piece.id,
        piece.version,
        {"video_url": None, "year": None},
        by=artist,
        manages=False,
        adds=True,
    )
    assert (cleared.video_url, cleared.video_id, cleared.year) == (None, None, None)


async def test_a_new_picture_moves_the_use(db: AsyncSession) -> None:
    artist = await _artist(db)
    piece = await _new(db, artist)
    old = piece.image_id
    fresh = await make_image(db)
    await service.change(
        db,
        piece.id,
        piece.version,
        {"image_id": str(fresh)},
        by=artist,
        manages=False,
        adds=True,
    )
    await db.commit()
    rows = await db.execute(
        text("SELECT image_id FROM media_use WHERE owner = :owner"),
        {"owner": service.owner(piece.id)},
    )
    assert [row.image_id for row in rows] == [fresh]
    assert old != fresh


async def test_a_discipline_deleted_leaves_the_piece_with_none(db: AsyncSession) -> None:
    artist = await _artist(db)
    gone = await new_discipline(db)
    piece = await _live(db, artist, discipline=gone)
    await db.execute(
        text(
            "DELETE FROM kernel_term WHERE slug = :slug AND vocabulary_id = "
            "(SELECT id FROM kernel_vocabulary WHERE key = 'portfolio_discipline')"
        ),
        {"slug": gone},
    )
    await db.commit()
    (card,) = await service.cards(db, [piece])
    assert card["discipline"] is None
    assert piece.id in {each.id for each in await service.newest(db, discipline=None, limit=200)}


# --- the lists --------------------------------------------------------------------------------


async def test_the_public_list_is_live_pieces_newest_first_of_one_discipline(
    db: AsyncSession,
) -> None:
    artist = await _artist(db)
    discipline = await new_discipline(db)
    older = await _live(db, artist, discipline=discipline)
    newer = await _live(db, artist, discipline=discipline)
    await db.execute(
        text("UPDATE portfolio_piece SET published_at = now() - interval '1 day' WHERE id = :id"),
        {"id": older.id},
    )
    await db.commit()
    await _new(db, artist, discipline=discipline)  # a draft, never shown
    first = await service.page_of(db, discipline=discipline, cursor=None, limit=1)
    assert [each["id"] for each in first["items"]] == [str(newer.id)]
    assert first["next_cursor"] is not None
    second = await service.page_of(db, discipline=discipline, cursor=first["next_cursor"], limit=1)
    assert [each["id"] for each in second["items"]] == [str(older.id)]
    assert second["next_cursor"] is None
    missing = await _problem(service.page_of(db, discipline="d-nothing-here", cursor=None))
    assert (missing.code, missing.status) == ("portfolio.discipline_not_found", 404)


async def test_the_public_sees_only_disciplines_with_something_live(db: AsyncSession) -> None:
    artist = await _artist(db)
    shown, empty = await new_discipline(db, "Shown"), await new_discipline(db, "Empty")
    await _live(db, artist, discipline=shown)
    await _new(db, artist, discipline=empty)
    slugs = {each["slug"] for each in await service.live_disciplines(db)}
    assert shown in slugs
    assert empty not in slugs


async def test_the_admin_list_is_every_piece_or_your_own(db: AsyncSession) -> None:
    artist, other = await _artist(db), await _artist(db, "J Tone")
    title = f"Mine {uuid.uuid4().hex[:8]}"
    mine = await _new(db, artist, title=title)
    await _new(db, other, title=title)
    own = await service.every(db, mine=artist, q=title, discipline=None, cursor=None)
    assert [each["id"] for each in own["items"]] == [str(mine.id)]
    assert own["no_artist"] is None
    every = await service.every(db, mine=None, q=title, discipline=None, cursor=None)
    assert len(every["items"]) == 2
    assert isinstance(every["no_artist"], int)


# --- publishing and deleting ------------------------------------------------------------------


async def test_a_draft_or_scheduled_piece_is_not_live_until_it_is(db: AsyncSession) -> None:
    artist = await _artist(db)
    piece = await _new(db, artist)
    assert await service.live(db, piece.slug) is None
    later = (clock.now() + timedelta(days=2)).isoformat()
    await service.publish(db, piece.id, later, by=artist, manages=False, adds=True)
    await db.commit()
    assert piece.status == lifecycle.SCHEDULED
    assert await service.live(db, piece.slug) is None
    await service.publish(db, piece.id, None, by=artist, manages=False, adds=True)
    await db.commit()
    assert await service.live(db, piece.slug) is not None
    assert (await service.one(db, piece))["path"] == f"/art/piece/{piece.slug}"
    await service.unpublish(db, piece.id, by=artist, manages=False, adds=True)
    await db.commit()
    assert await service.live(db, piece.slug) is None
    refused = await _problem(
        service.publish(db, piece.id, "tomorrow", by=artist, manages=False, adds=True)
    )
    assert refused.status == 422


async def test_a_live_piece_saved_is_found_by_its_new_words(db: AsyncSession) -> None:
    artist = await _artist(db)
    piece = await _live(db, artist)
    word = f"w{uuid.uuid4().hex[:10]}"
    await service.change(
        db,
        piece.id,
        piece.version,
        {"about": f"Oil and {word}."},
        by=artist,
        manages=False,
        adds=True,
    )
    await db.commit()
    body = await db.scalar(select(SearchDocument.body).where(SearchDocument.content_id == piece.id))
    assert body is not None
    assert word in body
    assert "petro" in body


async def test_a_deleted_piece_takes_its_use_terms_and_document_and_says_so(
    db: AsyncSession, said: list[tuple[str, Any]]
) -> None:
    artist = await _artist(db)
    piece = await _live(db, artist)
    said.clear()
    await service.remove(db, piece.id, by=artist, manages=False, adds=True)
    await db.commit()
    left = [
        await db.scalar(text(query), {"id": piece.id, "owner": service.owner(piece.id)})
        for query in (
            "SELECT count(*) FROM portfolio_piece WHERE id = :id",
            "SELECT count(*) FROM media_use WHERE owner = :owner",
            "SELECT count(*) FROM kernel_term_link WHERE content_id = :id",
            "SELECT count(*) FROM kernel_search_document WHERE content_id = :id",
        )
    ]
    assert left == [0, 0, 0, 0]
    ours = [(name, payload.id) for name, payload in said if name.startswith("portfolio.")]
    assert ours == [("portfolio.piece.deleted", piece.id)]


async def test_two_saves_of_one_piece_make_one_version(database: Any) -> None:
    """The row is locked as it's read: two saves sent with the same version
    make one change and one 409, never two changes. Each save is held after
    its lock until both have been sent, so they really race (a mutant without
    the lock lets both through)."""
    import asyncio

    async with database.sessions() as db:
        artist = await _artist(db)
        piece = await _new(db, artist)
    outcomes: list[str] = []

    async def save(title: str) -> None:
        async with database.sessions() as session:
            try:
                await service.change(
                    session, piece.id, 1, {"title": title}, by=artist, manages=False, adds=True
                )
                await asyncio.sleep(0.2)
                await session.commit()
                outcomes.append("saved")
            except Problem as problem:
                await session.rollback()
                outcomes.append(problem.code)

    await asyncio.gather(save("One"), save("Two"))
    assert sorted(outcomes) == ["portfolio.changed", "saved"]
    async with database.sessions() as db:
        assert await db.scalar(select(Piece.version).where(Piece.id == piece.id)) == 2
        count = await db.scalar(select(func.count()).select_from(Piece).where(Piece.id == piece.id))
        assert count == 1


async def test_a_piece_that_isnt_there_a_taken_title_and_a_bad_cursor(db: AsyncSession) -> None:
    missing = await _problem(service.get(db, uuid.uuid4()))
    assert (missing.code, missing.status) == ("portfolio.piece_not_found", 404)
    artist = await _artist(db)
    title = f"Twin {uuid.uuid4().hex[:6]}"
    first = await _new(db, artist, title=title, slug=None)
    second = await _new(db, artist, title=title, slug=None)
    assert second.slug == f"{first.slug}-2"
    for call in (
        service.page_of(db, discipline=None, cursor="not-a-cursor"),
        service.every(db, mine=None, q=None, discipline=None, cursor="2026-11-28~nope"),
    ):
        refused = await _problem(call)
        assert refused.status == 422
    assert await service.live(db, "Not A Slug") is None


async def test_the_admin_list_pages_by_discipline(db: AsyncSession) -> None:
    artist = await _artist(db)
    discipline = await new_discipline(db)
    one = await _new(db, artist, discipline=discipline)
    two = await _new(db, artist, discipline=discipline)
    first = await service.every(
        db, mine=artist, q=None, discipline=discipline, cursor=None, limit=1
    )
    assert [each["id"] for each in first["items"]] == [str(two.id)]
    after = await service.every(
        db, mine=artist, q=None, discipline=discipline, cursor=first["next_cursor"], limit=1
    )
    assert [each["id"] for each in after["items"]] == [str(one.id)]
