"""discography's routes over HTTP only (`dev plans/contracts/discography.md`
§2, §7): who may call each, what each answers, drafts, release day and moved
addresses, an upload made into a stream file by the job, the refusals and
the body limits, covers from the media library, credits, links, lyrics under
the setting, and what the site's server copy says of a release. Nothing here
imports discography."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ..conftest import master
from .conftest import FILES, Browser, silence, slug, unique_image

pytestmark = pytest.mark.db

API = "/api/discography"
ADMIN = f"{API}/admin/releases"
NOBODY = "00000000-0000-0000-0000-000000000001"
UNCHECKED = {"mechframe_unchecked": True}
SETTINGS = "/api/kernel/admin/settings/discography"
TRACK_LINK = "https://soundcloud.com/petrodestroys/catalyst"
SET_LINK = "https://soundcloud.com/petrodestroys/sets/catalyst"
MB = 1024 * 1024


async def _release(browser: Browser, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        ADMIN, json={"title": "An album", "slug": slug(), "artist_line": "The band", **fields}
    )
    assert made.status_code == 201, made.text
    release: dict[str, Any] = made.json()
    return release


async def _publish(browser: Browser, release_id: str, **body: Any) -> dict[str, Any]:
    published = await browser.http.post(f"{ADMIN}/{release_id}/publish", json=body)
    assert published.status_code == 200, published.text
    release: dict[str, Any] = published.json()
    return release


async def _linked(browser: Browser, release_id: str, title: str = "A track", **body: Any) -> Any:
    made = await browser.http.post(
        f"{ADMIN}/{release_id}/tracks",
        json={"title": title, "soundcloud_url": TRACK_LINK, **body},
    )
    assert made.status_code == 201, made.text
    return made.json()


async def _read(browser: Browser, at: str) -> tuple[int, dict[str, Any]]:
    answer = await browser.http.get(f"{API}/releases/{at}")
    return answer.status_code, answer.json()


async def _settings(browser: Browser, **changes: Any) -> None:
    form = await browser.http.get(SETTINGS)
    assert form.status_code == 200, form.text
    saved = await browser.http.put(
        SETTINGS, json={"version": form.json()["version"], "changes": changes}
    )
    assert saved.status_code == 200, saved.text


def _json_ld(html: str) -> list[dict[str, Any]]:
    found = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    return [json.loads(each) for each in found]


# --- who may call each route ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", ADMIN, None),
        ("POST", ADMIN, {"title": "x"}),
        ("GET", f"{ADMIN}/{NOBODY}", None),
        ("PATCH", f"{ADMIN}/{NOBODY}", {"version": 1}),
        ("DELETE", f"{ADMIN}/{NOBODY}", None),
        ("POST", f"{ADMIN}/{NOBODY}/publish", {}),
        ("POST", f"{ADMIN}/{NOBODY}/unpublish", None),
        ("POST", f"{ADMIN}/{NOBODY}/tracks", {"title": "x"}),
        ("POST", f"{ADMIN}/{NOBODY}/tracks/upload", None),
        ("GET", f"{API}/admin/tracks", None),
        ("GET", f"{API}/admin/tracks/{NOBODY}", None),
        ("PATCH", f"{API}/admin/tracks/{NOBODY}", {"version": 1}),
        ("DELETE", f"{API}/admin/tracks/{NOBODY}", None),
        ("PUT", f"{API}/admin/tracks/{NOBODY}/audio", None),
        ("DELETE", f"{API}/admin/tracks/{NOBODY}/audio", None),
        ("POST", f"{API}/admin/tracks/{NOBODY}/audio/retry", None),
        ("GET", f"{API}/admin/people", None),
        ("PATCH", f"{API}/admin/people/{NOBODY}", {"version": 1}),
        ("GET", f"{API}/admin/roles", None),
        ("PUT", f"{API}/admin/roles", {"items": [{"name": "Artist"}]}),
        ("GET", f"{API}/admin/links", None),
        ("PUT", f"{API}/admin/links", {"links": []}),
        ("GET", f"{API}/admin/plays", None),
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


async def test_every_route_declares_who_may_call_it(browser: Browser) -> None:
    audit = await browser.http.get("/api/_test/routes")
    assert audit.status_code == 200, audit.text
    said = audit.json()
    assert [each for each in said["undeclared"] if "/api/discography" in each] == []
    mine = [each for each in said["admin"] if "/api/discography/" in each]
    assert mine
    assert all(each.split(" ", 1)[1].startswith(f"{API}/admin/") for each in mine)


async def test_the_live_library_and_the_artists_links_are_open_to_anyone(
    browser: Browser,
) -> None:
    listed = await browser.http.get(f"{API}/releases")
    assert listed.status_code == 200, listed.text
    assert set(listed.json()) == {"items", "next_cursor"}
    links = await browser.http.get(f"{API}/links")
    assert (links.status_code, set(links.json())) == (200, {"items"})
    missing = await browser.http.get(f"{API}/releases/{slug()}")
    assert (missing.status_code, missing.json()["code"]) == (404, "discography.release_not_found")
    no_track = await browser.http.get(f"{API}/releases/{slug()}/tracks/{slug()}")
    assert (no_track.status_code, no_track.json()["code"]) == (404, "discography.track_not_found")
    wrong = await browser.http.get(f"{API}/releases", params={"kind": "mixtape"})
    assert wrong.status_code == 422


async def test_an_editor_and_an_admin_manage_the_library(browser: Browser) -> None:
    for role in ("editor", "admin"):
        await browser.as_new("member", role)
        assert (await browser.http.get(ADMIN)).status_code == 200
        assert (await browser.http.get(f"{API}/admin/tracks")).status_code == 200
        browser.forget()


# --- releases: drafts, saves, release day and moves ----------------------------------------


async def test_an_editor_makes_saves_publishes_unpublishes_and_deletes_a_release(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser, kind="ep", year=2024, summary="Four songs.")
    assert set(release) == {
        "id",
        "version",
        "title",
        "slug",
        "kind",
        "year",
        "artist_line",
        "cover",
        "status",
        "publish_at",
        "published_at",
        "track_count",
        "unplayable",
        "tracklist_to_come",
        "updated_at",
        "credit_line",
        "summary",
        "back_cover",
        "tracks",
        "credits",
        "links",
        "moves",
        "path",
    }
    assert (release["status"], release["version"], release["moves"]) == ("draft", 1, [])
    assert release["path"] == f"/music/{release['slug']}"
    track = await _linked(browser, release["id"], "Night Drive")
    assert (await _read(browser, release["slug"]))[0] == 404  # a draft isn't on the site
    track_page = await browser.http.get(f"{API}/releases/{release['slug']}/tracks/{track['slug']}")
    assert track_page.status_code == 404

    saved = await browser.http.patch(
        f"{ADMIN}/{release['id']}", json={"version": 1, "title": "Unified Vibration"}
    )
    assert saved.status_code == 200, saved.text
    assert (saved.json()["title"], saved.json()["version"]) == ("Unified Vibration", 2)

    live = await _publish(browser, release["id"])
    assert live["status"] == "published"
    status, shown = await _read(browser, release["slug"])
    assert status == 200
    assert (shown["title"], shown["kind"], shown["year"], shown["summary"]) == (
        "Unified Vibration",
        "ep",
        2024,
        "Four songs.",
    )
    assert [line["title"] for line in shown["tracks"]] == ["Night Drive"]
    assert shown["tracks"][0]["path"] == f"/music/{release['slug']}/{track['slug']}"
    listed = (await browser.http.get(f"{API}/releases", params={"kind": "ep"})).json()["items"]
    assert release["slug"] in [card["slug"] for card in listed]

    down = await browser.http.post(f"{ADMIN}/{release['id']}/unpublish")
    assert (down.status_code, down.json()["status"]) == (200, "draft")
    assert (await _read(browser, release["slug"]))[0] == 404

    gone = await browser.http.delete(f"{ADMIN}/{release['id']}")
    assert gone.status_code == 204
    assert (await browser.http.get(f"{ADMIN}/{release['id']}")).status_code == 404
    assert (await browser.http.get(f"{API}/admin/tracks/{track['id']}")).status_code == 404


async def test_a_stale_save_is_409_with_the_row_as_it_is_now(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    first = await browser.http.patch(f"{ADMIN}/{release['id']}", json={"version": 1, "title": "1"})
    assert first.status_code == 200, first.text
    stale = await browser.http.patch(f"{ADMIN}/{release['id']}", json={"version": 1, "title": "2"})
    assert stale.status_code == 409, stale.text
    problem = stale.json()
    assert problem["code"] == "discography.changed"
    assert (problem["release"]["title"], problem["release"]["version"]) == ("1", 2)

    track = await _linked(browser, release["id"])
    once = await browser.http.patch(
        f"{API}/admin/tracks/{track['id']}", json={"version": track["version"], "title": "One"}
    )
    assert once.status_code == 200, once.text
    again = await browser.http.patch(
        f"{API}/admin/tracks/{track['id']}", json={"version": track["version"], "title": "Two"}
    )
    assert (again.status_code, again.json()["code"]) == (409, "discography.changed")
    assert again.json()["track"]["title"] == "One"


async def test_a_taken_slug_is_409_and_a_missing_one_comes_from_the_title(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    first = await _release(browser)
    taken = await browser.http.post(ADMIN, json={"title": "Other", "slug": first["slug"]})
    assert (taken.status_code, taken.json()["code"]) == (409, "discography.slug_taken")
    assert "slug" in taken.json()["errors"]
    title = f"Fresh {uuid.uuid4().hex[:6]}"
    made = await browser.http.post(ADMIN, json={"title": title})
    assert made.status_code == 201, made.text
    assert made.json()["slug"] == title.lower().replace(" ", "-")


async def test_a_moved_release_answers_where_it_is_now_its_tracks_too(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    track = await _linked(browser, release["id"], "Night Drive")
    live = await _publish(browser, release["id"])
    first, second, third = release["slug"], slug(), slug()
    version = live["version"]
    for to in (second, third):
        moved = await browser.http.patch(
            f"{ADMIN}/{release['id']}", json={"version": version, "slug": to}
        )
        assert moved.status_code == 200, moved.text
        version = moved.json()["version"]
    assert {f"/music/{first}", f"/music/{second}"} <= set(moved.json()["moves"])
    browser.forget()

    for old in (first, second):
        status, said = await _read(browser, old)
        assert (status, said) == (200, {"moved": f"/music/{third}"})
        site = await browser.http.get(f"/music/{old}", extensions=UNCHECKED)
        assert (site.status_code, site.headers["location"]) == (301, f"/music/{third}")
    on_track = await browser.http.get(f"{API}/releases/{first}/tracks/{track['slug']}")
    assert on_track.json() == {"moved": f"/music/{third}/{track['slug']}"}
    site = await browser.http.get(f"/music/{first}/{track['slug']}", extensions=UNCHECKED)
    assert (site.status_code, site.headers["location"]) == (301, f"/music/{third}/{track['slug']}")


async def test_a_scheduled_release_goes_live_on_its_day(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    await _linked(browser, release["id"])
    at = datetime.now(UTC) + timedelta(seconds=60)
    scheduled = await _publish(browser, release["id"], at=at.isoformat())
    assert (scheduled["status"], scheduled["publish_at"] is not None) == ("scheduled", True)
    assert (await _read(browser, release["slug"]))[0] == 404

    await browser.advance(120)
    queued = await browser.http.post("/api/_test/jobs", json={"name": "kernel.publish_due"})
    assert queued.status_code == 201, queued.text
    await browser.run_jobs()
    assert (await _read(browser, release["slug"]))[0] == 200


# --- what plays ----------------------------------------------------------------------------


async def test_an_upload_is_taken_past_the_sites_body_limit_and_plays_once_processed(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    await _publish(browser, release["id"])
    data = master(8.0)
    assert len(data) > 1 * MB  # past the site's MAX_BODY_BYTES: the route takes 64 MB

    uploaded = await browser.upload_track(release["id"], data)
    assert uploaded.status_code == 201, uploaded.text
    track = uploaded.json()
    assert (track["title"], track["slug"], track["number"]) == ("Night Drive", "night-drive", 1)
    assert (track["audio"]["state"], track["audio"]["plays_from"]) == ("processing", None)
    assert track["audio"]["master_name"] == "Night Drive.wav"
    status, shown = await _read(browser, release["slug"])
    assert (status, shown["tracks"]) == (200, [])  # it can't play yet

    await browser.run_jobs()

    done = (await browser.http.get(f"{API}/admin/tracks/{track['id']}")).json()
    assert (done["audio"]["state"], done["audio"]["percent"]) == ("ready", 100)
    assert abs(done["audio"]["duration_ms"] - 8000) <= 50
    browser.forget()
    [line] = (await _read(browser, release["slug"]))[1]["tracks"]
    assert line["plays_from"] == "upload"
    assert line["stream_url"].startswith(f"{FILES}/discography/stream/")
    assert line["stream_url"].endswith(".mp3")
    assert track["id"] not in line["stream_url"]  # unguessable, so a draft's audio can't be found
    page = await browser.http.get(f"{API}/releases/{release['slug']}/tracks/{line['slug']}")
    assert page.status_code == 200, page.text
    peaks = page.json()["peaks"]
    assert len(peaks) == 1000
    assert max(peaks) == 255

    site = await browser.http.get(f"/music/{release['slug']}", extensions=UNCHECKED)
    policy = site.headers["content-security-policy"]
    media_src = next(part for part in policy.split(";") if part.strip().startswith("media-src"))
    assert FILES in media_src  # the public bucket's stream files may play


async def test_a_soundcloud_track_and_a_playlist_are_taken_and_a_profile_refused(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    one = await _linked(browser, release["id"], "Catalyst", soundcloud_url=TRACK_LINK + "/")
    whole = await _linked(browser, release["id"], "The album", soundcloud_url=SET_LINK)
    assert (one["audio"]["soundcloud_url"], one["audio"]["soundcloud_kind"]) == (
        TRACK_LINK,
        "track",
    )
    assert (whole["audio"]["soundcloud_kind"], whole["audio"]["plays_from"]) == (
        "set",
        "soundcloud",
    )
    for wrong in ("https://soundcloud.com/petrodestroys", "https://open.spotify.com/track/1"):
        refused = await browser.http.post(
            f"{ADMIN}/{release['id']}/tracks", json={"title": "No", "soundcloud_url": wrong}
        )
        assert (refused.status_code, refused.json()["code"]) == (422, "discography.not_soundcloud")
        assert "soundcloud_url" in refused.json()["errors"]

    await _publish(browser, release["id"])
    [first, second] = (await _read(browser, release["slug"]))[1]["tracks"]
    assert (first["plays_from"], first["stream_url"], first["soundcloud_url"]) == (
        "soundcloud",
        None,
        TRACK_LINK,
    )
    assert second["soundcloud_kind"] == "set"


async def test_a_track_that_cant_play_is_missing_from_every_public_answer(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    await _linked(browser, release["id"], "Plays")
    silent = await browser.http.post(f"{ADMIN}/{release['id']}/tracks", json={"title": "Waits"})
    assert silent.status_code == 201, silent.text
    assert silent.json()["audio"] == {
        **silent.json()["audio"],
        "state": "none",
        "plays_from": None,
    }
    await _publish(browser, release["id"])
    [row] = [
        each
        for each in (await browser.http.get(ADMIN)).json()["items"]
        if each["id"] == release["id"]
    ]
    assert (row["track_count"], row["unplayable"]) == (2, 1)
    cant = (await browser.http.get(f"{API}/admin/tracks", params={"show": "cant_play"})).json()
    assert silent.json()["id"] in [each["id"] for each in cant["items"]]
    browser.forget()

    shown = (await _read(browser, release["slug"]))[1]
    assert ([line["title"] for line in shown["tracks"]], shown["track_count"]) == (["Plays"], 1)
    hidden = await browser.http.get(
        f"{API}/releases/{release['slug']}/tracks/{silent.json()['slug']}"
    )
    assert hidden.status_code == 404
    cards = (await browser.http.get(f"{API}/releases")).json()["items"]
    [card] = [each for each in cards if each["slug"] == release["slug"]]
    assert card["track_count"] == 1
    sitemap = await browser.http.get("/sitemap.xml", extensions=UNCHECKED)
    assert f"/music/{release['slug']}/{silent.json()['slug']}</loc>" not in sitemap.text


# --- the refusals and the body limits ------------------------------------------------------


async def test_the_four_refusals_of_a_tracks_audio(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)

    not_audio = await browser.upload_track(release["id"], b"<html>no song</html>" * 200, "a.wav")
    assert (not_audio.status_code, not_audio.json()["code"]) == (415, "discography.not_audio")

    long = silence(61 * 60)
    assert len(long) < 1 * MB
    too_long = await browser.upload_track(release["id"], long, "set.flac")
    assert (too_long.status_code, too_long.json()["code"]) == (422, "discography.too_long")

    too_large = await browser.upload_track(release["id"], bytes(60 * MB + 1), "huge.wav")
    assert (too_large.status_code, too_large.json()["code"]) == (413, "discography.too_large")
    assert "Export it as FLAC" in too_large.json()["detail"]

    not_soundcloud = await browser.http.post(
        f"{ADMIN}/{release['id']}/tracks",
        json={"title": "A profile", "soundcloud_url": "https://soundcloud.com/petrodestroys"},
    )
    assert (not_soundcloud.status_code, not_soundcloud.json()["code"]) == (
        422,
        "discography.not_soundcloud",
    )
    after = (await browser.http.get(f"{ADMIN}/{release['id']}")).json()
    assert after["tracks"] == []  # nothing refused left a track behind


async def test_the_upload_routes_take_64_mb_and_every_other_route_the_sites_limit(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    track = await _linked(browser, release["id"])

    over = await browser.upload_track(release["id"], bytes(64 * MB + 1), "huge.wav")
    assert (over.status_code, over.json()["code"]) == (413, "kernel.too_large")
    replaced = await browser.http.put(
        f"{API}/admin/tracks/{track['id']}/audio",
        files={"file": ("huge.wav", bytes(64 * MB + 1), "application/octet-stream")},
    )
    assert (replaced.status_code, replaced.json()["code"]) == (413, "kernel.too_large")

    words = "la " * (MB // 2)  # past the site's 1 MB as JSON
    saved = await browser.http.patch(
        f"{API}/admin/tracks/{track['id']}", json={"version": track["version"], "lyrics": words}
    )
    assert (saved.status_code, saved.json()["code"]) == (413, "kernel.too_large")


# --- replacing, removing and retrying the upload -------------------------------------------


async def test_a_replaced_upload_plays_the_new_stream_and_a_removed_one_falls_back_to_the_link(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    track = (await browser.upload_track(release["id"], master(2.0))).json()
    await browser.run_jobs()
    first = (await browser.http.get(f"{API}/admin/tracks/{track['id']}")).json()
    assert first["audio"]["state"] == "ready"

    replaced = await browser.http.put(
        f"{API}/admin/tracks/{track['id']}/audio",
        files={"file": ("Take 2.wav", master(3.0), "application/octet-stream")},
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["audio"]["state"] == "processing"
    assert replaced.json()["audio"]["stream_url"] == first["audio"]["stream_url"]  # plays on
    await browser.run_jobs()
    second = (await browser.http.get(f"{API}/admin/tracks/{track['id']}")).json()
    assert abs(second["audio"]["duration_ms"] - 3000) <= 50
    assert second["audio"]["stream_url"] != first["audio"]["stream_url"]

    linked = await browser.http.patch(
        f"{API}/admin/tracks/{track['id']}",
        json={"version": second["version"], "soundcloud_url": TRACK_LINK},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["audio"]["plays_from"] == "upload"  # the upload first, the link behind it
    removed = await browser.http.delete(f"{API}/admin/tracks/{track['id']}/audio")
    assert removed.status_code == 200, removed.text
    assert (removed.json()["audio"]["state"], removed.json()["audio"]["plays_from"]) == (
        "none",
        "soundcloud",
    )
    nothing = await browser.http.post(f"{API}/admin/tracks/{track['id']}/audio/retry")
    assert (nothing.status_code, nothing.json()["code"]) == (409, "discography.nothing_to_retry")


# --- covers, credits, roles and links ------------------------------------------------------


async def test_covers_are_library_images_whose_uses_are_recorded_and_let_go(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    front = (await browser.upload_image(unique_image())).json()
    back = (await browser.upload_image(unique_image())).json()
    missing = await browser.http.post(ADMIN, json={"title": "X", "cover_id": str(uuid.uuid4())})
    assert (missing.status_code, missing.json()["code"]) == (422, "discography.cover_not_found")

    release = await _release(browser, title="Covered", cover_id=front["id"])
    assert release["cover"]["url"] == front["url"]
    saved = await browser.http.patch(
        f"{ADMIN}/{release['id']}", json={"version": 1, "back_cover_id": back["id"]}
    )
    assert saved.json()["back_cover"]["url"] == back["url"]
    use = {"label": "Covered", "link": f"/admin/music/{release['id']}"}
    for image in (front, back):
        uses = (await browser.http.get(f"/api/media/admin/images/{image['id']}")).json()["uses"]
        assert use in uses

    await _linked(browser, release["id"])
    await _publish(browser, release["id"])
    site = await browser.http.get(f"/music/{release['slug']}", extensions=UNCHECKED)
    assert f'<meta property="og:image" content="{front["url"]}"' in site.text

    version = (await browser.http.get(f"{ADMIN}/{release['id']}")).json()["version"]
    cleared = await browser.http.patch(
        f"{ADMIN}/{release['id']}", json={"version": version, "cover_id": None}
    )
    assert (cleared.status_code, cleared.json()["cover"]) == (200, None)
    uses = (await browser.http.get(f"/api/media/admin/images/{front['id']}")).json()["uses"]
    assert use not in uses
    uses = (await browser.http.get(f"/api/media/admin/images/{back['id']}")).json()["uses"]
    assert use in uses


async def test_credits_name_people_the_credits_board_gathers_and_a_used_role_stays(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    roles = (await browser.http.get(f"{API}/admin/roles")).json()["items"]
    by_name = {each["name"]: each["id"] for each in roles}
    assert {"Artist", "Featuring", "Produced by", "Written by", "Mastered by"} <= set(by_name)
    name = f"Petro {uuid.uuid4().hex[:6]}"
    release = await _release(browser, title="Credited")
    saved = await browser.http.patch(
        f"{ADMIN}/{release['id']}",
        json={
            "version": 1,
            "credits": [
                {"role_id": by_name["Artist"], "name": name},
                {"role_id": by_name["Produced by"], "name": f" {name} "},
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert [(each["role"], each["name"]) for each in saved.json()["credits"]] == [
        ("Artist", name),
        ("Produced by", name),
    ]
    people = (await browser.http.get(f"{API}/admin/people")).json()
    [person] = [each for each in people["items"] if each["name"] == name]
    assert (person["credits"], person["profile"]) == (2, "unlinked")
    assert "Credited" in person["credited_for"]

    renamed = await browser.http.patch(
        f"{API}/admin/people/{person['id']}",
        json={"version": person["version"], "profile": "collective"},
    )
    assert renamed.status_code == 200, renamed.text
    member = await browser.http.patch(
        f"{API}/admin/people/{person['id']}", json={"version": 2, "profile": "member"}
    )
    assert member.status_code == 422  # roster sets that, in step 3

    keep = [{"id": each["id"], "name": each["name"]} for each in roles if each["name"] != "Artist"]
    in_use = await browser.http.put(f"{API}/admin/roles", json={"items": keep})
    assert (in_use.status_code, in_use.json()["code"]) == (409, "discography.role_in_use")

    cleared = await browser.http.patch(
        f"{ADMIN}/{release['id']}", json={"version": 2, "credits": []}
    )
    assert cleared.status_code == 200, cleared.text
    people = (await browser.http.get(f"{API}/admin/people")).json()["items"]
    assert name not in [each["name"] for each in people]  # gone with its last credit


async def test_streaming_links_are_read_by_their_platform_one_a_platform(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    spotify = "https://open.spotify.com/artist/0abc"
    bandcamp = "https://vibrantmindz.bandcamp.com/"
    put = await browser.http.put(f"{API}/admin/links", json={"links": [spotify, bandcamp]})
    assert put.status_code == 200, put.text
    assert [(each["platform"], each["label"]) for each in put.json()["items"]] == [
        ("spotify", "Spotify"),
        ("bandcamp", "Bandcamp"),
    ]
    twice = await browser.http.put(f"{API}/admin/links", json={"links": [spotify, spotify]})
    assert (twice.status_code, twice.json()["code"]) == (422, "discography.platform_twice")
    off = await browser.http.put(f"{API}/admin/links", json={"links": ["https://example.com/me"]})
    assert (off.status_code, off.json()["code"]) == (422, "discography.not_a_platform")

    release = await _release(browser)
    await _linked(browser, release["id"])
    linked = await browser.http.patch(
        f"{ADMIN}/{release['id']}", json={"version": 1, "links": [spotify]}
    )
    assert linked.status_code == 200, linked.text
    await _publish(browser, release["id"])
    browser.forget()
    assert [each["url"] for each in (await browser.http.get(f"{API}/links")).json()["items"]] == [
        spotify,
        bandcamp,
    ]
    assert (await _read(browser, release["slug"]))[1]["links"][0]["platform"] == "spotify"


async def test_lyrics_show_on_a_tracks_page_while_the_setting_is_on(browser: Browser) -> None:
    await browser.as_new("member", "admin")
    release = await _release(browser)
    track = await _linked(browser, release["id"], "Pray For You")
    words = "Pray for you\nevery night"
    saved = await browser.http.patch(
        f"{API}/admin/tracks/{track['id']}",
        json={"version": track["version"], "lyrics": words, "explicit": True},
    )
    assert saved.status_code == 200, saved.text
    await _publish(browser, release["id"])
    page = f"{API}/releases/{release['slug']}/tracks/{track['slug']}"
    shown = (await browser.http.get(page)).json()
    assert (shown["lyrics"], shown["has_lyrics"], shown["explicit"]) == (words, True, True)
    assert (await _read(browser, release["slug"]))[1]["explicit"] is True

    await _settings(browser, show_lyrics=False, show_explicit_badge=False)
    try:
        hidden = (await browser.http.get(page)).json()
        assert hidden["lyrics"] is None
        site = await browser.http.get(
            f"/music/{release['slug']}/{track['slug']}", extensions=UNCHECKED
        )
        assert "every night" not in site.text
        assert (await _read(browser, release["slug"]))[1]["explicit"] is False
    finally:
        await _settings(browser, show_lyrics=True, show_explicit_badge=True)


# --- the server's copy ---------------------------------------------------------------------


async def test_the_server_copy_of_a_release_a_track_the_library_and_a_draft(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(
        browser, title="Catalyst", kind="album", year=2025, summary="The first record."
    )
    track = (await browser.upload_track(release["id"], master(2.0), "Night Drive.wav")).json()
    await browser.run_jobs()
    draft = await _release(browser)
    await _linked(browser, draft["id"])
    await _publish(browser, release["id"])
    stream = (await browser.http.get(f"{API}/admin/tracks/{track['id']}")).json()["audio"][
        "stream_url"
    ]
    browser.forget()

    served = await browser.http.get(f"/music/{release['slug']}", extensions=UNCHECKED)
    assert served.status_code == 200, served.text
    html = served.text
    assert "<title>Catalyst · " in html
    assert "<h1>Catalyst</h1>" in html
    (album,) = [each for each in _json_ld(html) if each.get("@type") == "MusicAlbum"]
    assert album["name"] == "Catalyst"
    assert album["url"].endswith(f"/music/{release['slug']}")
    [item] = album["track"]["itemListElement"]
    assert (item["item"]["@type"], item["item"]["name"]) == ("MusicRecording", "Night Drive")
    assert item["item"]["duration"].startswith("PT")

    on_track = await browser.http.get(
        f"/music/{release['slug']}/{track['slug']}", extensions=UNCHECKED
    )
    assert on_track.status_code == 200, on_track.text
    (recording,) = [
        each for each in _json_ld(on_track.text) if each.get("@type") == "MusicRecording"
    ]
    assert recording["inAlbum"]["name"] == "Catalyst"

    library = await browser.http.get("/music", extensions=UNCHECKED)
    assert library.status_code == 200, library.text
    assert any(each.get("@type") == "ItemList" for each in _json_ld(library.text))
    assert (
        await browser.http.get(f"/music/{draft['slug']}", extensions=UNCHECKED)
    ).status_code == 404

    sitemap = (await browser.http.get("/sitemap.xml", extensions=UNCHECKED)).text
    llms = (await browser.http.get("/llms.txt", extensions=UNCHECKED)).text
    assert f"/music/{release['slug']}</loc>" in sitemap
    assert f"/music/{release['slug']}/{track['slug']}</loc>" in sitemap
    assert f"/music/{draft['slug']}</loc>" not in sitemap
    assert "[Catalyst](" in llms
    for text in (html, on_track.text, library.text, sitemap, llms):
        assert stream not in text  # no audio address goes to crawlers
        assert "/discography/stream/" not in text


# --- plays (0.1.1, `dev plans/contracts/audio-player.md` §2 and §7) -----------------------


async def _week(browser: Browser) -> dict[str, Any]:
    read = await browser.http.get(f"{API}/admin/plays")
    assert read.status_code == 200, read.text
    week: dict[str, Any] = read.json()
    return week


async def test_a_play_counts_once_for_a_live_track_that_plays_and_never_for_a_draft(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    release = await _release(browser)
    plays = await _linked(browser, release["id"], f"Heard {uuid.uuid4().hex[:6]}")
    silent = await browser.http.post(f"{ADMIN}/{release['id']}/tracks", json={"title": "Waits"})
    assert silent.status_code == 201, silent.text
    await _publish(browser, release["id"])
    draft = await _linked(browser, (await _release(browser))["id"])
    shown = (await _read(browser, release["slug"]))[1]
    assert [line["id"] for line in shown["tracks"]] == [plays["id"]]
    before = await _week(browser)
    browser.forget()

    for each in (plays["id"], plays["id"], silent.json()["id"], draft["id"], NOBODY):
        answer = await browser.http.post(f"{API}/tracks/{each}/plays")
        assert (answer.status_code, answer.content) == (204, b""), answer.text
    assert (await browser.http.post(f"{API}/tracks/not-an-id/plays")).status_code == 422

    await browser.as_new("member", "editor")
    after = await _week(browser)
    assert after["this_week"] == before["this_week"] + 1
    assert set(after) == {"this_week", "last_week", "leading"}


async def test_the_61st_play_in_an_hour_from_one_address_is_429(browser: Browser) -> None:
    for _ in range(60):
        answer = await browser.http.post(f"{API}/tracks/{NOBODY}/plays")
        assert answer.status_code == 204, answer.text
    sixty_first = await browser.http.post(f"{API}/tracks/{NOBODY}/plays")
    assert sixty_first.status_code == 429, sixty_first.text
    assert sixty_first.json()["code"] == "kernel.rate_limited"
