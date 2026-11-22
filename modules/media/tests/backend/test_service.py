"""The media library's service, public API and hooks, on the migrated test
database with the public bucket in memory (`dev plans/contracts/media.md`)."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from media import dashboard, public, service
from media import privacy as media_privacy
from media.models import MediaImage
from media.seed import _NAMESPACE, IMAGES
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Problem, load_module, privacy
from kernel import seed as seeding

from ..conftest import Bucket, make_person, unique_image

MODULE = Path(__file__).resolve().parents[2]


async def _settled() -> None:
    """Lets the files a commit gives up be deleted (`service.after_commit`)."""
    for _ in range(5):
        await asyncio.sleep(0)


async def _call(read: object, image: MediaImage) -> None:
    read(image)  # type: ignore[operator]


async def _problem(coroutine: object) -> Problem:
    with pytest.raises(Problem) as raised:
        await coroutine  # type: ignore[misc]
    return raised.value


# --- upload ----------------------------------------------------------------------------


async def test_an_upload_stores_the_file_and_each_smaller_copy(
    db: AsyncSession, bucket: Bucket
) -> None:
    person = await make_person(db, "Pat Uploader")
    image, made = await service.upload(
        db, unique_image(size=(1000, 600)), filename="C:\\photos\\Day\n1.png", by=person
    )
    await db.commit()

    assert made
    assert bucket.under(f"media/{image.id}/") == [
        f"media/{image.id}/1-480.png",
        f"media/{image.id}/1-960.png",
        f"media/{image.id}/1.png",
    ]
    assert (image.width, image.height, image.content_type) == (1000, 600, "image/png")
    assert image.filename == "Day1.png"
    assert image.byte_count == len(bucket.files[f"media/{image.id}/1.png"])
    shown = service.as_answer(image, await service.names(db, {person}))
    assert shown["uploaded_by"] == "Pat Uploader"
    assert shown["url"].endswith(f"/media/{image.id}/1.png")
    assert [each.rsplit(" ", 1)[1] for each in shown["srcset"].split(", ")] == [
        "480w",
        "960w",
        "1000w",
    ]
    assert shown["srcset"].split(", ")[-1].endswith(f"/media/{image.id}/1.png 1000w")


async def test_the_same_image_again_is_the_one_stored(db: AsyncSession, bucket: Bucket) -> None:
    data = unique_image()
    first, _ = await service.upload(db, data, filename="a.png", by=None)
    await db.commit()
    stored = dict(bucket.files)

    again, made = await service.upload(db, data, filename="b.png", by=None)

    assert not made
    assert again.id == first.id
    assert bucket.files == stored


async def test_a_refused_upload_stores_nothing(db: AsyncSession, bucket: Bucket) -> None:
    refused = await _problem(service.upload(db, b"<svg></svg>", filename="x.svg", by=None))

    assert (refused.code, refused.status) == ("media.not_an_image", 415)
    assert bucket.files == {}


async def test_a_file_name_any_character_may_be_in_is_taken(
    db: AsyncSession, bucket: Bucket
) -> None:
    """CodeRabbit on #116: the audit log refuses an @ in its details, so the name stays out of them."""
    image, made = await service.upload(db, unique_image(), filename="logo@2x.png", by=None)
    await db.commit()

    assert made
    assert image.filename == "logo@2x.png"


async def test_a_rolled_back_upload_or_replace_takes_its_new_files_back(
    db: AsyncSession, bucket: Bucket
) -> None:
    """CodeRabbit on #116: the files a transaction wrote go if it never commits."""
    image, _ = await service.upload(db, unique_image(), filename="a.png", by=None)
    image_id = image.id
    await db.rollback()
    await _settled()
    assert bucket.under(f"media/{image_id}/") == []

    kept, _ = await service.upload(db, unique_image(size=(600, 400)), filename="b.png", by=None)
    await db.commit()
    kept_id = kept.id
    await _settled()
    before = bucket.under(f"media/{kept_id}/")
    await service.replace(db, kept_id, unique_image(size=(600, 400)), filename="c.png", by=None)
    await db.rollback()
    await _settled()
    assert bucket.under(f"media/{kept_id}/") == before  # the old version's files stay


