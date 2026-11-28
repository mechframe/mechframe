"""portfolio's routes over HTTP only (`dev plans/contracts/portfolio.md` §2,
§7): who may call each (decision 0074), an artist adding and editing their
own pieces and no one else's, staff crediting a piece, the public reads, and
what the site's server copy says of a piece. Nothing here imports portfolio."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from .conftest import Browser, Person, slug, unique_image

pytestmark = pytest.mark.db

ADMIN = "/api/portfolio/admin/pieces"
NOBODY = "00000000-0000-0000-0000-000000000001"
UNCHECKED = {"mechframe_unchecked": True}


async def _artist_role(browser: Browser) -> str:
    """A site's artist role, made by its owner: `portfolio.piece.add`, and
    `media.image.upload` to add a picture. The browser ends signed in as the owner."""
    await browser.as_new("owner")
    role = f"artist-{uuid.uuid4().hex[:8]}"
    made = await browser.http.post(
        "/api/auth/admin/roles",
        json={
            "id": role,
            "name": f"Artist {role}",
            "permissions": ["portfolio.piece.add", "media.image.upload"],
        },
    )
    assert made.status_code == 201, made.text
    return role


async def _discipline(browser: Browser, label: str = "Paintings") -> str:
    """A discipline of the test's own, through the kernel's term routes (the owner's)."""
    term = f"d-{uuid.uuid4().hex[:10]}"
    made = await browser.http.post(
        "/api/kernel/admin/terms",
        json={"vocabulary": "portfolio_discipline", "slug": term, "label": label},
    )
    assert made.status_code == 201, made.text
    return term


async def _image(browser: Browser) -> str:
    uploaded = await browser.upload(unique_image())
    assert uploaded.status_code == 201, uploaded.text
    return str(uploaded.json()["id"])


async def _piece(browser: Browser, discipline: str, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        ADMIN,
        json={
            "title": "Harbour at dusk",
            "slug": slug(),
            "discipline": discipline,
            "image_id": await _image(browser),
            **fields,
        },
    )
    assert made.status_code == 201, made.text
    piece: dict[str, Any] = made.json()
    return piece


async def _signed_in_as(browser: Browser, *roles: str) -> tuple[Browser, Person]:
    """Another browser, signed in as someone new holding `roles`."""
    other = browser.stranger()
    person = await other.person(*roles)
    await other.sign_in(person)
    return other, person


# --- who may call each route ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", ADMIN, None),
        ("POST", ADMIN, {"title": "x"}),
        ("GET", f"{ADMIN}/{NOBODY}", None),
        ("PATCH", f"{ADMIN}/{NOBODY}", {"version": 1}),
        ("POST", f"{ADMIN}/{NOBODY}/publish", {}),
        ("POST", f"{ADMIN}/{NOBODY}/unpublish", None),
        ("DELETE", f"{ADMIN}/{NOBODY}", None),
        ("GET", "/api/portfolio/admin/artists", None),
        ("GET", "/api/portfolio/admin/disciplines", None),
    ],
)
async def test_signed_out_is_401_and_a_member_is_403(
    browser: Browser, method: str, path: str, body: Any
) -> None:
    signed_out = await browser.http.request(method, path, json=body)
    assert signed_out.status_code == 401, signed_out.text
    await browser.as_new("member")
    member = await browser.http.request(method, path, json=body)
    assert member.status_code == 403, member.text
    assert member.json()["code"] == "kernel.forbidden"


async def test_the_live_pieces_and_disciplines_are_open_to_anyone(browser: Browser) -> None:
    missing = await browser.http.get(f"/api/portfolio/pieces/{slug()}")
    assert (missing.status_code, missing.json()["code"]) == (404, "portfolio.piece_not_found")
    listed = await browser.http.get("/api/portfolio/pieces")
    assert listed.status_code == 200, listed.text
    assert set(listed.json()) == {"items", "next_cursor"}
    disciplines = await browser.http.get("/api/portfolio/disciplines")
    assert disciplines.status_code == 200, disciplines.text
    unknown = await browser.http.get("/api/portfolio/pieces", params={"discipline": "d-none-here"})
    assert (unknown.status_code, unknown.json()["code"]) == (
        404,
        "portfolio.discipline_not_found",
    )
    wrong = await browser.http.get("/api/portfolio/pieces", params={"discipline": "Not A Slug"})
    assert wrong.status_code == 422


