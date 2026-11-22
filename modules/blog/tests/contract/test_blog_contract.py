"""The blog's routes over HTTP only (`dev plans/contracts/blog.md` §2, §7):
who may call each, what each answers, the categories through the kernel's
term routes, a cover from the media library, and what the site's server copy
says of a post. Nothing here imports blog."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from .conftest import Browser, slug, unique_image

pytestmark = pytest.mark.db

ADMIN = "/api/blog/admin/posts"
NOBODY = "00000000-0000-0000-0000-000000000001"
UNCHECKED = {"mechframe_unchecked": True}


async def _post(browser: Browser, **fields: Any) -> dict[str, Any]:
    made = await browser.http.post(
        ADMIN, json={"title": "A post", "slug": slug(), "body": "Some words.", **fields}
    )
    assert made.status_code == 201, made.text
    post: dict[str, Any] = made.json()
    return post


async def _publish(browser: Browser, post_id: str, **body: Any) -> dict[str, Any]:
    published = await browser.http.post(f"{ADMIN}/{post_id}/publish", json=body)
    assert published.status_code == 200, published.text
    post: dict[str, Any] = published.json()
    return post


async def _read(browser: Browser, at: str) -> tuple[int, dict[str, Any]]:
    answer = await browser.http.get(f"/api/blog/posts/{at}")
    return answer.status_code, answer.json()


async def _category(browser: Browser, label: str = "News") -> str:
    """A category of the test's own, through the kernel's term routes."""
    term = f"c-{uuid.uuid4().hex[:10]}"
    made = await browser.http.post(
        "/api/kernel/admin/terms",
        json={"vocabulary": "blog_category", "slug": term, "label": label},
    )
    assert made.status_code == 201, made.text
    return term


# --- who may call each route ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", ADMIN, None),
        ("POST", ADMIN, {"title": "x"}),
        ("GET", f"{ADMIN}/{NOBODY}", None),
        ("PATCH", f"{ADMIN}/{NOBODY}", {"version": 1}),
        ("POST", "/api/blog/admin/preview", {"body": "Hi"}),
        ("POST", f"{ADMIN}/{NOBODY}/publish", {}),
        ("POST", f"{ADMIN}/{NOBODY}/unpublish", None),
        ("DELETE", f"{ADMIN}/{NOBODY}", None),
        ("GET", "/api/blog/admin/categories", None),
        ("GET", "/api/blog/admin/authors", None),
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


async def test_the_live_posts_and_the_categories_are_open_to_anyone(browser: Browser) -> None:
    missing = await browser.http.get(f"/api/blog/posts/{slug()}")
    assert (missing.status_code, missing.json()["code"]) == (404, "blog.post_not_found")
    listed = await browser.http.get("/api/blog/posts")
    assert listed.status_code == 200, listed.text
    assert set(listed.json()) == {"items", "next_cursor"}
    categories = await browser.http.get("/api/blog/categories")
    assert categories.status_code == 200, categories.text
    wrong = await browser.http.get("/api/blog/posts", params={"category": "Not A Slug"})
    assert wrong.status_code == 422


# --- writing, saving and publishing --------------------------------------------------------


async def test_an_editor_writes_saves_publishes_unpublishes_and_deletes(browser: Browser) -> None:
    editor = await browser.as_new("member", "editor")
    post = await _post(browser, body="Hello **there**.", summary="One line.")
    assert set(post) == {
        "id",
        "title",
        "slug",
        "status",
        "category",
        "author",
        "publish_at",
        "published_at",
        "updated_at",
        "has_cover",
        "summary",
        "body",
        "cover_id",
        "cover",
        "search_title",
        "search_description",
        "allow_comments",
        "post_to_community",
        "email_subscribers",
        "version",
        "moves",
        "related",
    }
    assert (post["status"], post["version"], post["moves"]) == ("draft", 1, [])
    assert post["author"]["id"] == editor.id  # whoever writes it, by default
    assert (await _read(browser, post["slug"]))[0] == 404  # a draft isn't on the site

    preview = await browser.http.post("/api/blog/admin/preview", json={"body": "# Hi\n\n**Bold**"})
    assert preview.status_code == 200, preview.text
    assert preview.json()["html"] == "<h2>Hi</h2>\n<p><strong>Bold</strong></p>"

    saved = await browser.http.patch(
        f"{ADMIN}/{post['id']}", json={"version": 1, "title": "Hello", "search_title": "Hi there"}
    )
    assert saved.status_code == 200, saved.text
    assert (saved.json()["title"], saved.json()["version"]) == ("Hello", 2)

    live = await _publish(browser, post["id"])
    assert live["status"] == "published"
    status, shown = await _read(browser, post["slug"])
    assert status == 200
    assert (shown["title"], shown["search_title"], shown["summary"]) == (
        "Hello",
        "Hi there",
        "One line.",
    )
    assert shown["html"] == "<p>Hello <strong>there</strong>.</p>"
    assert shown["search_description"] == "One line."
    assert shown["reading_minutes"] == 1
    assert "email" not in json.dumps(shown)

    down = await browser.http.post(f"{ADMIN}/{post['id']}/unpublish")
    assert (down.status_code, down.json()["status"]) == (200, "draft")
    assert (await _read(browser, post["slug"]))[0] == 404

    gone = await browser.http.delete(f"{ADMIN}/{post['id']}")
    assert gone.status_code == 204
    assert (await browser.http.get(f"{ADMIN}/{post['id']}")).status_code == 404


async def test_a_stale_save_is_409_with_the_post_as_it_is_now(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    post = await _post(browser)
    first = await browser.http.patch(f"{ADMIN}/{post['id']}", json={"version": 1, "title": "One"})
    assert first.status_code == 200, first.text
    stale = await browser.http.patch(f"{ADMIN}/{post['id']}", json={"version": 1, "title": "Two"})
    assert stale.status_code == 409, stale.text
    problem = stale.json()
    assert problem["code"] == "blog.changed"
    assert (problem["post"]["title"], problem["post"]["version"]) == ("One", 2)


async def test_a_taken_slug_is_409_and_a_missing_one_comes_from_the_title(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    first = await _post(browser, title="Taken")
    taken = await browser.http.post(ADMIN, json={"title": "Other", "slug": first["slug"]})
    assert (taken.status_code, taken.json()["code"]) == (409, "blog.slug_taken")
    assert "slug" in taken.json()["errors"]
    title = f"Fresh {uuid.uuid4().hex[:6]}"
    made = await browser.http.post(ADMIN, json={"title": title})
    assert made.status_code == 201, made.text
    assert made.json()["slug"] == title.lower().replace(" ", "-")


async def test_a_moved_slug_answers_where_the_post_is_now(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    post = await _post(browser)
    await _publish(browser, post["id"])
    first, second, third = post["slug"], slug(), slug()
    version = post["version"]
    for to in (second, third):
        moved = await browser.http.patch(
            f"{ADMIN}/{post['id']}", json={"version": version, "slug": to}
        )
        assert moved.status_code == 200, moved.text
        version = moved.json()["version"]
    assert sorted(moved.json()["moves"]) == sorted([first, second])
    browser.forget()

    for old in (first, second):
        status, said = await _read(browser, old)
        assert (status, said) == (200, {"moved": f"/blog/{third}"})
        site = await browser.http.get(f"/blog/{old}", extensions=UNCHECKED)
        assert (site.status_code, site.headers["location"]) == (301, f"/blog/{third}")


async def test_a_scheduled_post_goes_live_once_its_time_comes(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    post = await _post(browser)
    at = datetime.now(UTC) + timedelta(seconds=60)
    scheduled = await _publish(browser, post["id"], at=at.isoformat())
    assert (scheduled["status"], scheduled["publish_at"] is not None) == ("scheduled", True)
    assert (await _read(browser, post["slug"]))[0] == 404
    waiting = (await browser.http.get(ADMIN)).json()["needs_cover"]
    assert waiting is not None
    assert waiting["publish_at"] is not None

    await browser.advance(120)
    queued = await browser.http.post("/api/_test/jobs", json={"name": "kernel.publish_due"})
    assert queued.status_code == 201, queued.text
    await browser.run_jobs()
    assert (await _read(browser, post["slug"]))[0] == 200


async def test_the_admin_list_filters_by_state_and_words(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    mark = uuid.uuid4().hex[:8]
    draft = await _post(browser, title=f"Draft {mark}")
    live = await _post(browser, title=f"Live {mark}")
    await _publish(browser, live["id"])
    every = (await browser.http.get(ADMIN, params={"q": mark})).json()["items"]
    assert {each["id"] for each in every} == {draft["id"], live["id"]}
    only = (await browser.http.get(ADMIN, params={"q": mark, "status": "published"})).json()
    assert [each["id"] for each in only["items"]] == [live["id"]]
    wrong = await browser.http.get(ADMIN, params={"status": "live"})
    assert wrong.status_code == 422


# --- categories, covers, authors and related posts -----------------------------------------


async def test_categories_come_from_the_kernels_terms_and_filter_the_list(
    browser: Browser,
) -> None:
    await browser.as_new("member", "editor")
    term = await _category(browser, "Poetry")
    unknown = await browser.http.post(ADMIN, json={"title": "X", "category": "no-such-one"})
    assert (unknown.status_code, unknown.json()["code"]) == (422, "blog.category_not_found")

    filed = await _post(browser, category=term)
    assert filed["category"] == {"slug": term, "label": "Poetry"}
    await _publish(browser, filed["id"])
    await _post(browser, category=term)  # a draft: counted by the admin only

    admin = (await browser.http.get("/api/blog/admin/categories")).json()["items"]
    (mine,) = [each for each in admin if each["slug"] == term]
    assert (mine["label"], mine["posts"]) == ("Poetry", 2)
    browser.forget()

    listed = (await browser.http.get("/api/blog/posts", params={"category": term})).json()
    assert [card["slug"] for card in listed["items"]] == [filed["slug"]]
    assert listed["items"][0]["category"] == {"slug": term, "label": "Poetry"}
    public = (await browser.http.get("/api/blog/categories")).json()["items"]
    assert {"slug": term, "label": "Poetry", "posts": 1} in public


async def test_a_cover_is_a_library_image_whose_use_is_recorded(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    uploaded = await browser.upload(unique_image())
    assert uploaded.status_code == 201, uploaded.text
    image = uploaded.json()
    missing = await browser.http.post(ADMIN, json={"title": "X", "cover_id": str(uuid.uuid4())})
    assert (missing.status_code, missing.json()["code"]) == (422, "blog.cover_not_found")

    post = await _post(browser, title="Covered", cover_id=image["id"])
    assert (post["cover_id"], post["has_cover"]) == (image["id"], True)
    assert post["cover"]["url"] == image["url"]
    placed = (await browser.http.get(f"/api/media/admin/images/{image['id']}")).json()["uses"]
    assert {"label": "Covered", "link": f"/admin/blog/{post['id']}"} in placed

    live = await _publish(browser, post["id"])
    site = await browser.http.get(f"/blog/{post['slug']}", extensions=UNCHECKED)
    assert f'<meta property="og:image" content="{image["url"]}"' in site.text

    cleared = await browser.http.patch(
        f"{ADMIN}/{post['id']}", json={"version": live["version"], "cover_id": None}
    )
    assert (cleared.status_code, cleared.json()["cover"]) == (200, None)
    placed = (await browser.http.get(f"/api/media/admin/images/{image['id']}")).json()["uses"]
    assert all(each["link"] != f"/admin/blog/{post['id']}" for each in placed)


async def test_the_authors_are_those_who_may_write(browser: Browser) -> None:
    member = await browser.person("member")
    editor = await browser.as_new("member", "editor")
    names = {
        each["id"] for each in (await browser.http.get("/api/blog/admin/authors")).json()["items"]
    }
    assert editor.id in names
    assert member.id not in names
    refused = await browser.http.post(ADMIN, json={"title": "X", "author_id": member.id})
    assert (refused.status_code, refused.json()["code"]) == (422, "blog.author_not_allowed")


async def test_a_new_post_names_its_writer_unless_it_names_no_one(browser: Browser) -> None:
    """Codex on #123: an author left out is the writer; one sent as null is no one."""
    writer = await browser.as_new("member", "editor")
    named = await _post(browser)
    assert named["author"]["id"] == writer.id
    nobody = await _post(browser, author_id=None)
    assert nobody["author"] is None


