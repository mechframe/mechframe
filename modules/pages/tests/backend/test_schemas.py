"""What a page's body may hold (`dev plans/contracts/pages.md` §3): one-line
titles and search words, and no character Postgres can't store."""

from __future__ import annotations

import pytest
from pages.schemas import NewPage, PageChange
from pydantic import ValidationError

#: Every line boundary str.splitlines() knows but the CR LF pair, each by number.
BREAKS = [chr(code) for code in (10, 13, 11, 12, 28, 29, 30, 0x85, 0x2028, 0x2029)]


@pytest.mark.parametrize("breaking", BREAKS)
@pytest.mark.parametrize("field", ["title", "search_title", "search_description"])
def test_a_title_and_search_words_are_one_line(field: str, breaking: str) -> None:
    fields = {"title": "About", "address": "/about", field: f"About{breaking}us"}
    with pytest.raises(ValidationError, match="One line"):
        NewPage.model_validate(fields)
    with pytest.raises(ValidationError, match="One line"):
        PageChange.model_validate({"version": 1, field: f"About{breaking}us"})


def test_one_line_words_and_empty_search_words_pass() -> None:
    page = NewPage.model_validate(
        {"title": "  Café · About  ", "address": "/about", "search_title": None}
    )
    assert (page.title, page.search_title) == ("Café · About", None)


@pytest.mark.parametrize("model", [NewPage, PageChange])
def test_a_body_holds_no_nul_which_postgres_cant_store(model: type) -> None:
    fields = {"title": "About", "address": "/about"} if model is NewPage else {"version": 1}
    with pytest.raises(ValidationError, match="NUL"):
        model.model_validate({**fields, "body": "Before\x00after"})
    assert model.model_validate({**fields, "body": "Lines\nand\ttabs"}).body == "Lines\nand\ttabs"
