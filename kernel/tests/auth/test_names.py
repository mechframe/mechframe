"""The account's name (`kernel.auth.names`; decision 0061; contract
dev plans/contracts/account-name.md): how a name is cleaned, a person's own
change, and a change by staff, who must outrank the person (decision 0013).

The statuses each route answers are also in the contract suites
(`test_auth_contract.py`, `test_people_roles_contract.py`); these are the
rules behind them, read from the rows and the audit log."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import httpx
import pyotp
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import clock, crypto
from kernel.app import create_app
from kernel.auth.accounts import normal_email
from kernel.auth.models import AuditEvent, Role, RolePermission, Totp, User, UserRole
from kernel.auth.names import MAX_NAME, clean_name
from kernel.email import CapturingMailer

from ..conftest import SITE, Client, Draining, make_config

PASSWORD = "quiet orbit lantern 4471 marsh"
OWN = "/api/auth/account/name"
_SAME_ORIGIN = {"Origin": SITE, "Sec-Fetch-Site": "same-origin"}


def _staff(user_id: uuid.UUID) -> str:
    return f"/api/auth/admin/users/{user_id}/name"


# --- the rules -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "kept"),
    [
        ("  Big \n  Haas ", "Big Haas"),
        ("Big\tHaas", "Big Haas"),
        ("Big\u00a0\u2003Haas", "Big Haas"),
        (unicodedata.normalize("NFD", "Ren\u00e9e"), "Ren\u00e9e"),
        ("x" * MAX_NAME, "x" * MAX_NAME),
        (" " + "x" * MAX_NAME + " ", "x" * MAX_NAME),
        ("\u0645\u0631\u064a\u0645", "\u0645\u0631\u064a\u0645"),
        ("", None),
        ("   \n ", None),
    ],
)
def test_a_name_is_cleaned_before_it_is_kept(typed: str, kept: str | None) -> None:
    assert clean_name(typed) == kept


@pytest.mark.parametrize(
    "typed",
    [
        "x" * (MAX_NAME + 1),
        "Big\x00Haas",
        "Big\x1bHaas",
        "Big\x7fHaas",
        "Big \u202eHaas",
        "\u2066Big",
    ],
)
def test_a_long_name_or_one_holding_a_control_or_an_override_is_refused(typed: str) -> None:
    with pytest.raises(ValueError, match="up to 120 characters"):
        clean_name(typed)


# --- a site and its people -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clock() -> Iterator[None]:
    clock.reset()
    yield
    clock.reset()


@dataclass
class Site:
    app: FastAPI

    def db(self) -> AsyncSession:
        made: AsyncSession = self.app.state.database.sessions()
        return made

    def browser(self) -> httpx.AsyncClient:
        transport = Draining(app=self.app, raise_app_exceptions=False)
        return httpx.AsyncClient(transport=transport, base_url=SITE, headers=_SAME_ORIGIN)


@dataclass
class Person:
    id: uuid.UUID
    email: str
    totp_secret: str


@pytest_asyncio.fixture
async def site(migrated_url: str) -> AsyncIterator[Site]:
    app = create_app(config=make_config(database_url=migrated_url), mailer=CapturingMailer())
    async with Client(app):
        yield Site(app)


async def _person(site: Site, *role_ids: str, status: str = "active") -> Person:
    email = f"Na.{uuid.uuid4().hex[:10]}@Site.test"
    secret = pyotp.random_base32()
    async with site.db() as db:
        user = User(
            email=email,
            email_normal=normal_email(email),
            password_hash=await site.app.state.passwords.hash(PASSWORD),
            email_verified_at=clock.now(),
            status=status,
        )
        db.add(user)
        await db.flush()
        for role in role_ids or ("member",):
            db.add(UserRole(user_id=user.id, role_id=role))
        db.add(Totp(user_id=user.id, secret_sealed=crypto.seal(secret), confirmed_at=clock.now()))
        await db.commit()
        return Person(user.id, email, secret)


async def _role(site: Site, *permissions: str) -> str:
    role_id = f"r-{uuid.uuid4().hex[:10]}"
    async with site.db() as db:
        db.add(Role(id=role_id, name="Helper"))
        await db.flush()
        for key in permissions:
            db.add(RolePermission(role_id=role_id, permission=key))
        await db.commit()
    return role_id


async def _signed_in(site: Site, person: Person) -> httpx.AsyncClient:
    browser = site.browser()
    body = (
        await browser.post("/api/auth/sign-in", json={"email": person.email, "password": PASSWORD})
    ).json()
    body = (
        await browser.post(
            "/api/auth/sign-in/second-factor",
            json={"challenge": body["challenge"], "totp": pyotp.TOTP(person.totp_secret).now()},
        )
    ).json()
    assert body["status"] == "signed_in", body
    return browser


async def _name_of(site: Site, person: Person) -> str | None:
    async with site.db() as db:
        found: str | None = await db.scalar(select(User.display_name).where(User.id == person.id))
        return found


async def _renames(site: Site, person: Person) -> list[AuditEvent]:
    async with site.db() as db:
        found = await db.scalars(
            select(AuditEvent)
            .where(AuditEvent.action == "auth.name_changed", AuditEvent.subject_id == person.id)
            .order_by(AuditEvent.id)
        )
        return list(found)


# --- your own name ---------------------------------------------------------------------


async def test_your_name_changes_the_session_and_is_audited(site: Site) -> None:
    person = await _person(site)
    browser = await _signed_in(site, person)
    answer = await browser.put(OWN, json={"name": "  Big   Haas "})
    assert answer.status_code == 200, answer.text
    assert answer.json()["user"]["name"] == "Big Haas"
    assert answer.json()["user"]["email"] == person.email
    assert (await browser.get("/api/auth/session")).json()["user"]["name"] == "Big Haas"
    assert await _name_of(site, person) == "Big Haas"
    [row] = await _renames(site, person)
    assert (row.actor_id, row.subject_id, row.result) == (person.id, person.id, "success")
    assert row.details == {}  # the log keeps no name (decision 0061)


async def test_the_same_name_again_writes_nothing(site: Site) -> None:
    person = await _person(site)
    browser = await _signed_in(site, person)
    assert (await browser.put(OWN, json={"name": "Ana"})).status_code == 200
    again = await browser.put(OWN, json={"name": " Ana  "})
    assert (again.status_code, again.json()["user"]["name"]) == (200, "Ana")
    assert len(await _renames(site, person)) == 1


async def test_removing_your_name_is_recorded_as_cleared(site: Site) -> None:
    person = await _person(site)
    browser = await _signed_in(site, person)
    assert (await browser.put(OWN, json={"name": "Ana"})).status_code == 200
    cleared = await browser.put(OWN, json={"name": "   "})
    assert (cleared.status_code, cleared.json()["user"]["name"]) == (200, None)
    assert await _name_of(site, person) is None
    assert [row.details for row in await _renames(site, person)] == [{}, {"cleared": True}]
    # With none, removing it again changes nothing.
    assert (await browser.put(OWN, json={"name": ""})).status_code == 200
    assert len(await _renames(site, person)) == 2


@pytest.mark.parametrize("body", [{"name": "Big\x00Haas"}, {"name": "x" * 121}, {"name": None}, {}])
async def test_a_refused_name_changes_nothing(site: Site, body: dict[str, object]) -> None:
    person = await _person(site)
    browser = await _signed_in(site, person)
    refused = await browser.put(OWN, json=body)
    assert (refused.status_code, refused.json()["code"]) == (422, "kernel.invalid_request")
    assert await _name_of(site, person) is None
    assert await _renames(site, person) == []


async def test_your_name_needs_no_recent_sign_in(site: Site) -> None:
    person = await _person(site)
    browser = await _signed_in(site, person)
    clock.advance(11 * 60)
    assert (await browser.put(OWN, json={"name": "Ana"})).status_code == 200


async def test_signed_out_there_is_no_name_to_change(site: Site) -> None:
    refused = await site.browser().put(OWN, json={"name": "Ana"})
    assert (refused.status_code, refused.json()["code"]) == (401, "kernel.not_signed_in")


async def test_the_eleventh_change_in_an_hour_is_refused(site: Site) -> None:
    person = await _person(site)
    browser = await _signed_in(site, person)
    for each in range(10):
        assert (await browser.put(OWN, json={"name": f"Ana {each}"})).status_code == 200
    refused = await browser.put(OWN, json={"name": "Ana 10"})
    assert (refused.status_code, refused.json()["code"]) == (429, "kernel.rate_limited")
    assert await _name_of(site, person) == "Ana 9"
    # The budget is the account's: another person's is untouched.
    other = await _person(site)
    assert (await (await _signed_in(site, other)).put(OWN, json={"name": "Bo"})).status_code == 200


# --- a name changed by staff -----------------------------------------------------------


async def test_staff_rename_only_those_they_outrank(site: Site) -> None:
    owner, other_owner = await _person(site, "owner"), await _person(site, "owner")
    admin, member = await _person(site, "admin"), await _person(site)
    as_owner, as_admin = await _signed_in(site, owner), await _signed_in(site, admin)

    renamed = await as_admin.put(_staff(member.id), json={"name": " Ana  Example "})
    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["id"], renamed.json()["name"]) == (str(member.id), "Ana Example")
    [row] = await _renames(site, member)
    assert (row.actor_id, row.subject_id, row.details) == (admin.id, member.id, {})
    # The same name again, once cleaned, changes nothing and writes nothing.
    again = await as_admin.put(_staff(member.id), json={"name": "Ana Example"})
    assert (again.status_code, again.json()["name"]) == (200, "Ana Example")
    assert len(await _renames(site, member)) == 1

    refused = await as_admin.put(_staff(owner.id), json={"name": "Not you"})
    assert (refused.status_code, refused.json()["code"]) == (403, "auth.role_not_yours")
    assert await _name_of(site, owner) is None

    assert (await as_owner.put(_staff(other_owner.id), json={"name": "Co"})).status_code == 200
    assert (await as_owner.put(_staff(admin.id), json={"name": "Ad"})).status_code == 200
    # Anyone may rename themselves through People: they hold what they hold.
    assert (await as_admin.put(_staff(admin.id), json={"name": "Me"})).status_code == 200


async def test_a_role_short_of_one_of_the_persons_permissions_is_refused(site: Site) -> None:
    manager = await _role(site, "auth.user.manage")
    reader = await _role(site, "auth.user.manage", "auth.audit.read")
    helper, peer = await _person(site, manager), await _person(site, reader)
    member = await _person(site)
    as_helper = await _signed_in(site, helper)
    refused = await as_helper.put(_staff(peer.id), json={"name": "Peer"})
    assert (refused.status_code, refused.json()["code"]) == (403, "auth.role_not_yours")
    # `member` is no rank: a member's name is anyone's on People to change.
    assert (await as_helper.put(_staff(member.id), json={"name": "Mo"})).status_code == 200


async def test_staff_without_the_permission_are_forbidden(site: Site) -> None:
    editor, member = await _person(site, "editor"), await _person(site)
    refused = await (await _signed_in(site, editor)).put(_staff(member.id), json={"name": "Mo"})
    assert (refused.status_code, refused.json()["code"]) == (403, "kernel.forbidden")


async def test_a_rename_by_staff_needs_a_recent_sign_in(site: Site) -> None:
    admin, member = await _person(site, "admin"), await _person(site)
    browser = await _signed_in(site, admin)
    clock.advance(11 * 60)
    stale = await browser.put(_staff(member.id), json={"name": "Mo"})
    assert (stale.status_code, stale.json()["code"]) == (403, "auth.step_up_required")
    assert await _name_of(site, member) is None


async def test_a_suspended_person_can_be_renamed_so_staff_can_clear_a_name(site: Site) -> None:
    admin, member = await _person(site, "admin"), await _person(site, status="suspended")
    async with site.db() as db:
        row = await db.get(User, member.id)
        assert row is not None
        row.display_name = "Something rude"
        await db.commit()
    cleared = await (await _signed_in(site, admin)).put(_staff(member.id), json={"name": ""})
    assert (cleared.status_code, cleared.json()["name"]) == (200, None)
    [row] = await _renames(site, member)
    assert row.details == {"cleared": True}


async def test_a_deleted_person_is_not_found_and_a_departing_one_is_refused(site: Site) -> None:
    admin = await _person(site, "admin")
    gone, leaving = await _person(site, status="deleted"), await _person(site, status="deleting")
    browser = await _signed_in(site, admin)
    for missing in (gone.id, uuid.uuid4()):
        answer = await browser.put(_staff(missing), json={"name": "Mo"})
        assert (answer.status_code, answer.json()["code"]) == (404, "kernel.not_found")
    answer = await browser.put(_staff(leaving.id), json={"name": "Mo"})
    assert (answer.status_code, answer.json()["code"]) == (409, "auth.account_not_active")
    async with site.db() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "auth.name_changed",
                AuditEvent.subject_id.in_([gone.id, leaving.id]),
            )
        )
    assert count == 0
