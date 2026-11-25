"""social's settings, bodies and answers (`dev plans/contracts/social.md` §2).

`Settings` is the section `social`, drawn on Settings, Site, as "Social": a
Buffer token saved there, sealed, never answered and never kept in a version.
It wins over the host's BUFFER_ACCESS_TOKEN.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from kernel import Answer, Id, When
from social.buffer import token_problem
from social.models import MAX_ADMIN_PATH, MAX_TEXT, MAX_TYPE

Mode = Literal["queue", "now", "at", "draft"]
State = Literal["sending", "queued", "draft", "sent", "failed", "refused", "unknown", "removed"]
Source = Literal["saved", "host", "none"]
#: A content type: `<module>.<entity>`, as the kernel's hooks name one.
CONTENT_TYPE = r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9_]*$"
#: The most channels one share goes to.
MAX_CHANNELS = 10


class Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    #: A token saved in Settings, sealed; None is the host's, BUFFER_ACCESS_TOKEN.
    buffer_token: SecretStr | None = None

    @field_validator("buffer_token")
    @classmethod
    def _could_be_a_token(cls, token: SecretStr | None) -> SecretStr | None:
        if token is not None and (problem := token_problem(token.get_secret_value())) is not None:
            raise ValueError(problem)
        return token


# --- answers ----------------------------------------------------------------------------------


class SocialChannel(Answer):
    id: str
    name: str
    #: Buffer's own: `linkedin`, `twitter`, …
    service: str
    #: The network as people name it: "X".
    network: str
    descriptor: str
    #: It can take a link post now.
    usable: bool
    #: Why it can't, or "".
    problem: str
    #: A paused queue holds what's queued until it's resumed in Buffer.
    queue_paused: bool
    #: The longest text it takes, the link included; None for a network that takes no link posts.
    limit: int | None


class TokenState(Answer):
    """Never the token: where the one in use comes from, and what it reached."""

    source: Source
    #: A saved token can't be opened (ENCRYPTION_KEYS changed): nothing is shared until it's saved again.
    unreadable: bool
    channels: list[SocialChannel]
    listed_at: When | None


class ChannelList(Answer):
    channels: list[SocialChannel]
    listed_at: When


class SharePreview(Answer):
    """The thing's link, as its page's head tags name it."""

    url: str
    title: str
    description: str
    image: str | None


class SocialShare(Answer):
    id: Id
    channel_id: str
    channel_name: str
    service: str
    network: str
    text: str
    link: str
    mode: Mode
    due_at: When | None
    state: State
    error: str
    #: The post's address on the network, once it's sent.
    external_link: str | None
    sent_at: When | None
    sent_by_name: str
    created_at: When


class ShareView(Answer):
    """What the Share card opens with, from the database alone."""

    #: A token is in use and readable, and Buffer has listed its channels.
    ready: bool
    source: Source
    unreadable: bool
    #: The thing is public now, so it can be shared.
    live: bool
    card: SharePreview | None
    #: The text to start from: the title, then the description.
    text: str
    channels: list[SocialChannel]
    listed_at: When | None
    history: list[SocialShare]


class ShareSent(Answer):
    #: This send's shares, one a channel, in the order the channels were chosen.
    results: list[SocialShare]
    history: list[SocialShare]


class ShareHistory(Answer):
    history: list[SocialShare]


# --- bodies -----------------------------------------------------------------------------------


class Thing(BaseModel):
    """A thing to share, by its content type and id."""

    model_config = ConfigDict(strict=True, extra="forbid")

    type: str = Field(min_length=3, max_length=MAX_TYPE, pattern=CONTENT_TYPE)
    id: str = Field(min_length=1, max_length=36)


class ShareSend(Thing):
    #: The admin page it's shared from: the Dashboard's notice sends people there.
    admin_path: str = Field(min_length=6, max_length=MAX_ADMIN_PATH)
    channel_ids: list[str] = Field(min_length=1, max_length=MAX_CHANNELS)
    text: str = Field(max_length=MAX_TEXT)
    when: Mode = "queue"
    #: For `at`: when it goes out, at least a minute ahead.
    due_at: str | None = Field(default=None, max_length=40)
    #: Post to a channel this thing already went to.
    again: bool = False
