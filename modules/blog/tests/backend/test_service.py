"""The blog's rules on the database (`dev plans/contracts/blog.md` §2, §3, §7):
slugs and the moves they leave, saves that cross, categories, covers,
authors, related posts, the lists, search, the announcement, and the hooks."""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from blog import dashboard, events, service
from blog import privacy as blog_privacy
from blog.models import Post, Related, SlugMove
from blog.seed import _NAMESPACE, POSTS
from blog.server_copy import PAGES
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, Problem, clock, lifecycle, load_module, privacy, server_copy, taxonomy
from kernel import events as kernel_events
from kernel import seed as seeding
from kernel.models import SearchDocument

from ..conftest import make_image, make_person, slug

pytestmark = pytest.mark.db

MODULE = Path(__file__).resolve().parents[2]


async def _new(db: AsyncSession, by: uuid.UUID | None = None, **fields: Any) -> Post:
    post = await service.create(
        db, {"title": "A post", "slug": slug(), "body": "Some words.", **fields}, by=by
    )
    await db.commit()
    return post


async def _live(db: AsyncSession, **fields: Any) -> Post:
    post = await _new(db, **fields)
    await service.publish(db, post.id, None, by=None)
    await db.commit()
    return post


async def _category(db: AsyncSession, label: str = "News") -> str:
    """A category of the test's own, committed."""
    found = taxonomy.vocabulary("blog_category")
    assert found is not None
    term = f"c-{uuid.uuid4().hex[:10]}"
    await taxonomy.create(
        db, found, slug=term, label=label, parent_id=None, position=0, actor=await make_person(db)
    )
    await db.commit()
    return term


async def _save(db: AsyncSession, post: Post, **fields: Any) -> Post:
    saved = await service.change(db, post.id, post.version, fields, by=None)
    await db.commit()
    return saved


# --- slugs ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "made"),
    [
        ("Don't stop the music!", "dont-stop-the-music"),
        ("Rap battles: round 2", "rap-battles-round-2"),
        ("Café Ñandú", "cafe-nandu"),
        ("  --  ", ""),
    ],
)
def test_a_title_spells_its_slug(title: str, made: str) -> None:
    assert service.slug_for(title) == made


def test_a_long_title_spells_a_slug_that_fits() -> None:
    made = service.slug_for("word " * 40)
    assert len(made) <= 80
    assert not made.endswith("-")


async def test_a_post_without_a_slug_takes_one_from_its_title_numbered_when_taken(
    db: AsyncSession,
) -> None:
    title = f"Spring {uuid.uuid4().hex[:8]}"
    first = await service.create(db, {"title": title}, by=None)
    second = await service.create(db, {"title": title}, by=None)
    nothing = await service.create(db, {"title": "!!!"}, by=None)
    await db.commit()
    assert first.slug == service.slug_for(title)
    assert second.slug == f"{first.slug}-2"
    assert nothing.slug.startswith("post")


async def test_a_slug_another_post_has_is_refused(db: AsyncSession) -> None:
    taken = await _new(db, title="First")
    with pytest.raises(Problem) as refused:
        await service.create(db, {"title": "Second", "slug": taken.slug}, by=None)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.slug_taken", 409)
    assert "First" in refused.value.detail


async def test_a_stale_save_is_refused_with_the_post_as_it_is_now(db: AsyncSession) -> None:
    post = await _new(db)
    await _save(db, post, title="Theirs")
    with pytest.raises(Problem) as refused:
        await service.change(db, post.id, 1, {"title": "Mine"}, by=None)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.changed", 409)
    assert refused.value.extra["post"]["title"] == "Theirs"
    assert refused.value.extra["post"]["version"] == 2


async def test_a_live_post_given_a_new_slug_leaves_a_move_and_none_chains(
    db: AsyncSession,
) -> None:
    post = await _live(db)
    first, second, third = post.slug, slug(), slug()
    post = await _save(db, post, slug=second)
    post = await _save(db, post, slug=third)

    for old in (first, second):
        found = await service.live(db, old)
        assert isinstance(found, SlugMove)
        assert await service.moved_to(db, found) == f"/blog/{third}"
    assert isinstance(await service.live(db, third), Post)
    assert await service.moves_of(db, post.id) == sorted([first, second])


