"""Export and erase (decision 0052, hook 7; contract `dev plans/contracts/hooks.md`):
the start refusing `data_hooks` that disagree with `privacy.py`, `export`
asking every exporting module, `erase` running every deletion, the ZIP, and
the job's last try. The routes and a copy made end to end are the contract
suite's (`kernel/tests/contract/test_hook_privacy.py`)."""

from __future__ import annotations

import importlib.util
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from harness.probe import MODULES as PROBES
from kernel import clock, email, jobs, privacy
from kernel.auth import exports
from kernel.auth.models import User, UserRole
from kernel.db import Database
from kernel.models import AuditEvent, Job
from kernel.models import Export as ExportRow
from kernel.modules import InstalledModule, Manifest

from .conftest import AppFactory


def _module(
    module_id: str, *, hooks: dict[str, bool] | None = None, **parts: Any
) -> InstalledModule:
    manifest = Manifest.from_dict(
        {
            "id": module_id,
            "name": module_id.title(),
            "version": "0.1.0",
            "summary": "A module for the privacy tests",
            "category": "admin",
            **({"data_hooks": hooks} if hooks is not None else {}),
        }
    )
    return InstalledModule(manifest, **parts)


def _exports(name: str, rows: list[dict[str, Any]]) -> Any:
    async def export_user_data(db: Any, subject: privacy.Subject) -> privacy.Exported:
        return {name: [{**row, "for": str(subject.user_id)} for row in rows]}

    return export_user_data


def _deletes(log: list[str], module_id: str) -> Any:
    async def delete_user_data(db: Any, subject: privacy.Subject) -> None:
        log.append(module_id)

    return delete_user_data


SUBJECT = privacy.Subject(uuid.UUID("00000000-0000-4000-8000-000000000042"), "Person@Site.test")


@pytest.fixture(autouse=True)
def _restore() -> Any:
    yield
    privacy.install(privacy.build(PROBES))


# --- the start's checks ----------------------------------------------------------------------


def test_only_the_probe_takes_part() -> None:
    found = privacy.build(PROBES)
    assert list(found) == ["probe"]
    assert found["probe"].export is not None
    assert found["probe"].delete is not None


def test_a_module_that_holds_nothing_declares_nothing() -> None:
    assert privacy.build([_module("quiet"), _module("off", hooks={"export": False})]) == {}


def test_the_manifest_saying_export_without_the_function_is_refused() -> None:
    with pytest.raises(ValueError, match=r"photos's module.json says data_hooks.export"):
        privacy.build([_module("photos", hooks={"export": True})])


def test_the_function_without_the_manifest_saying_so_is_refused() -> None:
    module = _module(
        "photos",
        hooks={"export": True, "delete": False},
        export_user_data=_exports("photos", []),
        delete_user_data=_deletes([], "x"),
    )
    with pytest.raises(ValueError, match=r"photos.s privacy.py has delete_user_data, but"):
        privacy.build([module])


def test_a_function_that_isnt_async_is_refused() -> None:
    def export_user_data(db: Any, subject: Any) -> dict[str, Any]:
        return {}

    module = _module("photos", hooks={"export": True}, export_user_data=export_user_data)
    with pytest.raises(ValueError, match="async def export_user_data"):
        privacy.build([module])


def test_the_start_refuses_data_hooks_that_disagree(app_factory: AppFactory) -> None:
    with pytest.raises(RuntimeError, match=r"Refusing to start: .*data_hooks\.delete"):
        app_factory([_module(f"p{uuid.uuid4().hex[:8]}", hooks={"delete": True})])


def test_the_module_templates_privacy_py_agrees_with_its_module_json() -> None:
    folder = Path(__file__).resolve().parents[2] / "modules" / "_template"
    listed = Manifest.from_file(folder / "module.json")
    spec = importlib.util.spec_from_file_location(
        f"template_privacy_{uuid.uuid4().hex[:8]}", folder / "backend" / "my_module" / "privacy.py"
    )
    assert spec is not None
    assert spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    module = InstalledModule(
        listed,
        export_user_data=loaded.export_user_data,
        delete_user_data=loaded.delete_user_data,
    )
    assert list(privacy.build([module])) == [listed.id]


# --- export and erase --------------------------------------------------------------------------


async def test_export_asks_every_exporting_module_in_id_order() -> None:
    privacy.install(
        privacy.build(
            [
                _module(
                    "zines", hooks={"export": True}, export_user_data=_exports("zines", [{"n": 1}])
                ),
                _module(
                    "art", hooks={"export": True}, export_user_data=_exports("pieces", [{"n": 2}])
                ),
                _module("bare"),
            ]
        )
    )
    found = await privacy.export(None, SUBJECT)  # type: ignore[arg-type]
    assert list(found) == ["art", "zines"]
    assert found["art"] == {"pieces": [{"n": 2, "for": str(SUBJECT.user_id)}]}