# --- an artist's own pieces ----------------------------------------------------------------


async def test_an_artist_adds_edits_publishes_and_deletes_their_own(browser: Browser) -> None:
    role = await _artist_role(browser)
    discipline = await _discipline(browser)
    artist_browser, artist = await _signed_in_as(browser, "member", role)

    piece = await _piece(artist_browser, discipline, video_url="https://youtu.be/dQw4w9WgXcQ")
    assert set(piece) == {
        "id",
        "title",
        "slug",
        "discipline",
        "artist",
        "year",
        "about",
        "image_id",
        "picture",
        "video",
        "status",
        "publish_at",
        "published_at",
        "version",
        "updated_at",
        "path",
    }
    assert piece["artist"]["id"] == artist.id  # whoever adds it
    assert (piece["status"], piece["path"]) == ("draft", None)
    assert piece["video"] == {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_id": "dQw4w9WgXcQ",
    }

    saved = await artist_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 1, "year": 2025, "about": "Oil."}
    )
    assert saved.status_code == 200, saved.text
    stale = await artist_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 1, "title": "Late"}
    )
    assert (stale.status_code, stale.json()["code"]) == (409, "portfolio.changed")
    assert stale.json()["piece"]["year"] == 2025

    published = await artist_browser.http.post(f"{ADMIN}/{piece['id']}/publish", json={})
    assert published.status_code == 200, published.text
    assert published.json()["path"] == f"/art/piece/{piece['slug']}"

    shown = await browser.stranger().http.get(f"/api/portfolio/pieces/{piece['slug']}")
    assert shown.status_code == 200, shown.text
    assert shown.json()["about"] == "Oil."
    assert "@" not in shown.text

    mine = await artist_browser.http.get(ADMIN)
    assert [each["id"] for each in mine.json()["items"]] == [piece["id"]]
    assert mine.json()["no_artist"] is None

    gone = await artist_browser.http.delete(f"{ADMIN}/{piece['id']}")
    assert gone.status_code == 204, gone.text
    after = await browser.stranger().http.get(f"/api/portfolio/pieces/{piece['slug']}")
    assert after.status_code == 404


async def test_an_artist_cant_touch_or_credit_another_persons_piece(browser: Browser) -> None:
    role = await _artist_role(browser)
    discipline = await _discipline(browser)
    owners_piece = await _piece(browser, discipline)
    artist_browser, _ = await _signed_in_as(browser, "member", role)
    path = f"{ADMIN}/{owners_piece['id']}"
    for method, at, body in (
        ("GET", path, None),
        ("PATCH", path, {"version": 1, "title": "Mine now"}),
        ("POST", f"{path}/publish", {}),
        ("POST", f"{path}/unpublish", None),
        ("DELETE", path, None),
    ):
        refused = await artist_browser.http.request(method, at, json=body)
        assert refused.status_code == 403, (method, at, refused.text)
    crediting = await artist_browser.http.post(
        ADMIN,
        json={
            "title": "Someone else's",
            "discipline": discipline,
            "image_id": await _image(artist_browser),
            "artist_id": owners_piece["artist"]["id"],
        },
    )
    assert crediting.status_code == 403, crediting.text
    artists = await artist_browser.http.get("/api/portfolio/admin/artists")
    assert artists.status_code == 403


async def test_staff_credit_a_piece_to_an_artist_who_then_may_edit_it(browser: Browser) -> None:
    role = await _artist_role(browser)
    discipline = await _discipline(browser)
    artist_browser, artist = await _signed_in_as(browser, "member", role)
    _, member = await _signed_in_as(browser, "member")
    editor_browser, _ = await _signed_in_as(browser, "member", "editor")

    artists = await editor_browser.http.get("/api/portfolio/admin/artists")
    assert artists.status_code == 200, artists.text
    ids = {each["id"] for each in artists.json()["items"]}
    assert artist.id in ids
    assert member.id not in ids

    piece = await _piece(editor_browser, discipline, artist_id=None)
    assert piece["artist"] is None
    listed = await editor_browser.http.get(ADMIN, params={"q": piece["title"]})
    assert listed.json()["no_artist"] >= 1
    refused = await editor_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 1, "artist_id": member.id}
    )
    assert (refused.status_code, refused.json()["code"]) == (422, "portfolio.not_an_artist")
    credited = await editor_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 1, "artist_id": artist.id}
    )
    assert credited.status_code == 200, credited.text
    now_theirs = await artist_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 2, "title": "Now theirs"}
    )
    assert now_theirs.status_code == 200, now_theirs.text
    unknown = await editor_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 3, "discipline": "d-not-one"}
    )
    assert (unknown.status_code, unknown.json()["code"]) == (422, "portfolio.unknown_discipline")
    vimeo = await editor_browser.http.patch(
        f"{ADMIN}/{piece['id']}", json={"version": 3, "video_url": "https://vimeo.com/1"}
    )
    assert (vimeo.status_code, vimeo.json()["code"]) == (422, "portfolio.not_youtube")