async def test_a_draft_given_a_new_slug_leaves_no_move(db: AsyncSession) -> None:
    post = await _new(db)
    old = post.slug
    await _save(db, post, slug=slug())
    assert await db.scalar(select(SlugMove).where(SlugMove.slug == old)) is None


async def test_a_post_that_takes_a_moved_slug_ends_the_move(db: AsyncSession) -> None:
    moved = await _live(db)
    old = moved.slug
    await _save(db, moved, slug=slug())
    taker = await _live(db, slug=old)
    found = await service.live(db, old)
    assert isinstance(found, Post)
    assert found.id == taker.id
    assert await db.scalar(select(SlugMove).where(SlugMove.slug == old)) is None


async def test_a_draft_or_an_unpublished_post_isnt_on_the_site(db: AsyncSession) -> None:
    draft = await _new(db)
    assert await service.live(db, draft.slug) is None
    gone = await _live(db)
    old = gone.slug
    gone = await _save(db, gone, slug=slug())
    await service.unpublish(db, gone.id, by=None)
    await db.commit()
    assert await service.live(db, gone.slug) is None
    assert await service.live(db, old) is None  # its moves go quiet with it


@pytest.mark.parametrize("given", ["", "UPPER", "two--hyphens", "-edge", "x" * 81, "a/b"])
async def test_a_slug_that_isnt_one_finds_nothing(db: AsyncSession, given: str) -> None:
    assert await service.live(db, given) is None


async def test_a_field_that_cant_be_empty_sent_as_null_is_left_as_it_is(db: AsyncSession) -> None:
    post = await _new(db, summary="Kept")
    saved = await _save(db, post, title=None, slug=None, summary=None, allow_comments=None)
    assert (saved.title, saved.summary, saved.allow_comments) == ("A post", "Kept", True)


# --- categories ----------------------------------------------------------------------------


async def test_a_post_takes_one_existing_category_and_can_lose_it(db: AsyncSession) -> None:
    news = await _category(db, "News")
    with pytest.raises(Problem) as refused:
        await service.create(db, {"title": "X", "category": "no-such-category"}, by=None)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.category_not_found", 422)

    post = await _live(db, category=news)
    (card,) = await service.cards(db, [post])
    assert card["category"] == {"slug": news, "label": "News"}

    other = await _category(db, "Poetry")
    post = await _save(db, post, category=other)
    assert (await service.categories_of(db, [post.id]))[post.id] == {
        "slug": other,
        "label": "Poetry",
    }
    post = await _save(db, post, category=None)
    assert (await service.categories_of(db, [post.id]))[post.id] is None


async def test_a_category_counts_its_live_posts_and_all_of_them(db: AsyncSession) -> None:
    term = await _category(db)
    await _live(db, category=term)
    await _new(db, category=term)
    live = {each["slug"]: each["posts"] for each in await service.counted(db, live=True)}
    every = {each["slug"]: each["posts"] for each in await service.counted(db, live=False)}
    assert (live[term], every[term]) == (1, 2)


async def test_a_deleted_post_loses_its_terms(db: AsyncSession) -> None:
    term = await _category(db)
    post = await _new(db, category=term)
    await service.remove(db, post.id, by=None)
    await db.commit()
    held = await taxonomy.terms_for(db, "blog.post", [post.id])
    assert held[post.id] == []


# --- covers --------------------------------------------------------------------------------


