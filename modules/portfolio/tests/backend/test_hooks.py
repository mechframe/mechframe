"""portfolio's hooks and public surface (`dev plans/contracts/portfolio.md`
§2, §7): item references, the server copy, `public.py`, search, export and
erase, the seed and the settings."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from portfolio import privacy as portfolio_privacy
from portfolio import public, service
from portfolio import refs as portfolio_refs
from portfolio.models import Piece
from portfolio.schemas import Settings
from portfolio.search import SEARCH
from portfolio.server_copy import PAGES
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import load_module, privacy, refs, server_copy
from kernel.models import SearchDocument

from ..conftest import make_image, make_person, make_role, new_discipline, slug

pytestmark = pytest.mark.db

(PIECES,) = portfolio_refs.REFS


async def _artist(db: AsyncSession, name: str = "petro") -> uuid.UUID:
    return await make_person(db, name, role=await make_role(db, service.ADD))


async def _piece(
    db: AsyncSession,
    artist: uuid.UUID | None,
    *,
    live: bool = True,
    discipline: str | None = None,
    **fields: Any,
) -> Piece:
    editor = await make_person(db, "Ed", role="editor")
    piece = await service.create(
        db,
        {
            "title": "Harbour at dusk",
            "slug": slug(),
            "discipline": discipline or await new_discipline(db, "Paintings"),
            "image_id": str(await make_image(db, "Boats at dusk")),
            "artist_id": str(artist) if artist else None,
            "year": 2025,
            "about": "Oil on canvas.\n\nPainted from the sea wall.",
            **fields,
        },
        by=editor,
        manages=True,
    )
    if live:
        await service.publish(db, piece.id, None, by=editor, manages=True, adds=True)
    await db.commit()
    return piece


# --- item references (hook 11) -----------------------------------------------------------------


async def test_a_piece_is_referred_to_by_its_line_picture_and_page(db: AsyncSession) -> None:
    artist = await _artist(db)
    live = await _piece(db, artist)
    draft = await _piece(db, None, live=False, year=None)
    found = await PIECES.find(db, [live.id, draft.id, uuid.uuid4()])
    assert set(found) == {live.id, draft.id}
    shown = found[live.id]
    assert (shown.title, shown.line, shown.live) == (
        "Harbour at dusk",
        "Paintings, by petro, 2025",
        True,
    )
    assert shown.path == f"/art/piece/{live.slug}"
    assert shown.image is not None
    assert shown.image.startswith("https://files.portfolio.test/")
    hidden = found[draft.id]
    assert (hidden.line, hidden.live, hidden.path) == ("Paintings", False, None)


async def test_the_picker_finds_by_title_drafts_too_a_page_at_a_time(db: AsyncSession) -> None:
    word = f"Tide{uuid.uuid4().hex[:8]}"
    first = await _piece(db, None, live=False, title=f"{word} one")
    second = await _piece(db, None, title=f"{word} two")
    page = await PIECES.pick(db, word, cursor=None, limit=1)
    assert [each.id for each in page["items"]] == [second.id]
    after = await PIECES.pick(db, word, cursor=page["next_cursor"], limit=1)
    assert [each.id for each in after["items"]] == [first.id]
    assert after["next_cursor"] is None
    with pytest.raises(ValueError, match="a page of"):
        await PIECES.pick(db, word, cursor="not-a-cursor", limit=1)


def test_the_kernel_takes_portfolios_one_type() -> None:
    from pathlib import Path

    module = load_module(Path(__file__).resolve().parents[2] / "module.json")
    assert refs.build([module]).keys() == {"portfolio.piece"}


# --- public.py -------------------------------------------------------------------------------


async def test_public_answers_live_pieces_only_in_the_order_asked(db: AsyncSession) -> None:
    artist = await _artist(db)
    one, two = await _piece(db, artist), await _piece(db, artist)
    draft = await _piece(db, artist, live=False)
    cards = await public.piece_cards(db, [two.id, draft.id, one.id, uuid.uuid4()])
    assert [card.id for card in cards] == [str(two.id), str(one.id)]
    theirs = await public.pieces_by(db, artist)
    assert {card.id for card in theirs} == {str(one.id), str(two.id)}


# --- search (hook 3) -------------------------------------------------------------------------


async def test_search_reads_a_live_piece_with_its_artist_and_discipline(
    db: AsyncSession,
) -> None:
    piece = await _piece(db, await _artist(db, "Moya Brown"))
    draft = await _piece(db, None, live=False)
    (source,) = SEARCH
    found = await source.document(db, piece.id)
    assert found is not None
    assert found.path == f"/art/piece/{piece.slug}"
    assert "Moya Brown" in found.body
    assert "Paintings" in found.body
    assert "sea wall" in found.body
    assert await source.document(db, draft.id) is None


# --- the server copy (SPEC 9) ----------------------------------------------------------------


async def test_a_pieces_page_is_read_without_javascript(db: AsyncSession) -> None:
    piece = await _piece(db, await _artist(db), video_url="https://youtu.be/dQw4w9WgXcQ")
    assert PAGES is not None
    page = await PAGES.page(db, service.path(piece), {"slug": piece.slug})
    assert isinstance(page, server_copy.Page)
    assert page.title.startswith("Harbour at dusk, by petro")
    assert page.description == "Oil on canvas. Painted from the sea wall."
    words = str(page.words)
    for said in (
        "<h1>Harbour at dusk</h1>",
        "By petro, 2025",
        "Painted from the sea wall.",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        'href="/art"',
    ):
        assert said in words, said
    (artwork,) = page.data
    assert artwork["@type"] == "VisualArtwork"
    assert artwork["creator"] == {"@type": "Person", "name": "petro"}
    assert (artwork["artform"], artwork["dateCreated"]) == ("Paintings", "2025")
    assert page.image is not None


async def test_a_draft_or_a_discipline_that_isnt_one_is_a_real_404(db: AsyncSession) -> None:
    draft = await _piece(db, None, live=False)
    assert PAGES is not None
    assert await PAGES.page(db, service.path(draft), {"slug": draft.slug}) is None
    assert await PAGES.page(db, "/art/no-such-thing", {"discipline": "no-such-thing"}) is None


async def test_the_art_page_lists_live_pieces_and_the_disciplines_as_links(
    db: AsyncSession,
) -> None:
    discipline = await new_discipline(db, "Graphic design")
    piece = await _piece(db, await _artist(db), discipline=discipline, title="Sunburst")
    assert PAGES is not None
    page = await PAGES.page(db, f"/art/{discipline}", {"discipline": discipline})
    assert isinstance(page, server_copy.Page)
    words = str(page.words)
    assert f'href="/art/piece/{piece.slug}"' in words
    assert f'href="/art/{discipline}"' in words
    assert "Graphic design, by petro, 2025" in words
    (collection,) = page.data
    assert collection["@type"] == "CollectionPage"
    names = [each["name"] for each in collection["mainEntity"]["itemListElement"]]
    assert names == ["Sunburst"]
    everything = await PAGES.page(db, "/art", {})
    assert isinstance(everything, server_copy.Page)
    assert "<h1>Art</h1>" in str(everything.words)
    entries = {entry.path for entry in await PAGES.sitemap(db)}
    assert {"/art", f"/art/{discipline}", service.path(piece)} <= entries


# --- export and erase (hook 7) ---------------------------------------------------------------


async def test_export_lists_a_persons_pieces_and_erase_keeps_them_uncredited(
    db: AsyncSession,
) -> None:
    artist = await _artist(db, "Lil' Ma")
    piece = await _piece(db, artist)
    subject = privacy.Subject(user_id=artist, email="x@example.test")
    exported = await portfolio_privacy.export_user_data(db, subject)
    assert [each["id"] for each in exported["pieces"]] == [str(piece.id)]
    json.dumps(exported)  # it's written to a file as JSON
    await portfolio_privacy.delete_user_data(db, subject)
    await db.commit()
    kept = await db.scalar(select(Piece).where(Piece.id == piece.id))
    assert kept is not None
    assert kept.artist_id is None
    body = await db.scalar(select(SearchDocument.body).where(SearchDocument.content_id == piece.id))
    assert body is not None
    assert "Lil' Ma" not in body


# --- the settings ----------------------------------------------------------------------------


def test_the_settings_refuse_a_link_that_could_go_anywhere() -> None:
    assert Settings().pieces_per_page == 24
    for good in ("", "/contact", "https://example.com/commissions"):
        assert Settings(commission_link=good).commission_link == good
    for bad in ("//evil.test", "javascript:alert(1)", "http://example.com", "contact"):
        with pytest.raises(ValidationError):
            Settings(commission_link=bad)
    with pytest.raises(ValidationError):
        Settings(pieces_per_page=2)
    with pytest.raises(ValidationError):
        Settings(lead="two\nlines")


def test_the_manifest_agrees_with_the_settings_model() -> None:
    from pathlib import Path

    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "module.json").read_text(encoding="utf-8")
    )
    declared = {each["key"]: each["default"] for each in manifest["settings"]}
    assert declared == Settings().model_dump()


# --- the migration on its own ----------------------------------------------------------------


async def test_the_seed_makes_the_four_disciplines_once(db: AsyncSession) -> None:
    from portfolio.seed import DISCIPLINES, _disciplines

    actor = await make_person(db)
    await _disciplines(db, actor)
    await _disciplines(db, actor)
    await db.commit()
    have = [term["slug"] for term in await service.terms(db)]
    for wanted, _ in DISCIPLINES:
        assert have.count(wanted) == 1


async def test_media_keeps_a_placed_picture(db: AsyncSession) -> None:
    piece = await _piece(db, None)
    used = await db.scalar(
        text("SELECT label FROM media_use WHERE owner = :owner"),
        {"owner": service.owner(piece.id)},
    )
    assert used == "Harbour at dusk"


async def test_a_reindex_reads_every_live_piece_and_no_draft(db: AsyncSession) -> None:
    live = await _piece(db, await _artist(db))
    draft = await _piece(db, None, live=False)
    (source,) = SEARCH
    found = {document.id async for document in source.documents(db)}
    assert live.id in found
    assert draft.id not in found


async def test_the_seed_makes_its_pieces_once_while_storage_is_on(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from media import public as media
    from portfolio import seed as portfolio_seed

    from kernel import seed as seeding

    kept: dict[str, uuid.UUID] = {}

    async def store(session: AsyncSession, data: bytes, *, filename: str, alt: str, by: Any) -> Any:
        if filename not in kept:
            kept[filename] = await make_image(session, alt)
        return media.Picture(
            id=kept[filename],
            url=f"https://files.test/{filename}",
            srcset="",
            width=1200,
            height=900,
            alt=alt,
            decorative=False,
        )

    monkeypatch.setattr(media, "storage_on", lambda: True)
    monkeypatch.setattr(media, "store", store)
    editor = await make_person(db, "Ed", role="editor")

    async def user(role: str) -> uuid.UUID:
        return editor

    ctx = SimpleNamespace(now=seeding.NOW, user=user)
    for _ in range(2):
        await portfolio_seed.seed(db, ctx)  # type: ignore[arg-type]
        await db.commit()
    for slug_, _title, _discipline, _year, state, *_ in portfolio_seed.PIECES:
        rows = list(await db.scalars(select(Piece).where(Piece.slug == slug_)))
        assert len(rows) == 1, slug_
        assert rows[0].status == ("published" if state == portfolio_seed.LIVE else "draft")


async def test_a_long_piece_is_described_in_its_opening_words_and_an_empty_discipline_named(
    db: AsyncSession,
) -> None:
    words = " ".join(["Oil and ash on a long linen canvas"] * 12)
    piece = await _piece(db, None, about=words)
    assert PAGES is not None
    page = await PAGES.page(db, service.path(piece), {"slug": piece.slug})
    assert isinstance(page, server_copy.Page)
    assert len(page.description) <= 160
    assert page.description.endswith("…")
    quiet = await new_discipline(db, "Sculpture")
    empty = await PAGES.page(db, f"/art/{quiet}", {"discipline": quiet})
    assert isinstance(empty, server_copy.Page)
    assert empty.title.startswith("Sculpture · Art")
    assert "Nothing here yet." in str(empty.words)
