"""The newsletter's settings, bodies and answers (`dev plans/contracts/campaigns.md` §2).

`Settings` is the section `campaigns`, edited in the admin's Settings as
"Newsletter": whether sign-ups are open, the postal address every newsletter
carries (CAN-SPAM; nothing sends until it's set), the footer's note and the
send pace.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from campaigns.models import (
    MAX_BODY,
    MAX_DETAIL,
    MAX_EMAIL,
    MAX_NAME,
    MAX_PREVIEW,
    MAX_SOURCE,
    MAX_SUBJECT,
)
from kernel import Answer, BotProof, Id, When, email

Kind = Literal["newsletter", "release"]
EmailStatus = Literal["draft", "scheduled", "sending", "sent"]
EmailTab = Literal["all", "draft", "scheduled", "sent"]
SubscriberStatus = Literal["pending", "subscribed", "unsubscribed"]
SubscriberTab = Literal["all", "pending", "subscribed", "unsubscribed"]
Why = Literal["bounced", "complained", "unsubscribed"]
SOURCE = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_NOTE = 300
MAX_ADDRESS = 300
MAX_TOKEN = 200
DEFAULT_NOTE = "You're getting this because you asked for news from ${site_name}."

#: Control characters and Unicode's line and paragraph separators: the kernel
#: mailer refuses any of them in a header.
REFUSED = frozenset({"Cc", "Zl", "Zp"})


def one_line(value: str) -> str:
    """The text trimmed, refused if it holds a line break or a control character:
    by the kernel mailer's own rule (Unicode's Cc, Zl and Zp, C1 controls among
    them), so a subject saved is one it sends (CodeRabbit on #134)."""
    if any(unicodedata.category(each) in REFUSED for each in value):
        raise ValueError("One line, with no line breaks.")
    return value.strip()


def _no_nul(value: str) -> str:
    # Postgres's text holds no NUL: refused here, a field's error, not at the flush.
    if chr(0) in value:
        raise ValueError("The text can't hold a NUL character.")
    return value


class Settings(BaseModel):
    model_config = ConfigDict(strict=True)

    #: The board's "Sign-ups open": while it's off, the forms say sign-ups are closed.
    signups_open: bool = True
    #: The postal address every newsletter carries (a P.O. box will do). Nothing sends without it.
    postal_address: str = Field(default="", max_length=MAX_ADDRESS)
    #: The footer's first line; ${site_name} is the site's name.
    footer_note: str = Field(default=DEFAULT_NOTE, max_length=MAX_NOTE)
    #: How many newsletter messages may go out in an hour (a sixtieth each minute).
    send_per_hour: int = Field(default=6_000, ge=1, le=10_000)

    @field_validator("postal_address")
    @classmethod
    def _address(cls, value: str) -> str:
        # Lines are kept, each trimmed, blank ones dropped: the text part prints
        # them as typed, the HTML runs them together with commas.
        _no_nul(value)
        lines = [line.strip() for line in value.splitlines()]
        if any(ord(each) < 32 and each not in "\t" for line in lines for each in line):
            raise ValueError("The address can't hold a control character.")
        return "\n".join(line for line in lines if line)

    @field_validator("footer_note")
    @classmethod
    def _note(cls, value: str) -> str:
        return one_line(value)


# --- the public forms -------------------------------------------------------------------


class NewSubscription(BaseModel):
    """A sign-up. `bot` is the kit's `useBotProof()` (hook 5)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    email: str = Field(max_length=MAX_EMAIL + 64)
    name: str | None = Field(default=None, max_length=MAX_NAME)
    #: `form`, or a site's own short name for its form.
    source: str = Field(default="form", min_length=1, max_length=MAX_SOURCE, pattern=SOURCE)
    bot: BotProof | None = None

    @field_validator("email")
    @classmethod
    def _one_address(cls, value: str) -> str:
        value = value.strip()
        if not email.is_address(value):
            raise ValueError("Enter one email address, like name@example.com.")
        # Kept lowercased too, and lowercasing can lengthen a letter beyond ASCII.
        if len(value.lower()) > MAX_EMAIL:
            raise ValueError("That address is too long.")
        return value

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return one_line(value) or None


class SignupReceived(Answer):
    """The same answer whatever the address's state, so nobody learns who's subscribed."""

    received: bool


class SignupState(Answer):
    """Whether the site takes sign-ups now: `useNewsletterOn()`'s answer."""

    open: bool


class NewsletterConfirm(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    token: str = Field(min_length=1, max_length=MAX_TOKEN)


class SubscriptionLink(Answer):
    """What a confirm or unsubscribe link names: the address, partly hidden, and its state."""

    email_hint: str
    subscribed: bool


# --- the admin's emails -----------------------------------------------------------------


class CampaignEmailItem(Answer):
    id: Id
    subject: str
    kind: Kind
    status: EmailStatus
    #: The people it went to; for a scheduled email, the people it would reach now.
    sent_to: int
    #: When it was sent, starts or started; null for a draft.
    when: When | None


class NewsletterCounts(Answer):
    """The three cards, and the tabs' counts."""

    subscribed: int
    pending: int
    unsubscribed: int
    scheduled: int
    set_aside: int
    emails: int


class ScheduledNext(Answer):
    """The Scheduled card's "Up next"."""

    id: Id
    subject: str
    when: When


class NewsletterWaiting(Answer):
    """The attention card, as the Dashboard shows it."""

    tone: Literal["info", "warning", "danger"]
    what: str
    why: str
    label: str
    to: str


class NewsletterSetup(Answer):
    """What the page says before anything sends: sign-ups' pill, the address, the bounce reader."""

    signups_open: bool
    has_address: bool
    reads_bounces: bool


class CampaignEmailsPage(Answer):
    items: list[CampaignEmailItem]
    next_cursor: str | None
    counts: NewsletterCounts
    scheduled: ScheduledNext | None
    waiting: NewsletterWaiting | None
    setup: NewsletterSetup


class _CampaignEmailFields(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    @field_validator("subject", "preview", check_fields=False)
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return None if value is None else one_line(value)

    @field_validator("body", check_fields=False)
    @classmethod
    def _body(cls, value: str | None) -> str | None:
        return None if value is None else _no_nul(value)


class NewCampaignEmail(_CampaignEmailFields):
    kind: Kind = "newsletter"
    subject: str = Field(min_length=1, max_length=MAX_SUBJECT)
    preview: str = Field(default="", max_length=MAX_PREVIEW)
    body: str = Field(default="", max_length=MAX_BODY)

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str) -> str:
        if not value:
            raise ValueError("An email needs a subject.")
        return value


class CampaignEmailChange(_CampaignEmailFields):
    """What a save changes: only the fields it sends, with the `version` it read."""

    version: int = Field(ge=1)
    kind: Kind | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=MAX_SUBJECT)
    preview: str | None = Field(default=None, max_length=MAX_PREVIEW)
    body: str | None = Field(default=None, max_length=MAX_BODY)

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("An email needs a subject.")
        return value


class CampaignEmail(Answer):
    id: Id
    version: int
    kind: Kind
    subject: str
    preview: str
    body: str
    status: EmailStatus
    send_at: When | None
    started_at: When | None
    sent_at: When | None
    sent_to: int
    #: The people a send now would reach: subscribed and not set aside.
    audience: int
    #: Made from blog's post, when it was.
    from_post: bool
    created_at: When
    updated_at: When


class CampaignPreviewBody(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    body: str = Field(max_length=MAX_BODY)


class CampaignPreview(Answer):
    """The email's words and footer as a subscriber reads them, for the editor's Preview."""

    html: str


class CampaignSend(BaseModel):
    """Now, or at `at`, a time with its zone still to come."""

    model_config = ConfigDict(strict=True, extra="forbid")

    at: str | None = Field(default=None, max_length=40)


class CampaignTestSent(Answer):
    """Where the test went: the asker's own address."""

    to: str


# --- the admin's people -----------------------------------------------------------------


class NewsletterSubscriber(Answer):
    id: Id
    email: str
    name: str | None
    source: str
    status: SubscriberStatus
    #: When it reached its status: asked, confirmed or unsubscribed.
    since: When


class NewsletterSubscribers(Answer):
    items: list[NewsletterSubscriber]
    next_cursor: str | None
    counts: NewsletterCounts


class NewsletterSetAside(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    why: Why
    detail: str | None = Field(default=None, max_length=MAX_DETAIL)

    @field_validator("detail")
    @classmethod
    def _detail(cls, value: str | None) -> str | None:
        return None if value is None else one_line(value)


class SetAsideAddress(Answer):
    email: str
    why: Why
    #: A bounce's code, or what a person wrote setting it aside.
    detail: str
    since: When


class SetAsideAddresses(Answer):
    items: list[SetAsideAddress]
    next_cursor: str | None
    #: Whether the bounce mailbox is read: else the tab says bounces aren't being read.
    reads_bounces: bool


class CampaignWebhookTaken(Answer):
    received: bool