async def _uses(db: AsyncSession, post_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await db.execute(
        text("SELECT image_id FROM media_use WHERE owner = :owner ORDER BY image_id"),
        {"owner": f"blog.post:{post_id}"},
    )
    return [row.image_id for row in rows]


async def test_a_cover_is_the_libraries_image_and_its_use_is_recorded_and_released(
    db: AsyncSession,
) -> None:
    with pytest.raises(Problem) as refused:
        await service.create(db, {"title": "X", "cover_id": str(uuid.uuid4())}, by=None)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.cover_not_found", 422)

    first, second = await make_image(db, "The crowd"), await make_image(db)
    post = await _live(db, cover_id=str(first))
    assert await _uses(db, post.id) == [first]
    (card,) = await service.cards(db, [post])
    assert card["cover"]["id"] == str(first)
    assert card["cover"]["alt"] == "The crowd"
    assert card["cover"]["url"].endswith(f"media/{first}/1.png")

    post = await _save(db, post, cover_id=str(second))
    assert await _uses(db, post.id) == [second]
    post = await _save(db, post, cover_id=None)
    assert await _uses(db, post.id) == []

    post = await _save(db, post, cover_id=str(first))
    await service.remove(db, post.id, by=None)
    await db.commit()
    assert await _uses(db, post.id) == []


async def test_a_new_title_renames_the_covers_use(db: AsyncSession) -> None:
    image = await make_image(db)
    post = await _new(db, cover_id=str(image))
    await _save(db, post, title="Renamed")
    label = await db.scalar(
        text("SELECT label FROM media_use WHERE owner = :owner"),
        {"owner": f"blog.post:{post.id}"},
    )
    assert label == "Renamed"


# --- authors -------------------------------------------------------------------------------


async def test_the_author_is_someone_who_may_write_and_readers_see_only_a_name(
    db: AsyncSession,
) -> None:
    writer = await make_person(db, "Ana Writer", role="editor")
    nameless = await make_person(db, None, role="editor")
    member = await make_person(db, "Ben Member", role="member")
    names = {each["id"]: each["name"] for each in await service.authors(db)}
    assert names[str(writer)] == "Ana Writer"
    assert names[str(nameless)].endswith("@example.test")  # staff see who it is
    assert str(member) not in names

    with pytest.raises(Problem) as refused:
        await service.create(db, {"title": "X", "author_id": str(member)}, by=writer)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.author_not_allowed", 422)

    post = await _live(db, by=writer)
    (card,) = await service.cards(db, [post])
    assert card["author"] == "Ana Writer"
    post = await _save(db, post, author_id=str(nameless))
    (card,) = await service.cards(db, [post])
    assert card["author"] is None  # never an address on the site
    (listed,) = await service.listed(db, [post])
    assert listed["author"] == {"id": str(nameless), "name": names[str(nameless)]}


# --- related posts -------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["itself", "twice", "draft", "missing"])
async def test_related_posts_are_live_others_each_once(db: AsyncSession, case: str) -> None:
    post = await _new(db)
    live = await _live(db)
    draft = await _new(db)
    wanted = {
        "itself": [str(post.id)],
        "twice": [str(live.id), str(live.id)],
        "draft": [str(draft.id)],
        "missing": [str(uuid.uuid4())],
    }[case]
    with pytest.raises(Problem) as refused:
        await service.change(db, post.id, post.version, {"related": wanted}, by=None)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.related_refused", 422)


async def test_related_posts_keep_their_order_and_one_unpublished_drops_off(
    db: AsyncSession,
) -> None:
    one, two, three = await _live(db), await _live(db), await _live(db)
    post = await _live(db, related=[str(three.id), str(one.id), str(two.id)])
    assert [each["id"] for each in await service.related_of(db, post.id)] == [
        str(three.id),
        str(one.id),
        str(two.id),
    ]

    await service.unpublish(db, one.id, by=None)
    await db.commit()
    shown = await service.shown(db, post)
    assert [each["slug"] for each in shown["related"]] == [three.slug, two.slug]
    still = await db.scalar(
        select(func.count()).select_from(Related).where(Related.post_id == post.id)
    )
    assert still == 3  # dropped at the next save, not before

    await _save(db, post, summary="A save")
    kept = await db.scalars(
        select(Related.related_id).where(Related.post_id == post.id).order_by(Related.position)
    )
    assert list(kept) == [three.id, two.id]


async def test_a_deleted_post_leaves_the_lists_it_was_in(db: AsyncSession) -> None:
    related = await _live(db)
    post = await _live(db, related=[str(related.id)])
    await service.remove(db, related.id, by=None)
    await db.commit()
    assert await service.related_of(db, post.id) == []


# --- what the site shows -------------------------------------------------------------------


async def test_a_list_is_newest_first_a_page_at_a_time_of_one_category(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    term = await _category(db)
    start = clock.now()
    made = []
    for number in range(service.PER_PAGE + 2):
        monkeypatch.setattr(clock, "now", lambda number=number: start + timedelta(minutes=number))
        made.append(await _live(db, category=term, title=f"Post {number}"))
    monkeypatch.undo()

    first = await service.page_of(db, category=term, cursor=None)
    assert [card["title"] for card in first["items"]] == [
        f"Post {number}" for number in range(13, 1, -1)
    ]
    assert first["next_cursor"] is not None
    second = await service.page_of(db, category=term, cursor=first["next_cursor"])
    assert [card["title"] for card in second["items"]] == ["Post 1", "Post 0"]
    assert second["next_cursor"] is None


async def test_a_cursor_that_isnt_one_is_refused(db: AsyncSession) -> None:
    with pytest.raises(Problem) as refused:
        await service.page_of(db, category=None, cursor="yesterday")
    assert refused.value.status == 422


async def test_a_live_post_reads_with_its_fallbacks(db: AsyncSession) -> None:
    words = " ".join(["word"] * 450)
    post = await _live(db, title="Long read", body=f"## Part\n\n{words}")
    shown = await service.shown(db, post)
    assert shown["reading_minutes"] == 3
    assert shown["html"].startswith("<h2>Part</h2>")
    assert shown["search_description"].startswith("Part word word")
    post = await _save(db, post, summary="One line.")
    assert service.description(post) == "One line."
    post = await _save(db, post, search_description="Its own.", search_title="Own title")
    assert (service.description(post), service.search_title(post, "Site")) == (
        "Its own.",
        "Own title",
    )


async def test_the_admin_list_finds_by_title_and_state(db: AsyncSession) -> None:
    mark = uuid.uuid4().hex[:8]
    draft = await _new(db, title=f"Draft {mark}")
    live = await _live(db, title=f"Live {mark}")
    found = await service.every(db, q=mark, status=None, cursor=None)
    assert {each["id"] for each in found["items"]} == {str(draft.id), str(live.id)}
    only = await service.every(db, q=mark, status="published", cursor=None)
    assert [each["id"] for each in only["items"]] == [str(live.id)]
    wild = await service.every(db, q="%", status=None, cursor=None)
    assert all("%" in each["title"] for each in wild["items"])


# --- search --------------------------------------------------------------------------------


async def _document(db: AsyncSession, post_id: uuid.UUID) -> SearchDocument | None:
    found: SearchDocument | None = await db.scalar(
        select(SearchDocument).where(
            SearchDocument.content_type == "blog.post", SearchDocument.content_id == post_id
        )
    )
    return found


async def test_a_live_save_is_searched_again_and_a_delete_leaves_search(db: AsyncSession) -> None:
    post = await _live(db)
    post = await _save(db, post, title="Searched title", summary="Under the bridge")
    found = await _document(db, post.id)
    assert found is not None
    assert found.title == "Searched title"
    assert "Under the bridge" in found.body
    assert found.path == f"/blog/{post.slug}"
    await service.remove(db, post.id, by=None)
    await db.commit()
    assert await _document(db, post.id) is None


# --- the announcement ----------------------------------------------------------------------


async def test_a_post_is_announced_once_with_its_choices(
    db: AsyncSession, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    said: list[Any] = []

    async def emit(session: AsyncSession, name: str, payload: Any) -> int:
        said.append((name, payload))
        return 1

    post = await _new(db, post_to_community=True)
    await service.publish(db, post.id, None, by=None)
    await db.commit()
    monkeypatch.setattr(kernel_events, "emit", emit)
    ctx = SimpleNamespace(sessions=database.sessions)
    heard = kernel_events.Event(
        uuid.uuid4(),
        "kernel.content.published",
        1,
        clock.now(),
        {"type": "blog.post", "id": str(post.id)},
    )
    await events._announce(ctx, heard)  # type: ignore[arg-type]
    await events._announce(ctx, heard)  # type: ignore[arg-type]  # delivered twice
    other = kernel_events.Event(
        uuid.uuid4(),
        "kernel.content.published",
        1,
        clock.now(),
        {"type": "pages.page", "id": str(post.id)},
    )
    await events._announce(ctx, other)  # type: ignore[arg-type]

    assert [name for name, _ in said] == ["blog.post.published"]
    payload = said[0][1]
    assert (payload.post_id, payload.post_to_community, payload.email_subscribers) == (
        post.id,
        True,
        False,
    )
    assert payload.path == f"/blog/{post.slug}"
    post_id = post.id
    db.expire_all()
    assert (await service.get(db, post_id)).announced_at is not None


async def test_the_announcement_carries_the_summary_as_version_2(
    db: AsyncSession, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """blog 0.1.3: campaigns' email holds the summary (SPEC 11, a new payload version)."""
    said: list[Any] = []

    async def emit(session: AsyncSession, name: str, payload: Any) -> int:
        said.append(payload)
        return 1

    post = await _live(db, summary="Ten years of shows, in one night.", email_subscribers=True)
    monkeypatch.setattr(kernel_events, "emit", emit)
    heard = kernel_events.Event(
        uuid.uuid4(),
        "kernel.content.published",
        1,
        clock.now(),
        {"type": "blog.post", "id": str(post.id)},
    )
    await events._announce(SimpleNamespace(sessions=database.sessions), heard)  # type: ignore[arg-type]

    assert kernel_events.declaration(events.PostPublished) == ("blog.post.published", 2)
    assert [(each.summary, each.email_subscribers) for each in said] == [
        ("Ten years of shows, in one night.", True)
    ]


# --- the hooks -----------------------------------------------------------------------------


async def test_export_lists_a_persons_posts_and_erase_keeps_them_as_the_sites(
    db: AsyncSession,
) -> None:
    writer = await make_person(db, "Ana", role="editor")
    post = await _new(db, by=writer, title="Mine")
    subject = privacy.Subject(user_id=writer, email="ana@example.test")
    exported = await blog_privacy.export_user_data(db, subject)
    assert [(each["id"], each["title"]) for each in exported["posts"]] == [(str(post.id), "Mine")]
    post_id = post.id
    await blog_privacy.delete_user_data(db, subject)
    await db.commit()
    db.expire_all()
    assert (await service.get(db, post_id)).author_id is None


async def test_a_scheduled_post_with_no_cover_needs_one(db: AsyncSession) -> None:
    post = await _new(db, title="Soon")
    await service.publish(db, post.id, (clock.now() + timedelta(seconds=30)).isoformat(), by=None)
    await db.commit()
    (item,) = await dashboard.ATTENTION(db, None)
    assert (item.key, item.to, item.permission) == (
        "blog.no_cover",
        f"/admin/blog/{post.id}",
        "blog.post.write",
    )
    assert "Soon" in item.why
    listed = await service.every(db, q=None, status=None, cursor=None)
    assert listed["needs_cover"]["id"] == str(post.id)

    await _save(db, await service.get(db, post.id), cover_id=str(await make_image(db)))
    left = await dashboard.ATTENTION(db, None)
    assert all(each.to != f"/admin/blog/{post.id}" for each in left)


async def test_the_seed_gives_three_categories_and_posts_in_each_state_once(
    db: AsyncSession,
) -> None:
    blog = load_module(MODULE / "module.json")
    allowed = {"MECHFRAME_ALLOW_SEED": "1"}
    ids = [uuid.uuid5(_NAMESPACE, each[0]) for each in POSTS]

    await seeding.run(db, [blog], environ=allowed)
    first = {
        row.id: (row.slug, row.status, row.version)
        for row in await db.scalars(select(Post).where(Post.id.in_(ids)))
    }
    await seeding.run(db, [blog], environ=allowed)
    db.expire_all()
    again = {
        row.id: (row.slug, row.status, row.version)
        for row in await db.scalars(select(Post).where(Post.id.in_(ids)))
    }

    assert again == first
    states = sorted(status for _, status, _ in first.values())
    assert states == ["draft", "published", "published", "published", "scheduled"]
    labels = {each["slug"]: each["label"] for each in await service.terms(db)}
    assert {labels["news"], labels["poetry"], labels["rap-battles"]} == {
        "News",
        "Poetry",
        "Rap battles",
    }


# --- the server copy -----------------------------------------------------------------------


async def test_the_server_copy_answers_a_live_post_a_move_and_a_real_404(db: AsyncSession) -> None:
    assert PAGES is not None
    image = await make_image(db)
    post = await _live(db, title="Copy", body="Hello **there**.", cover_id=str(image))
    page = await PAGES.page(db, f"/blog/{post.slug}", {"slug": post.slug})
    assert isinstance(page, server_copy.Page)
    assert "<h1>Copy</h1>" in page.words
    assert "<strong>there</strong>" in page.words
    assert page.kind == "article"
    assert page.image is not None
    assert str(image) in page.image
    (posting,) = page.data
    assert posting["@type"] == "BlogPosting"
    assert posting["headline"] == "Copy"

    old = post.slug
    post = await _save(db, post, slug=slug())
    moved = await PAGES.page(db, f"/blog/{old}", {"slug": old})
    assert moved == server_copy.Moved(f"/blog/{post.slug}")

    draft = await _new(db)
    assert await PAGES.page(db, f"/blog/{draft.slug}", {"slug": draft.slug}) is None

    blog = await PAGES.page(db, "/blog", {})
    assert isinstance(blog, server_copy.Page)
    assert "<h1>Blog</h1>" in blog.words
    entries = {entry.path for entry in await PAGES.sitemap(db)}
    assert {"/blog", f"/blog/{post.slug}"} <= entries
    assert f"/blog/{draft.slug}" not in entries


async def test_publishing_and_scheduling_go_through_the_lifecycle(db: AsyncSession) -> None:
    post_id = (await _new(db)).id
    with pytest.raises(Problem) as refused:
        await service.publish(db, post_id, "tomorrow", by=None)
    await db.rollback()
    assert refused.value.status == 422
    at = clock.now() + timedelta(days=2)
    scheduled = await service.publish(db, post_id, at.isoformat(), by=None)
    await db.commit()
    assert (scheduled.status, scheduled.publish_at) == (lifecycle.SCHEDULED, at)
    back = await service.unpublish(db, post_id, by=None)
    await db.commit()
    assert (back.status, back.publish_at) == (lifecycle.DRAFT, None)


# --- the review on #123 ----------------------------------------------------------------------


async def test_every_page_of_categories_is_read(db: AsyncSession) -> None:
    """CodeRabbit on #123: more categories than one page of the kernel's terms."""
    await _category(db)  # the vocabulary's row
    vocabulary = await db.scalar(
        text("SELECT id FROM kernel_vocabulary WHERE key = 'blog_category'")
    )
    mark = uuid.uuid4().hex[:8]
    await db.execute(
        text(
            "INSERT INTO kernel_term (id, vocabulary_id, slug, label, position) "
            "SELECT gen_random_uuid(), :vocabulary, 'zz-' || :mark || '-' || n, 'Many ' || n, 100000 "
            "FROM generate_series(1, :count) AS n"
        ),
        {"vocabulary": vocabulary, "mark": mark, "count": service.MAX_CATEGORIES + 1},
    )
    await db.commit()
    last = f"zz-{mark}-99"  # the last by slug, so on the second page
    slugs = {term["slug"] for term in await service.terms(db)}
    assert last in slugs
    post = await _new(db, category=last)
    assert (await service.categories_of(db, [post.id]))[post.id] == {
        "slug": last,
        "label": "Many 99",
    }


async def test_a_category_deleted_as_a_post_is_saved_isnt_made_again(
    db: AsyncSession, database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CodeRabbit on #123: staff delete it between the check and the tagging."""
    term = await _category(db)
    real = taxonomy.tag

    async def deleted_first(*args: Any, **kwargs: Any) -> Any:
        async with database.sessions() as other:
            await other.execute(text("DELETE FROM kernel_term WHERE slug = :slug"), {"slug": term})
            await other.commit()
        return await real(*args, **kwargs)

    monkeypatch.setattr(taxonomy, "tag", deleted_first)
    with pytest.raises(Problem) as refused:
        await service.create(db, {"title": "X", "category": term}, by=None)
    await db.rollback()
    assert (refused.value.code, refused.value.status) == ("blog.category_not_found", 422)
    again = await db.scalar(
        text("SELECT count(*) FROM kernel_term WHERE slug = :slug"), {"slug": term}
    )
    assert again == 0


async def test_the_announcement_choices_are_fixed_once_a_post_has_gone_live(
    db: AsyncSession,
) -> None:
    """CodeRabbit on #123: they're sent as they stood when it first went live."""
    post = await _live(db, post_to_community=True)
    post_id, version = post.id, post.version
    for name in ("post_to_community", "email_subscribers"):
        with pytest.raises(Problem) as refused:
            await service.change(db, post_id, version, {name: name == "email_subscribers"}, by=None)
        await db.rollback()
        assert (refused.value.code, refused.value.status) == ("blog.announced", 422)
    same = await _save(
        db, await service.get(db, post_id), post_to_community=True, allow_comments=False
    )
    assert (same.post_to_community, same.allow_comments) == (True, False)
    draft = await _new(db)
    changed = await _save(db, draft, email_subscribers=True)
    assert changed.email_subscribers is True
