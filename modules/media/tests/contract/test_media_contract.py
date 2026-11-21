"""The media library's routes over HTTP only (`dev plans/contracts/media.md`
§2): who may call each, and what each answers. Nothing here imports media."""

from __future__ import annotations

import pytest

from .conftest import STORAGE, Browser, unique_image

LIST = "/api/media/admin/images"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", LIST),
        ("GET", f"{LIST}/00000000-0000-0000-0000-000000000001"),
        ("PATCH", f"{LIST}/00000000-0000-0000-0000-000000000001"),
        ("DELETE", f"{LIST}/00000000-0000-0000-0000-000000000001"),
    ],
)
async def test_signed_out_is_401_and_a_member_is_403(
    browser: Browser, method: str, path: str
) -> None:
    body = {"version": 1} if method == "PATCH" else None
    signed_out = await browser.http.request(method, path, json=body)
    assert signed_out.status_code == 401, signed_out.text

    await browser.as_new("member")
    member = await browser.http.request(method, path, json=body)
    assert member.status_code == 403, member.text
    assert member.json()["code"] == "kernel.forbidden"


async def test_a_member_cant_upload(browser: Browser) -> None:
    await browser.as_new("member")

    response = await browser.upload(unique_image())

    assert response.status_code == 403


async def test_an_editor_uploads_lists_describes_replaces_and_deletes(browser: Browser) -> None:
    await browser.as_new("member", "editor")

    made = await browser.upload(unique_image(), name="Door.png")
    assert made.status_code == 201, made.text
    image = made.json()
    assert set(image) == {
        "id",
        "url",
        "srcset",
        "width",
        "height",
        "bytes",
        "content_type",
        "filename",
        "alt",
        "decorative",
        "uploaded_by",
        "created_at",
        "version",
    }
    assert image["url"] == f"{STORAGE['STORAGE_PUBLIC_URL']}/media/{image['id']}/1.png"
    assert (image["width"], image["filename"], image["alt"], image["version"]) == (
        600,
        "Door.png",
        None,
        1,
    )

    listed = await browser.http.get(LIST, params={"missing_alt": "true"})
    assert listed.status_code == 200, listed.text
    assert image["id"] in [each["id"] for each in listed.json()["items"]]
    assert listed.json()["missing_alt"] >= 1

    described = await browser.http.patch(
        f"{LIST}/{image['id']}", json={"version": 1, "alt": "A red door"}
    )
    assert described.status_code == 200, described.text
    assert (described.json()["alt"], described.json()["version"], described.json()["uses"]) == (
        "A red door",
        2,
        [],
    )

    stale = await browser.http.patch(f"{LIST}/{image['id']}", json={"version": 1, "alt": "Other"})
    assert stale.status_code == 409
    assert stale.json()["code"] == "media.changed"
    assert stale.json()["version"] == 2

    replaced = await browser.http.put(
        f"{LIST}/{image['id']}/file",
        files={"file": ("new.jpg", unique_image("JPEG"), "image/jpeg")},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["id"] == image["id"]
    assert replaced.json()["url"].endswith(f"/media/{image['id']}/2.jpg")
    assert (replaced.json()["alt"], replaced.json()["version"]) == ("A red door", 3)

    gone = await browser.http.delete(f"{LIST}/{image['id']}")
    assert gone.status_code == 204, gone.text
    missing = await browser.http.get(f"{LIST}/{image['id']}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "media.image_not_found"


async def test_the_same_image_twice_is_200_with_the_one_stored(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    data = unique_image()

    first = await browser.upload(data)
    again = await browser.upload(data, name="again.png")

    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["id"] == first.json()["id"]


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", 415, "media.not_an_image"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, 422, "media.unreadable"),
    ],
)
async def test_a_file_that_isnt_a_whole_image_is_refused_with_a_sentence(
    browser: Browser, data: bytes, status: int, code: str
) -> None:
    await browser.as_new("member", "editor")

    response = await browser.upload(data, name="photo.png")

    assert response.status_code == status, response.text
    assert response.json()["code"] == code
    assert response.json()["detail"].endswith(".")


async def test_a_bad_cursor_is_422(browser: Browser) -> None:
    await browser.as_new("member", "editor")

    response = await browser.http.get(LIST, params={"cursor": "nonsense"})

    assert response.status_code == 422
    assert "cursor" in response.json()["errors"]


@pytest.mark.xfail(
    strict=True,
    reason="The kernel refuses any body over MAX_BODY_BYTES (1 MB) with kernel.too_large, before media's "
    "15 MB check: a phone's photo can't be uploaded until media's upload routes may take more "
    "(asked of the owner, 2026-11-21). Remove this mark once they can.",
)
async def test_a_phones_photo_of_a_few_megabytes_is_taken(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    photo = unique_image("PNG", (1800, 1200))
    assert len(photo) > 2 * 1024 * 1024

    response = await browser.upload(photo)

    assert response.status_code == 201, response.text