async def test_with_the_public_bucket_off_an_upload_is_503(
    db: AsyncSession, bucket: Bucket
) -> None:
    bucket.on = False

    refused = await _problem(service.upload(db, unique_image(), filename="x.png", by=None))

    assert (refused.code, refused.status) == ("media.storage_off", 503)
    assert not service.storage_on()


async def test_with_the_public_bucket_off_an_images_address_is_503_not_500(
    db: AsyncSession, bucket: Bucket
) -> None:
    image, _ = await service.upload(db, unique_image(), filename="a.png", by=None)
    await db.commit()
    bucket.on = False

    for read in (service.url, service.srcset):
        refused = await _problem(_call(read, image))
        assert (refused.code, refused.status) == ("media.storage_off", 503)


async def test_a_failed_insert_takes_its_files_back(
    db: AsyncSession, bucket: Bucket, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_: object) -> None:
        raise RuntimeError("the database went away")

    monkeypatch.setattr(db, "add", broken)

    with pytest.raises(RuntimeError):
        await service.upload(db, unique_image(), filename="x.png", by=None)

    assert bucket.files == {}
    await db.rollback()


# --- replace ---------------------------------------------------------------------------


async def test_a_replace_keeps_the_id_and_takes_the_old_files_after_the_commit(
    db: AsyncSession, bucket: Bucket
) -> None:
    image, _ = await service.upload(db, unique_image(size=(1000, 600)), filename="old.png", by=None)
    await db.commit()
    await public.use(db, image.id, owner="blog.post:1", label="A post", link="/admin/blog/1")
    await db.commit()

    replaced = await service.replace(
        db, image.id, unique_image("JPEG", (700, 500)), filename="new.jpg", by=None
    )
    await _settled()
    assert f"media/{image.id}/1.png" in bucket.files  # until the commit
    await db.commit()
    await _settled()

    assert (replaced.id, replaced.file_version, replaced.version) == (image.id, 2, 2)
    assert bucket.under(f"media/{image.id}/") == [
        f"media/{image.id}/2-480.jpg",
        f"media/{image.id}/2.jpg",
    ]
    assert [each.owner for each in await service.uses_of(db, image.id)] == ["blog.post:1"]


async def test_a_replace_with_the_same_image_changes_nothing(
    db: AsyncSession, bucket: Bucket
) -> None:
    data = unique_image()
    image, _ = await service.upload(db, data, filename="a.png", by=None)
    await db.commit()

    same = await service.replace(db, image.id, data, filename="b.png", by=None)

    assert (same.file_version, same.version, same.filename) == (1, 1, "a.png")


async def test_a_replace_with_another_library_image_is_refused(
    db: AsyncSession, bucket: Bucket
) -> None:
    other_data = unique_image()
    other, _ = await service.upload(db, other_data, filename="other.png", by=None)
    image, _ = await service.upload(db, unique_image(), filename="this.png", by=None)
    await db.commit()

    refused = await _problem(service.replace(db, image.id, other_data, filename="x.png", by=None))

    assert (refused.code, refused.status) == ("media.already_in_library", 409)
    assert refused.extra == {"id": str(other.id)}
    await db.rollback()


# --- what it means ---------------------------------------------------------------------