@pytest.mark.parametrize("answer", [[{"n": 1}], {"notes": {"n": 1}}, {"notes": [1]}, {3: []}, None])
async def test_an_answer_that_isnt_lists_of_objects_by_name_is_refused(answer: Any) -> None:
    async def export_user_data(db: Any, subject: Any) -> Any:
        return answer

    privacy.install(
        privacy.build([_module("odd", hooks={"export": True}, export_user_data=export_user_data)])
    )
    with pytest.raises(ValueError, match="odd's export_user_data answers lists of objects"):
        await privacy.export(None, SUBJECT)  # type: ignore[arg-type]


async def test_erase_runs_every_deletion_in_id_order() -> None:
    log: list[str] = []
    privacy.install(
        privacy.build(
            [
                _module("zines", hooks={"delete": True}, delete_user_data=_deletes(log, "zines")),
                _module("art", hooks={"delete": True}, delete_user_data=_deletes(log, "art")),
                _module("only-export", hooks={"export": True}, export_user_data=_exports("x", [])),
            ]
        )
    )
    assert await privacy.erase(None, SUBJECT) == ["art", "zines"]  # type: ignore[arg-type]
    assert log == ["art", "zines"]


def test_the_zip_holds_one_json_file_each_in_order_dated_as_asked() -> None:
    at = datetime(2026, 11, 21, 15, 4, 6, tzinfo=UTC)  # a ZIP keeps even seconds
    data = privacy.archive(
        {"kernel": {"account": [{"id": SUBJECT.user_id, "at": at}]}, "probe": {"notes": []}}, at=at
    )
    found = zipfile.ZipFile(io.BytesIO(data))
    assert found.namelist() == ["kernel.json", "probe.json"]
    assert {entry.date_time for entry in found.infolist()} == {(2026, 11, 21, 15, 4, 6)}
    assert json.loads(found.read("kernel.json")) == {
        "account": [{"id": str(SUBJECT.user_id), "at": "2026-11-21T15:04:06+00:00"}]
    }


def test_a_value_json_cant_hold_is_refused() -> None:
    with pytest.raises(TypeError, match="set isn't JSON"):
        privacy.archive({"odd": {"rows": [{"tags": {1, 2}}]}}, at=datetime(2026, 1, 1, tzinfo=UTC))


# --- the job ---------------------------------------------------------------------------------


async def _account(db: AsyncSession) -> User:
    user_id = uuid.uuid4()
    address = f"{user_id.hex[:12]}@site.test"
    user = User(id=user_id, email=address, email_normal=address, session_epoch=0, role_version=0)
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user_id, role_id="member"))
    await db.commit()
    return user


async def _queued(db: AsyncSession, user: User, status: str = "queued") -> uuid.UUID:
    now = clock.now()
    row = ExportRow(user_id=user.id, status=status, created_at=now, expires_at=now + exports.KEEP)
    db.add(row)
    await db.commit()
    return row.id


def _context(database: Database, try_number: int) -> jobs.Context:
    return jobs.Context(uuid.uuid4(), exports.MAKE.name, try_number, database, email.LogMailer())


async def _status(db: AsyncSession, export_id: uuid.UUID) -> str | None:
    return await db.scalar(select(ExportRow.status).where(ExportRow.id == export_id))


async def _mails(db: AsyncSession) -> int:
    count = await db.scalar(
        select(func.count()).select_from(Job).where(Job.name == email.SEND_MAIL.name)
    )
    return int(count or 0)


@pytest.mark.db
async def test_the_last_try_marks_the_copy_failed_and_tells_its_owner(
    app_factory: AppFactory, database: Database, db: AsyncSession
) -> None:
    app_factory([])  # installs the mail templates the job renders
    user = await _account(db)
    user_id = user.id  # a rollback expires the row
    export_id = await _queued(db, user)
    before = await _mails(db)

    # Storage is off in the tests, so storing the ZIP fails: an early try
    # leaves the copy queued for the next.
    with pytest.raises(Exception, match="Storage is off"):
        await exports._make(_context(database, 1), {"export_id": str(export_id)})
    await db.rollback()
    assert await _status(db, export_id) == "queued"
    assert await _mails(db) == before

    with pytest.raises(Exception, match="Storage is off"):
        await exports._make(_context(database, exports.TRIES), {"export_id": str(export_id)})
    await db.rollback()
    assert await _status(db, export_id) == "failed"
    assert await _mails(db) == before + 1
    entry = await db.scalar(
        select(AuditEvent).where(
            AuditEvent.subject_id == user_id, AuditEvent.action == "auth.data_export_ready"
        )
    )
    assert entry is not None
    assert entry.result == "failed"


