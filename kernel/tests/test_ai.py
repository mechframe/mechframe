"""The AI's writing help (decision 0058; `dev plans/contracts/kernel-ai.md` §7):
the key's order, the request's shape and its failures, and each task's
answer, against the harness's fake Anthropic. No test calls Anthropic."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from harness.fake_anthropic import FakeAnthropic
from kernel import ai, crypto, writing
from kernel.errors import Problem
from kernel.models import Setting
from kernel.settings import settings

KEY = "sk-ant-test-" + "k" * 40
HOST_KEY = "sk-ant-host-" + "h" * 40
SITE = "Test Site"


@pytest.fixture
def fake() -> Iterator[FakeAnthropic]:
    found = FakeAnthropic()
    before = ai.use_transport(found.transport)
    yield found
    ai.use_transport(before)


def _writer(constitution: str = "The rules.") -> ai.Writer:
    return ai.Writer(KEY, constitution=constitution, site_name=SITE)


STYLE = writing.Style(
    name="Warm",
    description="Friendly",
    voice_rules="- Short sentences.",
    avoid=("delve",),
    samples=("We make music.",),
)


# --- the key ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "",
        "sk-ant-...",
        "has a space in it and is long enough",
        "x" * (ai.MAX_KEY_LENGTH + 1),
        "sk-abc",
    ],
)
def test_a_value_that_cant_be_a_key_has_a_problem_that_never_repeats_it(value: str) -> None:
    problem = ai.key_problem(value) if value else "blank"
    assert problem is not None
    assert value not in problem or not value


def test_a_key_shaped_value_has_no_problem() -> None:
    assert ai.key_problem(KEY) is None


@pytest.fixture
def section(monkeypatch: pytest.MonkeyPatch) -> str:
    """`kernel.ai` under a name of this test's own, so saved keys don't meet."""
    name = f"kernel.ai_{uuid.uuid4().hex[:8]}"
    settings.register(name, ai.KeySettings)
    monkeypatch.setattr(ai, "SECTION", name)
    monkeypatch.setattr(ai._installed, "host_key", "")
    return name


async def _save(db: AsyncSession, section: str, key: str) -> None:
    form = await settings.form(db, section)
    await settings.save(db, section, {"api_key": key}, version=form["version"], by=None)
    await db.commit()


@pytest.mark.db
async def test_with_no_key_the_ai_is_off(db: AsyncSession, section: str) -> None:
    assert await ai.source(db) == "none"
    assert await ai.readiness(db) == ai.Readiness(ready=False, unreadable=False)
    with pytest.raises(Problem) as off:
        await ai.key_in_use(db)
    assert (off.value.code, off.value.status) == ("kernel.ai_off", 503)


@pytest.mark.db
async def test_the_hosts_key_is_used_while_none_is_saved(
    db: AsyncSession, section: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai._installed, "host_key", HOST_KEY)
    assert await ai.key_in_use(db) == (HOST_KEY, "environment")
    assert await ai.readiness(db) == ai.Readiness(ready=True, unreadable=False)


@pytest.mark.db
async def test_a_placeholder_on_the_host_counts_as_none(
    db: AsyncSession, section: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai._installed, "host_key", "sk-ant-...")
    assert await ai.source(db) == "none"


@pytest.mark.db
async def test_a_saved_key_wins_over_the_hosts_and_removing_it_brings_the_hosts_back(
    db: AsyncSession, section: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai._installed, "host_key", HOST_KEY)
    await _save(db, section, KEY)
    assert await ai.key_in_use(db) == (KEY, "settings")
    # Sealed at rest: the row never holds the key.
    row = (await db.scalars(select(Setting).where(Setting.module_id == section))).one()
    assert KEY not in str(row.values)
    await _save(db, section, "")
    assert await ai.key_in_use(db) == (HOST_KEY, "environment")


@pytest.mark.db
async def test_a_saved_key_that_cant_be_opened_is_reported_never_swapped_for_the_hosts(
    db: AsyncSession, section: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai._installed, "host_key", HOST_KEY)
    await _save(db, section, KEY)

    def lost(sealed: str) -> str:
        raise crypto.SealError("The keys changed.")

    monkeypatch.setattr(crypto, "open", lost)
    assert await ai.source(db) == "settings"
    assert await ai.readiness(db) == ai.Readiness(ready=False, unreadable=True)
    with pytest.raises(Problem) as unreadable:
        await ai.key_in_use(db)
    assert (unreadable.value.code, unreadable.value.status) == ("kernel.ai_key_unreadable", 503)


@pytest.mark.db
async def test_a_value_that_cant_be_a_key_isnt_saved_nor_repeated(
    db: AsyncSession, section: str
) -> None:
    pasted = "sk-ant short paste"
    form = await settings.form(db, section)
    with pytest.raises(Problem) as refused:
        await settings.save(db, section, {"api_key": pasted}, version=form["version"], by=None)
    await db.rollback()
    assert refused.value.code == "kernel.invalid_request"
    said = " ".join(refused.value.errors["api_key"])
    assert "no spaces" in said
    assert pasted not in said
    assert await ai.source(db) == "none"


def test_a_bad_budget_fails_the_start() -> None:
    with pytest.raises(ValueError, match="isn't a rate rule"):
        ai.install(api_key=SecretStr(""), model="claude-opus-5-5", rate_rule="twenty an hour")


# --- the request -----------------------------------------------------------------------


async def test_a_task_sends_the_rules_then_the_style_each_cached(fake: FakeAnthropic) -> None:
    words = await _writer("The site's rules.").write(
        "Do it.", style=STYLE, max_tokens=100, effort="low"
    )
    assert words == "Words for the test."
    asked = fake.asked[0]
    assert asked.key == KEY
    body = asked.body
    assert body["model"] == ai.model()
    assert next(block["text"] for block in body["system"]) == "The site's rules."
    assert "<name>Warm</name>" in body["system"][1]["text"]
    assert "- delve" in body["system"][1]["text"]
    assert "We make music." in body["system"][1]["text"]
    assert all(block["cache_control"] == {"type": "ephemeral"} for block in body["system"])
    assert body["messages"] == [{"role": "user", "content": "Do it."}]
    assert body["output_config"] == {"effort": "low"}


async def test_the_house_style_sends_the_rules_alone(fake: FakeAnthropic) -> None:
    await _writer().write("Do it.", max_tokens=100, effort="low")
    assert len(fake.asked[0].body["system"]) == 1


async def test_a_structured_task_asks_for_its_shape_and_reads_it(fake: FakeAnthropic) -> None:
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    found = await _writer().write("Do it.", max_tokens=100, effort="low", schema=schema)
    assert found == {"a": "Words for the test."}
    assert fake.asked[0].body["output_config"]["format"] == {
        "type": "json_schema",
        "schema": schema,
    }


async def test_an_answer_not_in_its_shape_is_a_plain_failure(fake: FakeAnthropic) -> None:
    fake.queue("not json")
    with pytest.raises(Problem) as failed:
        await _writer().write("Do it.", max_tokens=100, effort="low", schema={"type": "object"})
    assert (failed.value.code, failed.value.status, failed.value.detail) == (
        "kernel.ai_failed",
        502,
        ai.WRONG_SHAPE,
    )


@pytest.mark.parametrize(
    ("status", "said"),
    [
        (401, "Anthropic didn't accept the key."),
        (403, "Anthropic refused the key"),
        (429, "Anthropic is busy"),
        (500, "Anthropic answered with an error (500)."),
    ],
)
async def test_an_error_is_said_plainly_without_the_key_or_anthropics_words(
    fake: FakeAnthropic, status: int, said: str, caplog: pytest.LogCaptureFixture
) -> None:
    fake.queue(status=status)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(Problem) as failed:
        await _writer().write("Do it.", max_tokens=100, effort="low", retries=0)
    assert failed.value.status == 502
    assert failed.value.code == "kernel.ai_failed"
    assert said in str(failed.value.detail)
    assert "fake's refusal" not in str(failed.value.detail)
    assert KEY not in str(failed.value.detail)
    assert KEY not in caplog.text


@pytest.mark.parametrize(
    ("stop", "said"),
    [("refusal", "The AI declined this request."), ("max_tokens", ai.CUT_OFF)],
)
async def test_a_refusal_or_a_cut_off_answer_is_a_failure(
    fake: FakeAnthropic, stop: str, said: str
) -> None:
    fake.queue("Half an", stop_reason=stop)
    with pytest.raises(Problem) as failed:
        await _writer().write("Do it.", max_tokens=100, effort="low")
    assert said in str(failed.value.detail)


async def test_a_timeout_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=request)

    before = ai.use_transport(httpx2.MockTransport(slow))
    try:
        with pytest.raises(Problem) as failed:
            await _writer().write("Do it.", max_tokens=100, effort="low", retries=0)
    finally:
        ai.use_transport(before)
    assert failed.value.detail == "The AI took too long to answer. Try again."


async def test_the_fallback_beta_goes_only_with_a_model_that_takes_it(
    fake: FakeAnthropic, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai._installed, "model", "claude-opus-5-5")
    await _writer().write("Do it.", max_tokens=100, effort="low")
    assert ai.FALLBACK_BETA in fake.asked[-1].beta
    assert fake.asked[-1].body["fallbacks"] == "default"
    monkeypatch.setattr(ai._installed, "model", "claude-haiku-5-5")
    await _writer().write("Do it.", max_tokens=100, effort="low")
    assert "fallbacks" not in fake.asked[-1].body


async def test_the_check_lists_one_model(fake: FakeAnthropic) -> None:
    await _writer().check()
    assert fake.asked[0].method == "GET"
    assert fake.asked[0].path.endswith("/models")
    fake.queue(status=401)
    with pytest.raises(Problem) as refused:
        await _writer().check()
    assert refused.value.status == 502


# --- the tasks -------------------------------------------------------------------------


async def test_a_draft_says_what_it_writes_and_for_whom(fake: FakeAnthropic) -> None:
    fake.queue("## Opening\n\nWords.")
    text = await ai.draft(
        _writer(), what="Post body", topic="Our new album", length="short", style=None
    )
    assert text == "## Opening\n\nWords."
    task = fake.asked[0].body["messages"][0]["content"]
    assert "the post body for Test Site" in task
    assert "Our new album" in task
    assert "400-600 words" in task
    assert fake.asked[0].body["output_config"] == {"effort": "high"}


async def test_an_empty_draft_is_a_failure(fake: FakeAnthropic) -> None:
    fake.queue("   ")
    with pytest.raises(Problem):
        await ai.draft(_writer(), what="Post body", topic="x", length="medium", style=None)


async def test_titles_are_trimmed_kept_once_and_at_most_eight(fake: FakeAnthropic) -> None:
    many = ['"One"', "one", " Two  words ", "", *[f"Title {n}" for n in range(10)], "x" * 300]
    fake.queue(answer={"titles": many})
    found = await ai.titles(_writer(), what="Post body", topic="", body="The text.", style=None)
    assert found[:2] == ["One", "Two words"]
    assert len(found) == ai.TITLES_MOST
    assert "<text>\nThe text.\n</text>" in fake.asked[0].body["messages"][0]["content"]


async def test_titles_from_the_topic_while_nothing_is_written(fake: FakeAnthropic) -> None:
    await ai.titles(_writer(), what="Post body", topic="Spring tour", body="  ", style=None)
    assert "It's about: Spring tour" in fake.asked[0].body["messages"][0]["content"]


async def test_a_summary_is_cut_to_its_fields_limit(fake: FakeAnthropic) -> None:
    fake.queue(answer={"summary": "word " * 200})
    found = await ai.summary(_writer(), what="Post body", body="The text.", most=120, style=None)
    assert len(found) <= 120
    assert found.endswith("…")


async def test_search_words_are_cut_to_seventy_and_one_hundred_sixty(fake: FakeAnthropic) -> None:
    fake.queue(answer={"title": "word " * 30, "description": "word " * 60})
    shown, under = await ai.search_words(
        _writer(), what="Post body", title="T", body="B", style=None
    )
    assert len(shown) <= ai.SEARCH_TITLE_MAX
    assert len(under) <= ai.SEARCH_DESCRIPTION_MAX


@pytest.mark.parametrize("answer", [{"titles": "one"}, {"titles": []}, {"nothing": 1}])
async def test_titles_not_in_their_shape_are_a_failure(
    fake: FakeAnthropic, answer: dict[str, Any]
) -> None:
    fake.queue(answer=answer)
    with pytest.raises(Problem):
        await ai.titles(_writer(), what="Post body", topic="x", body="", style=None)


BODY = (
    "## Listen\n\nHear [the album](/music/album) and see ![the cover](https://cdn.test/c.png).\n"
    "More at <https://example.test/more> or https://example.test/plain."
)


async def test_a_rewrite_keeps_every_address_and_comes_out_of_its_tags(fake: FakeAnthropic) -> None:
    rewritten = BODY.replace("Hear", "Listen to")
    fake.queue(f"<text>\n{rewritten}\n</text>")
    assert await ai.rewrite(_writer(), what="Post body", text=BODY, style=STYLE) == rewritten
    assert "in the style set out above" in fake.asked[0].body["messages"][0]["content"]


async def test_a_rewrite_that_drops_a_link_is_refused_and_the_text_kept(
    fake: FakeAnthropic,
) -> None:
    fake.queue(BODY.replace("[the album](/music/album)", "the album"))
    with pytest.raises(Problem) as lost:
        await ai.rewrite(_writer(), what="Post body", text=BODY, style=None)
    assert (lost.value.code, lost.value.status) == ("kernel.ai_rewrite_lost", 502)
    assert "left out 1 link or image" in str(lost.value.detail)


def test_addresses_are_every_link_image_and_bare_address() -> None:
    assert ai.addresses(BODY) == {
        "/music/album",
        "https://cdn.test/c.png",
        "https://example.test/more",
        "https://example.test/plain",
    }


async def test_style_rules_are_fitted_to_what_a_style_holds(fake: FakeAnthropic) -> None:
    fake.queue(answer={"voice_rules": " - Short. ", "avoid": ["delve", "Delve", "x" * 200]})
    voice_rules, avoid = await ai.style_rules(_writer(), ["We make music."])
    assert (voice_rules, avoid) == ("- Short.", "delve")
    assert len(fake.asked[0].body["system"]) == 1
