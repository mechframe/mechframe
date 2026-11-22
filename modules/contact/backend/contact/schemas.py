"""The contact module's settings, answers and bodies (`dev plans/contracts/contact.md` §2).

`Settings` is the section `contact`: the Contact page's intro line and the
topics a message can be about, edited in the admin's Settings. A topic's
`first` puts its new messages at the top of the Inbox.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contact.models import MAX_EMAIL, MAX_MESSAGE, MAX_NAME, MAX_TOPIC, MAX_TOPIC_LABEL
from kernel import Answer, BotProof, Id, When, email

Status = Literal["new", "replied", "archived", "spam"]
Tab = Literal["all", "new", "replied", "archived", "spam"]
TOPIC_KEY = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_INTRO = 300
MAX_TOPICS = 12

#: What breaks a line besides a control character: NEL and the line and
#: paragraph separators, which str.splitlines() reads as line ends.
_BREAKS = frozenset(chr(code) for code in (0x85, 0x2028, 0x2029))


def one_line(value: str) -> str:
    """The text trimmed, refused if it holds a line break or a control character."""
    if any(ord(each) < 32 or ord(each) == 127 or each in _BREAKS for each in value):
        raise ValueError("One line, with no line breaks.")
    return value.strip()


class Topic(BaseModel):
    """One thing a message can be about."""

    model_config = ConfigDict(strict=True, extra="forbid")

    key: str = Field(min_length=1, max_length=MAX_TOPIC, pattern=TOPIC_KEY)
    label: str = Field(min_length=1, max_length=MAX_TOPIC_LABEL)
    first: bool = False

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        value = one_line(value)
        if not value:
            raise ValueError("A topic needs a label.")
        return value


def _default_topics() -> list[Topic]:
    return [
        Topic(key="question", label="A question"),
        Topic(key="work", label="Working together", first=True),
        Topic(key="press", label="Press"),
        Topic(key="other", label="Something else"),
    ]


class Settings(BaseModel):
    model_config = ConfigDict(strict=True)

    #: The line under the Contact page's heading, and the page's description.
    intro: str = Field(default="Send a message and we'll reply by email.", max_length=MAX_INTRO)
    #: What a message can be about, in the form's order.
    topics: list[Topic] = Field(
        default_factory=_default_topics, min_length=1, max_length=MAX_TOPICS
    )

    @field_validator("intro")
    @classmethod
    def _intro(cls, value: str) -> str:
        return one_line(value)

    @field_validator("topics")
    @classmethod
    def _keys(cls, value: list[Topic]) -> list[Topic]:
        keys = [topic.key for topic in value]
        if len(set(keys)) != len(keys):
            raise ValueError("Each topic needs a key of its own.")
        return value


# --- the public form ------------------------------------------------------------------


class ContactTopic(Answer):
    key: str
    label: str


class ContactForm(Answer):
    """What the Contact page's form shows."""

    intro: str
    topics: list[ContactTopic]


class NewContactMessage(BaseModel):
    """A visitor's message. `bot` is the kit's `useBotProof()` (hook 5)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(max_length=MAX_NAME)
    email: str = Field(max_length=MAX_EMAIL + 64)
    topic: str = Field(max_length=MAX_TOPIC)
    message: str = Field(max_length=MAX_MESSAGE)
    wants_news: bool = False
    bot: BotProof | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = one_line(value)
        if not value:
            raise ValueError("Enter your name.")
        return value

    @field_validator("email")
    @classmethod
    def _one_address(cls, value: str) -> str:
        value = value.strip()
        if not email.is_address(value):
            raise ValueError("Enter one email address, like name@example.com.")
        return value

    @field_validator("message")
    @classmethod
    def _message(cls, value: str) -> str:
        # Postgres's text holds no NUL: refused here, a field's error, not at the flush.
        if chr(0) in value:
            raise ValueError("A message can't hold a NUL character.")
        if not value.strip():
            raise ValueError("Write your message.")
        return value


class MessageReceived(Answer):
    """The same answer whether the message passed or was held (hook 5)."""

    received: bool


# --- the Inbox ------------------------------------------------------------------------


class InboxItem(Answer):
    """A message in the Inbox's list."""

    id: Id
    name: str
    topic_label: str
    #: The message's opening words, on one line.
    first_line: str
    status: Status
    #: Its topic is one of Settings' first topics.
    first: bool
    received_at: When


class InboxCounts(Answer):
    new: int
    replied: int
    archived: int
    spam: int


class InboxWaiting(Answer):
    """The "Needs you" item for new messages, as the Dashboard shows it."""

    tone: Literal["info", "warning", "danger"]
    what: str
    why: str
    label: str
    to: str


class InboxPage(Answer):
    """One page of a tab, with every tab's count and the waiting item."""

    items: list[InboxItem]
    next_cursor: str | None
    counts: InboxCounts
    waiting: InboxWaiting | None


class InboxMessage(Answer):
    """One message, opened."""

    id: Id
    name: str
    email: str
    topic_label: str
    message: str
    wants_news: bool
    status: Status
    #: Why the bot check or the filters held it, or null.
    held_reason: str | None
    received_at: When
    status_at: When


class InboxExport(Answer):
    """Every message in a tab, for the Inbox's Export (a CSV made in the browser)."""

    items: list[InboxMessage]


class MessageStatus(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    status: Status