async def test_related_posts_are_live_ones_shown_in_order(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    one, two = await _post(browser, title="One"), await _post(browser, title="Two")
    draft = await _post(browser, title="Draft")
    for each in (one, two):
        await _publish(browser, each["id"])
    refused = await browser.http.post(ADMIN, json={"title": "X", "related": [draft["id"]]})
    assert (refused.status_code, refused.json()["code"]) == (422, "blog.related_refused")
    four = await browser.http.post(
        ADMIN, json={"title": "X", "related": [one["id"], two["id"], one["id"], two["id"]]}
    )
    assert four.status_code == 422

    post = await _post(browser, related=[two["id"], one["id"]])
    assert [each["id"] for each in post["related"]] == [two["id"], one["id"]]
    await _publish(browser, post["id"])
    shown = (await _read(browser, post["slug"]))[1]
    assert shown["related"] == [
        {"title": "Two", "slug": two["slug"]},
        {"title": "One", "slug": one["slug"]},
    ]


# --- the server's copy ---------------------------------------------------------------------


def _json_ld(html: str) -> list[dict[str, Any]]:
    found = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    return [json.loads(each) for each in found]


async def test_the_server_copy_of_a_live_post_the_blog_and_a_draft(browser: Browser) -> None:
    await browser.as_new("member", "editor")
    post = await _post(
        browser, title="Ten years", summary="A decade of shows.", body="## Then\n\nA **room**."
    )
    draft = await _post(browser)
    await _publish(browser, post["id"])
    browser.forget()

    served = await browser.http.get(f"/blog/{post['slug']}", extensions=UNCHECKED)
    assert served.status_code == 200, served.text
    html = served.text
    assert "<title>Ten years · " in html
    assert '<meta name="description" content="A decade of shows." />' in html
    assert "<h1>Ten years</h1>" in html
    assert "<p>A <strong>room</strong>.</p>" in html
    (data,) = [each for each in _json_ld(html) if each.get("@type") == "BlogPosting"]
    assert data["headline"] == "Ten years"
    assert data["url"].endswith(f"/blog/{post['slug']}")

    assert (
        await browser.http.get(f"/blog/{draft['slug']}", extensions=UNCHECKED)
    ).status_code == 404
    blog = await browser.http.get("/blog", extensions=UNCHECKED)
    assert blog.status_code == 200, blog.text
    # The blog's first page is the API's: other tests' posts may be newer than this one.
    newest = (await browser.http.get("/api/blog/posts")).json()["items"]
    linked = re.findall(r'<h2><a href="/blog/([a-z0-9-]+)">', blog.text)
    assert linked == [card["slug"] for card in newest]
    assert any(each.get("@type") == "Blog" for each in _json_ld(blog.text))

    sitemap = await browser.http.get("/sitemap.xml", extensions=UNCHECKED)
    assert f"/blog/{post['slug']}</loc>" in sitemap.text
    assert f"/blog/{draft['slug']}</loc>" not in sitemap.text
    llms = await browser.http.get("/llms.txt", extensions=UNCHECKED)
    assert "[Ten years](" in llms.text