async def test_alt_text_is_one_line_and_each_change_takes_the_version(
    db: AsyncSession, bucket: Bucket
) -> None:
    image, _ = await service.upload(db, unique_image(), filename="a.png", by=None)
    await db.commit()
    image_id = image.id  # read now: a rollback below expires the row

    changed = await service.change(
        db, image_id, version=1, alt="  A red door  ", decorative=False, by=None
    )
    await db.commit()
    assert (changed.alt, changed.version, changed.file_version) == ("A red door", 2, 1)

    stale = await _problem(
        service.change(db, image_id, version=1, alt="Other", decorative=False, by=None)
    )
    assert (stale.code, stale.status) == ("media.changed", 409)
    assert stale.extra == {"version": 2, "alt": "A red door", "decorative": False}
    await db.rollback()

    for said in ("Two\nlines", "A " + chr(0x2028) + " break", "Tab\tin"):
        refused = await _problem(
            service.change(db, image_id, version=2, alt=said, decorative=False, by=None)
        )
        assert (refused.code, refused.status) == ("kernel.invalid_request", 422)
        await db.rollback()

    refused = await _problem(
        service.change(db, image_id, version=2, alt="Says", decorative=True, by=None)
    )
    assert refused.errors is not None
    assert "alt" in refused.errors
    await db.rollback()

    decor = await service.change(db, image_id, version=2, alt="", decorative=True, by=None)
    await db.commit()
    assert (decor.alt, decor.decorative) == (None, True)
    assert (await public.picture(db, image_id)) == public.Picture(
        id=image_id,
        url=service.url(decor),
        srcset=service.srcset(decor),
        width=decor.width,
        height=decor.height,
        alt="",
        decorative=True,
    )


# --- uses and delete -------------------------------------------------------------------


async def test_an_image_in_use_waits_to_be_deleted(db: AsyncSession, bucket: Bucket) -> None:
    image, _ = await service.upload(db, unique_image(), filename="a.png", by=None)
    await db.commit()
    image_id = image.id  # read now: a rollback below expires the row
    owner = f"blog.post:{uuid.uuid4()}"
    await public.use(db, image_id, owner=owner, label="Draft", link="/admin/blog/1")
    await public.use(db, image_id, owner=owner, label="Published", link="/blog/hello")
    await db.commit()

    held = await _problem(service.delete(db, image_id, by=None))
    assert (held.code, held.status) == ("media.in_use", 409)
    assert held.extra == {"uses": [{"label": "Published", "link": "/blog/hello"}]}
    await db.rollback()

    await public.release(db, owner=owner, keep=[image_id])
    await db.commit()
    assert len(await service.uses_of(db, image_id)) == 1
    await public.release(db, owner=owner)
    await db.commit()

    files = bucket.under(f"media/{image_id}/")
    await service.delete(db, image_id, by=None)
    await _settled()
    assert bucket.under(f"media/{image_id}/") == files  # until the commit
    await db.commit()
    await _settled()
    assert bucket.under(f"media/{image_id}/") == []
    assert await db.scalar(select(MediaImage).where(MediaImage.id == image_id)) is None


async def test_a_use_needs_an_owner_key(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="owner"):
        await public.use(db, uuid.uuid4(), owner="no-colon", label="x", link="/x")


async def test_pictures_reads_only_the_images_the_library_has(
    db: AsyncSession, bucket: Bucket
) -> None:
    image, _ = await service.upload(db, unique_image(), filename="a.png", by=None)
    await db.commit()

    found = await public.pictures(db, [image.id, uuid.uuid4()])

    assert list(found) == [image.id]
    assert await public.pictures(db, []) == {}
    assert await public.picture(db, uuid.uuid4()) is None


# --- the list --------------------------------------------------------------------------


async def test_the_list_is_newest_first_in_pages_found_by_name_or_alt(
    db: AsyncSession, bucket: Bucket, monkeypatch: pytest.MonkeyPatch
) -> None:
    tag = uuid.uuid4().hex[:10]
    made = []
    for number in range(3):
        image, _ = await service.upload(db, unique_image(), filename=f"{tag}-{number}.png", by=None)
        await db.commit()
        made.append(image.id)
    monkeypatch.setattr(service, "PAGE", 2)

    first, cursor = await service.page(db, cursor=None, q=tag, only_missing_alt=False)
    assert [each.id for each in first] == [made[2], made[1]]
    assert cursor is not None
    rest, last = await service.page(db, cursor=cursor, q=tag, only_missing_alt=False)
    assert ([each.id for each in rest], last) == ([made[0]], None)

    await service.change(db, made[1], version=1, alt=f"Described {tag}", decorative=False, by=None)
    await db.commit()
    missing, _ = await service.page(db, cursor=None, q=tag, only_missing_alt=True)
    assert [each.id for each in missing] == [made[2], made[0]]
    assert await service.count_missing_alt(db) >= 2

    wild, _ = await service.page(db, cursor=None, q=f"{tag}%_", only_missing_alt=False)
    assert wild == []

    refused = await _problem(service.page(db, cursor="nonsense", q=None, only_missing_alt=False))
    assert (refused.code, refused.status) == ("kernel.invalid_request", 422)

    huge = "99999999999999999999." + "0" * 31 + "1"
    refused = await _problem(service.page(db, cursor=huge, q=None, only_missing_alt=False))
    assert (refused.code, refused.status) == ("kernel.invalid_request", 422)


