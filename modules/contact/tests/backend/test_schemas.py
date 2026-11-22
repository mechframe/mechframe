"""contact's settings and the form's body refuse what can't be stored or
shown (`dev plans/contracts/contact.md` §2)."""

from __future__ import annotations

from typing import Any

import pytest
from contact.schemas import NewContactMessage, Settings, Topic
from pydantic import ValidationError


def _message(**fields: Any) -> dict[str, Any]:
    return {
        "name": "Rae",
        "email": "rae@example.com",
        "topic": "work",
        "message": "Can you play in March?",
        **fields,
    }


def test_the_defaults_are_four_topics_with_working_together_first() -> None:
    cfg = Settings()
    assert [(t.key, t.first) for t in cfg.topics] == [
        ("question", False),
        ("work", True),
        ("press", False),
        ("other", False),
    ]


@pytest.mark.parametrize(
    "topics",
    [
        [],
        [{"key": "a", "label": "A"}, {"key": "a", "label": "Another"}],
        [{"key": "Not A Key", "label": "A"}],
        [{"key": "a", "label": "   "}],
        [{"key": "a", "label": "Two\nlines"}],
        [{"key": f"t{n}", "label": "T"} for n in range(13)],
    ],
)
def test_settings_refuse_topics_that_can_t_be_shown(topics: list[dict[str, Any]]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"topics": topics})


def test_a_topic_s_label_is_trimmed() -> None:
    assert Topic(key="press", label="  Press ").label == "Press"


def test_a_message_is_trimmed_where_it_s_one_line() -> None:
    body = NewContactMessage.model_validate(_message(name="  Rae  ", email=" rae@example.com "))
    assert (body.name, body.email, body.wants_news, body.bot) == (
        "Rae",
        "rae@example.com",
        False,
        None,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", "   "),
        ("name", "Rae\nOkafor"),
        ("name", "x" * 201),
        ("email", "not an address"),
        ("email", "a@example.com, b@example.com"),
        ("message", "   "),
        ("message", "Hi" + chr(0)),
        ("message", "x" * 5_001),
        ("topic", "x" * 41),
        # Lowercased, each dotted capital I is two characters: 412 in all (CodeRabbit on #125).
        ("email", chr(0x130) * 200 + "@example.com"),
    ],
)
def test_a_message_refuses_what_can_t_be_stored(field: str, value: str) -> None:
    with pytest.raises(ValidationError) as refused:
        NewContactMessage.model_validate(_message(**{field: value}))
    assert {error["loc"][0] for error in refused.value.errors()} == {field}


def test_a_message_refuses_a_field_it_doesn_t_know() -> None:
    with pytest.raises(ValidationError):
        NewContactMessage.model_validate(_message(phone="555"))