@pytest.mark.db
async def test_running_out_of_time_on_the_last_try_marks_the_copy_failed(
    app_factory: AppFactory, database: Database, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The export's own time limit runs out inside the job's: on the last try
    that's an ordinary failure, and its owner is told (CodeRabbit on #109)."""
    import asyncio

    app_factory([])
    user = await _account(db)
    export_id = await _queued(db, user)

    async def slow(db: Any, subject: Any) -> Any:
        await asyncio.sleep(5)

    monkeypatch.setattr(privacy, "export", slow)
    monkeypatch.setattr(exports, "WORK_SECONDS", 0.05)
    with pytest.raises(TimeoutError):
        await exports._make(_context(database, exports.TRIES), {"export_id": str(export_id)})
    await db.rollback()
    assert await _status(db, export_id) == "failed"
    assert exports.WORK_SECONDS < exports.JOB_SECONDS


@pytest.mark.db
async def test_a_shutdown_on_the_last_try_leaves_the_copy_to_its_lease(
    app_factory: AppFactory, database: Database, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worker's shutdown cancels the try: that's no failure, so the copy
    stays queued for the job's next run (CodeRabbit on #109)."""
    import asyncio

    app_factory([])
    user = await _account(db)
    export_id = await _queued(db, user)

    async def cancelled(db: Any, subject: Any) -> Any:
        raise asyncio.CancelledError

    monkeypatch.setattr(privacy, "export", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await exports._make(_context(database, exports.TRIES), {"export_id": str(export_id)})
    await db.rollback()
    assert await _status(db, export_id) == "queued"


@pytest.mark.db
async def test_a_copy_whose_job_was_lost_is_failed_a_day_on_and_its_owner_told(
    app_factory: AppFactory, database: Database, db: AsyncSession
) -> None:
    """A worker that dies on the last try leaves the job dead without running
    it again: the hourly prune fails a copy still queued a day on, and mails
    its owner; a newer one waits (CodeRabbit on #109)."""
    app_factory([])
    user = await _account(db)
    lost = ExportRow(
        user_id=user.id,
        status="queued",
        created_at=clock.now() - exports.STUCK - timedelta(minutes=1),
        expires_at=clock.now() + timedelta(days=5),
    )
    db.add(lost)
    await db.commit()
    lost_id = lost.id
    waiting = await _queued(db, user)
    before = await _mails(db)
    await exports._prune(_context(database, 1))
    await db.rollback()
    assert await _status(db, lost_id) == "failed"
    assert await _status(db, waiting) == "queued"
    assert await _mails(db) == before + 1


@pytest.mark.db
async def test_an_old_copy_whose_job_is_still_queued_or_running_waits_for_it(
    app_factory: AppFactory, database: Database, db: AsyncSession
) -> None:
    """A day-old copy whose job is only late, or at work, isn't failed: its
    job still ends it (CodeRabbit on #109)."""
    from sqlalchemy import update

    app_factory([])
    user = await _account(db)
    ids = []
    for state in ("queued", "running"):
        row = ExportRow(
            user_id=user.id,
            status="queued",
            created_at=clock.now() - exports.STUCK - timedelta(hours=2),
            expires_at=clock.now() + timedelta(days=5),
        )
        db.add(row)
        await db.flush()
        job_id = await jobs.enqueue(
            db, exports.MAKE.name, {"export_id": str(row.id)}, key=str(row.id)
        )
        await db.execute(update(Job).where(Job.id == job_id).values(state=state))
        ids.append(row.id)
    await db.commit()
    before = await _mails(db)
    await exports._prune(_context(database, 1))
    await db.rollback()
    assert [await _status(db, each) for each in ids] == ["queued", "queued"]
    assert await _mails(db) == before


@pytest.mark.db
async def test_a_try_finishing_after_its_copy_was_failed_mails_nothing(
    app_factory: AppFactory, database: Database, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The copy was failed while the try was at work: the try stores nothing
    more, marks nothing ready and mails nothing (CodeRabbit on #109)."""
    from sqlalchemy import update

    from kernel import storage

    app_factory([])
    user = await _account(db)
    export_id = await _queued(db, user)
    stored: list[str] = []
    deleted: list[str] = []

    async def put(key: str, data: bytes, **_: Any) -> None:
        stored.append(key)
        async with database.sessions() as other:  # the prune, failing it meanwhile
            await other.execute(
                update(ExportRow).where(ExportRow.id == export_id).values(status="failed")
            )
            await other.commit()

    async def remove(key: str, **_: Any) -> None:
        deleted.append(key)

    monkeypatch.setattr(storage, "put", put)
    monkeypatch.setattr(storage, "delete", remove)
    before = await _mails(db)
    await exports._make(_context(database, 1), {"export_id": str(export_id)})
    await db.rollback()
    assert await _status(db, export_id) == "failed"
    assert await _mails(db) == before
    assert deleted == stored == [exports.storage_key(export_id)]


@pytest.mark.db
async def test_a_deleted_accounts_copy_stays_tracked_for_the_prune(db: AsyncSession) -> None:
    """Its row stays, without an owner, so the prune still finds its file
    (CodeRabbit on #109)."""
    from sqlalchemy import delete as delete_rows

    user = await _account(db)
    user_id = user.id
    export_id = await _queued(db, user, status="ready")
    await db.execute(delete_rows(User).where(User.id == user_id))
    await db.commit()
    owner = await db.scalar(select(ExportRow.user_id).where(ExportRow.id == export_id))
    assert await _status(db, export_id) == "ready"
    assert owner is None


@pytest.mark.db
async def test_a_copy_already_made_or_gone_is_left_alone(
    app_factory: AppFactory, database: Database, db: AsyncSession
) -> None:
    app_factory([])
    user = await _account(db)
    made = await _queued(db, user, status="ready")
    await exports._make(_context(database, 1), {"export_id": str(made)})
    await exports._make(_context(database, 1), {"export_id": str(uuid.uuid4())})
    await db.rollback()
    assert await _status(db, made) == "ready"


@pytest.mark.db
async def test_the_kernels_own_file_holds_the_account_its_roles_and_its_activity(
    db: AsyncSession,
) -> None:
    user = await _account(db)
    own = await exports.own_data(db, user)
    assert list(own) == ["account", "roles", "activity"]
    (account,) = own["account"]
    assert account["id"] == user.id
    assert account["email"] == user.email
    assert own["roles"] == [{"name": "member"}]
    assert own["activity"] == []


@pytest.mark.db
async def test_the_prune_removes_a_copys_file_its_row_never_recorded(
    database: Database, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A try can store the ZIP and then fail to record it: the prune deletes
    the copy's own key all the same (Codex on #109)."""
    from moto import mock_aws

    from kernel import storage
    from kernel.config import reset_config

    from .test_storage import PRIVATE, STORAGE_ENV

    for name, value in STORAGE_ENV.items():
        monkeypatch.setenv(name, value)
    reset_config()
    storage._client.cache_clear()
    try:
        with mock_aws():
            client = storage._client(
                STORAGE_ENV["STORAGE_ENDPOINT_URL"],
                "auto",
                STORAGE_ENV["STORAGE_ACCESS_KEY_ID"],
                STORAGE_ENV["STORAGE_SECRET_ACCESS_KEY"],
            )
            client.create_bucket(
                Bucket=PRIVATE, CreateBucketConfiguration={"LocationConstraint": "auto"}
            )
            user = await _account(db)
            row = ExportRow(
                user_id=user.id,
                status="failed",
                created_at=clock.now() - exports.KEEP * 2,
                expires_at=clock.now() - exports.KEEP,
            )
            db.add(row)
            await db.commit()
            row_id = row.id
            await storage.put(exports.storage_key(row_id), b"PK", content_type="application/zip")

            # Storage switched off: the prune keeps the row that finds the file.
            monkeypatch.setenv("STORAGE_BUCKET", "")
            reset_config()
            await exports._prune(_context(database, 1))
            await db.rollback()
            assert await _status(db, row_id) == "failed"

            # Back on: the file and the row go.
            monkeypatch.setenv("STORAGE_BUCKET", STORAGE_ENV["STORAGE_BUCKET"])
            reset_config()
            storage._client.cache_clear()
            await exports._prune(_context(database, 1))
            assert await storage.get(exports.storage_key(row_id)) is None
            await db.rollback()
            assert await _status(db, row_id) is None
    finally:
        monkeypatch.undo()
        reset_config()
        storage._client.cache_clear()


@pytest.mark.db
async def test_while_storage_is_off_the_prune_removes_nothing(
    database: Database, db: AsyncSession
) -> None:
    user = await _account(db)
    kept = await _queued(db, user)
    gone = ExportRow(
        user_id=user.id,
        status="failed",
        created_at=clock.now() - exports.KEEP * 2,
        expires_at=clock.now() - exports.KEEP,
    )
    db.add(gone)
    await db.commit()
    gone_id = gone.id
    await exports._prune(_context(database, 1))
    await db.rollback()
    # Storage is off in these tests: nothing is deleted until it's back.
    assert await _status(db, gone_id) == "failed"
    assert await _status(db, kept) == "queued"
