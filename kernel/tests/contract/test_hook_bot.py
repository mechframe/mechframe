"""Hook 5, bot check (decision 0052; `dev plans/contracts/hooks.md` §7, test 5),
over HTTP only, on the probe module's form, with the kernel's `form` check
(the default): a filled `website` field, a fill under three seconds, or no
proof at all is held; a person's form passes. The probe answers the verdict
so the suite can see it; a real module answers a held submission and a
passed one alike."""

from __future__ import annotations

from typing import Any

import pytest

from .conftest import Api

pytestmark = pytest.mark.db

FORM = "/api/probe/inquiries"


async def _held(api: Api, **body: Any) -> str | None:
    sent = await api.http.post(FORM, json={"message": "Hello there", **body})
    assert sent.status_code == 201, sent.text
    held: str | None = sent.json()["held"]
    return held


async def test_a_persons_form_passes_and_a_bots_is_held(api: Api) -> None:
    person = {"website": "", "elapsed_ms": 12_000}
    assert await _held(api, bot=person) is None
    assert await _held(api, bot={**person, "website": "   "}) is None  # autofill's whitespace
    assert await _held(api, bot={"website": "", "elapsed_ms": 3_000}) is None

    assert await _held(api, bot={**person, "website": "http://spam.example"}) == "honeypot"
    assert await _held(api, bot={"website": "", "elapsed_ms": 2_999}) == "too_fast"
    assert await _held(api) == "not_from_form"  # no proof at all
    assert await _held(api, bot={"elapsed_ms": 12_000}) == "not_from_form"
    assert await _held(api, bot={"website": ""}) == "not_from_form"


async def test_a_proof_that_isnt_one_is_refused(api: Api) -> None:
    for proof in ({"elapsed_ms": -1}, {"website": "x" * 501}, {"elapsed_ms": "soon"}):
        sent = await api.http.post(FORM, json={"message": "Hello", "bot": proof})
        assert sent.status_code == 422, sent.text