# --- the public reads and the server copy -----------------------------------------------------


async def test_the_art_page_lists_live_pieces_by_discipline_and_says_them_to_crawlers(
    browser: Browser,
) -> None:
    await browser.as_new("owner")
    discipline = await _discipline(browser, "Graphic design")
    live = await _piece(browser, discipline, title="Sunburst sticker", year=2026)
    await _piece(browser, discipline, title="A draft")
    published = await browser.http.post(f"{ADMIN}/{live['id']}/publish", json={})
    assert published.status_code == 200, published.text

    visitor = browser.stranger()
    listed = await visitor.http.get("/api/portfolio/pieces", params={"discipline": discipline})
    assert listed.status_code == 200, listed.text
    (card,) = listed.json()["items"]
    assert set(card) == {
        "id",
        "title",
        "slug",
        "discipline",
        "artist",
        "year",
        "picture",
        "has_video",
        "path",
    }
    assert card["discipline"] == {"slug": discipline, "label": "Graphic design"}
    chips = await visitor.http.get("/api/portfolio/disciplines")
    assert {"slug": discipline, "label": "Graphic design"} in chips.json()["items"]

    page = await visitor.http.get(f"/art/piece/{live['slug']}", extensions=UNCHECKED)
    assert page.status_code == 200, page.text
    assert "Sunburst sticker" in page.text
    assert '"VisualArtwork"' in page.text
    listing = await visitor.http.get(f"/art/{discipline}", extensions=UNCHECKED)
    assert listing.status_code == 200
    assert "Sunburst sticker" in listing.text
    nothing = await visitor.http.get("/art/not-a-discipline", extensions=UNCHECKED)
    assert nothing.status_code == 404


async def test_staff_who_hold_neither_permission_are_refused(browser: Browser) -> None:
    await browser.as_new("owner")
    role = f"writer-{uuid.uuid4().hex[:8]}"
    made = await browser.http.post(
        "/api/auth/admin/roles",
        json={"id": role, "name": f"Writer {role}", "permissions": ["blog.post.write"]},
    )
    assert made.status_code == 201, made.text
    writer, _ = await _signed_in_as(browser, "member", role)
    refused = await writer.http.get(ADMIN)
    assert (refused.status_code, refused.json()["code"]) == (403, "kernel.forbidden")


async def test_an_editor_reads_unpublishes_and_counts_the_disciplines(browser: Browser) -> None:
    await browser.as_new("owner")
    discipline = await _discipline(browser, "Animation")
    editor, _ = await _signed_in_as(browser, "member", "editor")
    piece = await _piece(editor, discipline)
    read = await editor.http.get(f"{ADMIN}/{piece['id']}")
    assert read.status_code == 200, read.text
    assert read.json()["version"] == 1
    live = await editor.http.post(f"{ADMIN}/{piece['id']}/publish", json={})
    assert live.status_code == 200, live.text
    back = await editor.http.post(f"{ADMIN}/{piece['id']}/unpublish")
    assert back.status_code == 200, back.text
    assert (back.json()["status"], back.json()["path"]) == ("draft", None)
    counted = await editor.http.get("/api/portfolio/admin/disciplines")
    assert counted.status_code == 200, counted.text
    (mine,) = [each for each in counted.json()["items"] if each["slug"] == discipline]
    assert (mine["label"], mine["pieces"]) == ("Animation", 1)
    art = await browser.stranger().http.get("/api/portfolio/art")
    assert art.status_code == 200, art.text
    assert set(art.json()) == {"lead", "commission_link"}
