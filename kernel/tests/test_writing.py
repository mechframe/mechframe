"""The site's writing rules and styles (decision 0058; `dev plans/contracts/kernel-ai.md` §7)."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import writing
from kernel.auth.models import User
from kernel.errors import Problem
from kernel.models import AuditEvent, WritingStyle

SITE = "Test Site"


def test_the_block_as_a_site_ships_it_has_every_rule_and_no_brief() -> None:
    block = writing.block(writing.Constitution(), SITE)
    assert block.startswith(writing.mechanics(SITE))
    assert "You write for Test Site." in block
    for rule in writing.DEFAULT_RULES:
        assert f"- {rule.text}" in block
    assert "<brief>" not in block
    # Every phrase readers take for machine writing is named while its rule is on.
    assert '"delve"' in block
    assert '"myriad, plethora"' in block


def test_a_rule_switched_off_is_left_out_and_added_rules_follow() -> None:
    saved = writing.Constitution(rules_off=["em_dash"], added_rules="  Say we.\n\n Keep it short. ")
    block = writing.block(saved, SITE)
    em_dash = next(rule for rule in writing.DEFAULT_RULES if rule.id == "em_dash")
    assert em_dash.text not in block
    plain = next(rule for rule in writing.DEFAULT_RULES if rule.id == "plain_words")
    assert block.index(plain.text) < block.index("- Say we.") < block.index("- Keep it short.")
    assert block.index("- Keep it short.") < block.index("</rules>")


def test_own_text_replaces_the_rules_and_the_brief_keeps_its_boxes_in_order() -> None:
    saved = writing.Constitution(
        mode="own", own_text="Write in the first person.", voice="Warm.", about="A record label."
    )
    block = writing.block(saved, SITE)
    assert "<rules>\nWrite in the first person.\n</rules>" in block
    assert not any(rule.text in block for rule in writing.DEFAULT_RULES)
    assert block.index("<about_the_site>\nA record label.") < block.index("<voice>\nWarm.")
    assert "<audience>" not in block  # a blank box is left out


def test_own_mode_with_no_text_sends_no_rules() -> None:
    block = writing.block(writing.Constitution(mode="own"), SITE)
    assert "<rules>" not in block


def test_rules_off_keep_the_catalogues_order_once_each() -> None:
    saved = writing.Constitution(rules_off=["em_dash", "verified_only", "em_dash"])
    assert saved.rules_off == ["verified_only", "em_dash"]


@pytest.mark.parametrize(
    "fields",
    [
        {"rules_off": ["made_up"]},
        {"mode": "mine"},
        {"about": "x" * (writing.BOX_MAX + 1)},
        {"own_text": "x" * (writing.OWN_TEXT_MAX + 1)},
        {"surprise": "an unknown field"},
    ],
)
def test_the_section_refuses_what_it_cant_hold(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        writing.Constitution.model_validate(fields)


def test_a_site_with_no_name_is_still_written_for() -> None:
    assert "You write for this site." in writing.mechanics("  ")


def test_phrases_are_kept_once_each_in_any_case() -> None:
    assert writing.phrases(" delve \n\nDelve\nunleash\n") == ["delve", "unleash"]


def test_drafted_rules_and_phrases_are_cut_to_fit() -> None:
    assert len(writing.rules_that_fit("x" * 7000)) == writing.VOICE_RULES_MAX
    long = "y" * (writing.AVOID_PHRASE_MAX + 1)
    many = [f"phrase {n}" for n in range(writing.AVOID_PHRASES_MAX + 5)]
    kept = writing.phrases_that_fit([long, "Delve", "delve", *many]).splitlines()
    assert long not in kept
    assert kept[0] == "Delve"
    assert len(kept) == writing.AVOID_PHRASES_MAX


# --- styles, in Postgres ---------------------------------------------------------------


async def _person(db: AsyncSession) -> User:
    user_id = uuid.uuid4()
    address = f"{user_id.hex[:12]}@site.test"
    user = User(id=user_id, email=address, email_normal=address, session_epoch=0, role_version=0)
    db.add(user)
    await db.commit()
    return user


def _name(stem: str = "Warm") -> str:
    return f"{stem} {uuid.uuid4().hex[:8]}"


@pytest.mark.db
async def test_a_style_is_kept_normalised_and_audited(db: AsyncSession) -> None:
    person = await _person(db)
    name = _name()
    row = await writing.create(
        db,
        writing.StyleFields(
            name=f"  {name}  ",
            description=" Friendly. ",
            voice_rules=" - Short sentences. ",
            avoid="delve\n\nDELVE\n unleash ",
            samples=["  We make music.  ", "   ", "Come and hear it."],
        ),
        actor=person.id,
    )
    await db.commit()
    assert (row.name, row.description, row.voice_rules) == (name, "Friendly.", "- Short sentences.")
    assert row.avoid == "delve\nunleash"
    assert row.samples == ["We make music.", "Come and hear it."]
    assert row.version == 1
    assert row.created_by_id == person.id
    style = writing.style_of(row)
    assert style.avoid == ("delve", "unleash")
    entry = (
        await db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "kernel.writing_style.created",
                AuditEvent.target_id == str(row.id),
            )
        )
    ).one()
    assert entry.actor_id == person.id


@pytest.mark.db
async def test_a_name_is_taken_in_any_case(db: AsyncSession) -> None:
    person = await _person(db)
    name = _name()
    await writing.create(db, writing.StyleFields(name=name), actor=person.id)
    await db.commit()
    with pytest.raises(Problem) as refused:
        await writing.create(db, writing.StyleFields(name=name.upper()), actor=person.id)
    assert refused.value.code == "kernel.writing_style_name_taken"
    await db.rollback()


@pytest.mark.db
@pytest.mark.parametrize(
    "fields",
    [
        writing.StyleFields(name="   "),
        writing.StyleFields(name="house STYLE"),
        writing.StyleFields(name="x" * (writing.NAME_MAX + 1)),
        writing.StyleFields(name="Fine", samples=["a", "b", "c", "d"]),
        writing.StyleFields(name="Fine", samples=["x" * (writing.SAMPLE_MAX + 1)]),
        writing.StyleFields(name="Fine", avoid="y" * (writing.AVOID_PHRASE_MAX + 1)),
    ],
)
async def test_a_style_refuses_what_it_cant_hold(
    db: AsyncSession, fields: writing.StyleFields
) -> None:
    person = await _person(db)
    with pytest.raises(Problem) as refused:
        await writing.create(db, fields, actor=person.id)
    assert refused.value.code == "kernel.invalid_request"


@pytest.mark.db
async def test_a_change_from_an_older_version_is_refused(db: AsyncSession) -> None:
    person = await _person(db)
    row = await writing.create(db, writing.StyleFields(name=_name()), actor=person.id)
    await db.commit()
    changed = await writing.change(
        db, row.id, writing.StyleFields(voice_rules="- Plain."), version=1, actor=person.id
    )
    await db.commit()
    assert changed.version == 2
    # The same change again changes nothing and keeps the version.
    again = await writing.change(
        db, row.id, writing.StyleFields(voice_rules="- Plain."), version=2, actor=person.id
    )
    assert again.version == 2
    with pytest.raises(Problem) as refused:
        await writing.change(
            db, row.id, writing.StyleFields(description="Old"), version=1, actor=person.id
        )
    assert refused.value.code == "kernel.writing_style_changed"
    await db.rollback()


@pytest.mark.db
async def test_renaming_onto_another_styles_name_is_refused(db: AsyncSession) -> None:
    person = await _person(db)
    taken = _name("Taken")
    await writing.create(db, writing.StyleFields(name=taken), actor=person.id)
    row = await writing.create(db, writing.StyleFields(name=_name()), actor=person.id)
    await db.commit()
    with pytest.raises(Problem) as refused:
        await writing.change(
            db, row.id, writing.StyleFields(name=taken.lower()), version=1, actor=person.id
        )
    assert refused.value.code == "kernel.writing_style_name_taken"
    await db.rollback()


@pytest.mark.db
async def test_a_deleted_account_leaves_the_style(db: AsyncSession) -> None:
    person = await _person(db)
    row = await writing.create(db, writing.StyleFields(name=_name()), actor=person.id)
    await db.commit()
    await db.delete(await db.get(User, person.id))
    await db.commit()
    kept = await writing.find(db, row.id)
    assert kept is not None
    assert kept.created_by_id is None
    assert kept.updated_by_id is None


@pytest.mark.db
async def test_a_style_deleted_is_gone_for_a_task(db: AsyncSession) -> None:
    person = await _person(db)
    row = await writing.create(db, writing.StyleFields(name=_name()), actor=person.id)
    await db.commit()
    assert (await writing.chosen(db, row.id)) == writing.style_of(row)
    assert await writing.chosen(db, None) is None
    await writing.remove(db, row.id, actor=person.id)
    await db.commit()
    assert await db.get(WritingStyle, row.id) is None
    with pytest.raises(Problem) as refused:
        await writing.chosen(db, row.id)
    assert refused.value.code == "kernel.writing_style_not_found"
    with pytest.raises(Problem):
        await writing.remove(db, row.id, actor=person.id)


@pytest.mark.db
async def test_a_site_keeps_at_most_its_number_of_styles(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    person = await _person(db)
    monkeypatch.setattr(writing, "STYLES_MAX", len(await writing.listed(db)) + 1)
    await writing.create(db, writing.StyleFields(name=_name()), actor=person.id)
    await db.commit()
    with pytest.raises(Problem) as full:
        await writing.create(db, writing.StyleFields(name=_name()), actor=person.id)
    assert (full.value.code, full.value.status) == ("kernel.writing_styles_full", 409)
    await db.rollback()


@pytest.mark.db
async def test_styles_are_listed_by_name_in_any_case(db: AsyncSession) -> None:
    person = await _person(db)
    stem = uuid.uuid4().hex[:6]
    for name in (f"zz {stem} b", f"ZZ {stem} a", f"zz {stem} C"):
        await writing.create(db, writing.StyleFields(name=name), actor=person.id)
    await db.commit()
    names = [row.name for row in await writing.listed(db) if stem in row.name]
    assert names == [f"ZZ {stem} a", f"zz {stem} b", f"zz {stem} C"]