def test_a_cursor_keeps_the_exact_microsecond_long_after_2038() -> None:
    """CodeRabbit on #116: through a float, 2100's microseconds can come back one short."""
    from datetime import UTC, datetime

    at = datetime(2100, 6, 1, 12, 0, 0, 999_999, tzinfo=UTC)
    row = MediaImage(id=uuid.UUID(int=5), created_at=at)

    assert service._moment(service._cursor_of(row)) == at


# --- hooks -----------------------------------------------------------------------------


async def test_export_lists_a_persons_uploads_and_erase_forgets_who_uploaded(
    db: AsyncSession, bucket: Bucket
) -> None:
    person = await make_person(db)
    image, _ = await service.upload(db, unique_image(), filename="mine.png", by=person)
    await db.commit()
    subject = privacy.Subject(user_id=person, email="x@example.test")

    exported = await media_privacy.export_user_data(db, subject)
    assert [each["id"] for each in exported["images"]] == [str(image.id)]
    assert exported["images"][0]["filename"] == "mine.png"

    await media_privacy.delete_user_data(db, subject)
    await db.commit()
    await db.refresh(image)
    assert image.uploaded_by is None
    assert (await media_privacy.export_user_data(db, subject)) == {"images": []}


async def test_an_export_lists_the_uploads_while_the_public_bucket_is_off(
    db: AsyncSession, bucket: Bucket
) -> None:
    """CodeRabbit on #116: a missing public address mustn't stop the account's copy."""
    person = await make_person(db)
    image, _ = await service.upload(db, unique_image(), filename="mine.png", by=person)
    await db.commit()
    bucket.on = False

    exported = await media_privacy.export_user_data(
        db, privacy.Subject(user_id=person, email="x@example.test")
    )

    assert exported["images"] == [
        {
            "id": str(image.id),
            "url": None,
            "filename": "mine.png",
            "alt": None,
            "uploaded_at": image.created_at.isoformat(),
        }
    ]


async def test_the_dashboard_asks_for_alt_text_and_the_public_bucket(
    db: AsyncSession, bucket: Bucket, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def none(_: AsyncSession) -> int:
        return 0

    async def one(_: AsyncSession) -> int:
        return 1

    monkeypatch.setattr(service, "count_missing_alt", one)
    (item,) = await dashboard.ATTENTION(db, None)
    assert (item.key, item.permission, item.what) == (
        "media.missing_alt",
        "media.image.manage",
        "1 image has no alt text",
    )
    monkeypatch.setattr(service, "count_missing_alt", none)
    assert await dashboard.ATTENTION(db, None) == []

    (step,) = dashboard.SETUP
    assert step.link == "/admin/settings/system"  # the System page (Codex on #116)
    assert await step.done(db)
    bucket.on = False
    assert not await step.done(db)


async def test_the_seed_gives_three_described_images_once(db: AsyncSession, bucket: Bucket) -> None:
    media = load_module(MODULE / "module.json")
    allowed = {"MECHFRAME_ALLOW_SEED": "1"}

    await seeding.run(db, [media], environ=allowed)
    stored = dict(bucket.files)
    await seeding.run(db, [media], environ=allowed)

    ids = [uuid.uuid5(_NAMESPACE, name) for name, *_ in IMAGES]
    rows = list(await db.scalars(select(MediaImage).where(MediaImage.id.in_(ids))))
    assert sorted(row.filename for row in rows) == sorted(name for name, *_ in IMAGES)
    assert all(row.alt for row in rows)
    assert bucket.files == stored  # the second run stored nothing new
