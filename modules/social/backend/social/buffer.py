"""Buffer, which posts to the site's channels: one integration in place of each
network's own API, and the only way onto a LinkedIn page without LinkedIn's
app review (lifted from VybeSite's `services/buffer_service.py`).

Buffer's API is GraphQL at one address, with an access token from
publish.buffer.com's API settings as a bearer token. It answers 200 to nearly
everything: a refused token or a fault comes back in an `errors` array, and a
post it won't take as a typed error in the mutation's answer. Its rate limit is
a 429 with Retry-After; the free plan allows 100 requests every 15 minutes.

The token is opened by `service.py` just before a call and handed in here.
Nothing here logs it, and every message is scrubbed of it.

Failures come in two kinds. `BufferError`: nothing was made, say why.
`Unanswered`: a post's request went out and no answer came back, so it may
have been made; the share is kept as `unknown` and never posted twice by
mistake.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

API = "https://api.buffer.com"
USER_AGENT = "mechframe (website admin)"
TIMEOUT_SECONDS = 15.0
LINK_TIMEOUT_SECONDS = 10.0


@dataclass
class _Installed:
    #: Tests and the harness hand in an httpx transport (`use_transport`); None is the real network.
    transport: httpx.AsyncBaseTransport | None = None


_installed = _Installed()


def use_transport(transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncBaseTransport | None:
    """Every call goes through `transport` from now on: a fake Buffer, for the
    tests and the harness. Answers the one it replaces."""
    before = _installed.transport
    _installed.transport = transport
    return before


#: The longest text each network takes (Buffer's character limits).
LIMITS = {
    "linkedin": 3000,
    "facebook": 5000,
    "twitter": 280,
    "threads": 500,
    "bluesky": 300,
    "mastodon": 500,
}

#: The networks a link post goes to (§8, 4): every other needs a picture or a video of its own.
LINK_SERVICES = frozenset(LIMITS)

#: Each network as people name it.
NETWORKS = {
    "linkedin": "LinkedIn",
    "facebook": "Facebook",
    "twitter": "X",
    "threads": "Threads",
    "bluesky": "Bluesky",
    "mastodon": "Mastodon",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
    "pinterest": "Pinterest",
    "googlebusiness": "Google Business Profile",
    "startPage": "Start Page",
}

#: Networks whose post carries the link as a card of its own, sent whole, so
#: the link needn't be in the text. Every other gets it at the end of its text.
CARDS = frozenset({"linkedin"})

# Bounds that only catch a paste that is plainly something else: Check asks Buffer,
# which is the real test.
MIN_TOKEN_LENGTH = 20
MAX_TOKEN_LENGTH = 400

PLACE = "Settings, under Social"
REFUSED_TOKEN = (
    "Buffer didn't accept the token. Copy it again from Buffer's API settings, and save it in "
    f"{PLACE}, or set BUFFER_ACCESS_TOKEN on the host."
)
UNREACHABLE = "Buffer couldn't be reached, so nothing was sent. Try again in a minute."
SLOW = "Buffer didn't answer in time. Try again in a minute."
MAYBE_SENT = (
    "Buffer didn't answer, so this may or may not have gone. Check the channel's queue in "
    "Buffer before posting it again."
)

ORGANIZATIONS = "query { account { organizations { id name } } }"
CHANNELS = (
    "query($input: ChannelsInput!) { channels(input: $input) { id name service descriptor avatar "
    "organizationId isDisconnected isLocked isQueuePaused } }"
)
POST_FIELDS = "id status dueAt sentAt externalLink error { message }"
CREATE = (
    "mutation($input: CreatePostInput!) { createPost(input: $input) { __typename "
    f"... on PostActionSuccess {{ post {{ {POST_FIELDS} }} }} ... on MutationError {{ message }} }} }}"
)
DELETE = (
    "mutation($input: DeletePostInput!) { deletePost(input: $input) { __typename "
    "... on VoidMutationError { message } } }"
)
POST = f"query($input: PostInput!) {{ post(input: $input) {{ {POST_FIELDS} }} }}"

#: Buffer's statuses, as a share names them. Anything new reads as still
#: waiting in Buffer, which it is.
STATES = {
    "draft": "draft",
    "buffer": "queued",
    "sent": "sent",
    "published": "sent",
    "failed": "failed",
}


class BufferError(Exception):
    """Buffer made nothing. The message says why, and what to do."""


class Unanswered(BufferError):
    """A post's request went out and no answer came back: it may have been made."""


class Refused(BufferError):
    """Buffer answered, and wouldn't do it: a typed error in its answer."""


class TokenRefused(BufferError):
    """Buffer doesn't accept the token."""


class NotFound(BufferError):
    """Buffer has no such post: deleted there, most likely."""


# --- what Buffer holds ----------------------------------------------------------------------


@dataclass(frozen=True)
class Listed:
    """A channel as Buffer lists it."""

    id: str
    name: str
    service: str
    descriptor: str = ""
    avatar: str = ""
    organization_id: str = ""
    disconnected: bool = False
    locked: bool = False
    queue_paused: bool = False

    @classmethod
    def from_buffer(cls, found: dict[str, Any]) -> Listed:
        return cls(
            id=str(found["id"]),
            name=found.get("name") or "",
            service=found.get("service") or "",
            descriptor=found.get("descriptor") or "",
            avatar=found.get("avatar") or "",
            organization_id=found.get("organizationId") or "",
            disconnected=bool(found.get("isDisconnected")),
            locked=bool(found.get("isLocked")),
            queue_paused=bool(found.get("isQueuePaused")),
        )


def label(name: str, descriptor: str) -> str:
    return f"{name} ({descriptor})" if descriptor else name


def network(service: str) -> str:
    """The network as people name it: "X" for Buffer's `twitter`."""
    return NETWORKS.get(service, service.replace("_", " ").title() or "A network")


def problem(*, name: str, descriptor: str, service: str, disconnected: bool, locked: bool) -> str:
    """Why the channel can't take a link post, or "" when it can."""
    called = label(name, descriptor)
    if disconnected:
        return f"{called} isn't connected in Buffer any more. Reconnect it there, then check the channels again."
    if locked:
        return f"{called} is locked in Buffer, which happens when a plan has more channels than it allows."
    if service not in LINK_SERVICES:
        return f"{network(service)} takes no link posts from here: a post there needs a picture or a video of its own."
    return ""


@dataclass(frozen=True)
class PostState:
    id: str
    status: str
    due_at: datetime | None = None
    sent_at: datetime | None = None
    external_link: str | None = None
    error: str = ""

    @classmethod
    def from_buffer(cls, found: dict[str, Any]) -> PostState:
        return cls(
            id=str(found["id"]),
            status=found.get("status") or "",
            due_at=_when(found.get("dueAt")),
            sent_at=_when(found.get("sentAt")),
            external_link=found.get("externalLink") or None,
            error=((found.get("error") or {}).get("message") or ""),
        )

    @property
    def state(self) -> str:
        return STATES.get(self.status, "queued")


@dataclass(frozen=True)
class LinkCard:
    """LinkedIn's preview of the post: Buffer's API doesn't read the page for
    one, so it's sent whole."""

    url: str
    title: str
    description: str
    thumbnail: str | None


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _buffer_time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- a post's text --------------------------------------------------------------------------


def text_for(service: str, text: str, link: str) -> str:
    """The text as the channel gets it: with the link on the end unless the
    network shows it as a card, or the text has it already."""
    if service in CARDS or link in text:
        return text
    return f"{text}\n\n{link}"


def text_problem(*, name: str, descriptor: str, service: str, text: str, link: str) -> str | None:
    """Why the text won't fit the channel, or None. Buffer has the last word;
    this says so before anything is sent."""
    limit = LIMITS.get(service)
    length = len(text_for(service, text, link))
    if limit is None or length <= limit:
        return None
    return (
        f"{label(name, descriptor)} takes {limit:,} characters, and this would be {length:,}, "
        "the link included. Shorten the text."
    )


def token_problem(token: str) -> str | None:
    """Why a pasted value can't be a Buffer token, or None. Never repeats it."""
    if any(character.isspace() for character in token):
        return "A Buffer token has no spaces or line breaks in it. Copy it again from Buffer's API settings."
    if len(token) < MIN_TOKEN_LENGTH:
        return "That's too short to be a Buffer token. Copy the whole token from Buffer's API settings."
    if len(token) > MAX_TOKEN_LENGTH:
        return (
            "That's too long to be a Buffer token. Copy just the token from Buffer's API settings."
        )
    return None


# --- the calls --------------------------------------------------------------------------------


class Client:
    def __init__(self, token: str) -> None:
        self._token = token

    def _safe(self, text: str) -> str:
        return text.replace(self._token, "the token") if self._token else text

    async def _ask(
        self, query: str, variables: dict[str, Any] | None = None, *, posting: bool = False
    ) -> dict[str, Any]:
        """Buffer's `data`, or a BufferError saying what went wrong. With
        `posting`, a request that went out unanswered is Unanswered."""
        lost = Unanswered(MAYBE_SENT) if posting else BufferError(SLOW)
        try:
            async with httpx.AsyncClient(
                transport=_installed.transport, timeout=TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    API,
                    json={"query": query, "variables": variables or {}},
                    headers={"Authorization": f"Bearer {self._token}", "User-Agent": USER_AGENT},
                )
        except (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.PoolTimeout,
            httpx.ProxyError,
            httpx.UnsupportedProtocol,
            httpx.LocalProtocolError,
        ):
            raise BufferError(UNREACHABLE) from None
        except httpx.HTTPError:
            raise lost from None
        if response.status_code == 429:
            raise BufferError(_limited(response.headers.get("Retry-After")))
        if response.status_code >= 500:
            raise lost
        try:
            answer = response.json()
        except ValueError:
            if response.status_code == 200:
                raise lost from None
            raise BufferError(
                f"Buffer answered with an error ({response.status_code}). Try again in a minute."
            ) from None
        if not isinstance(answer, dict):
            raise BufferError(
                f"Buffer answered with an error ({response.status_code}). Try again in a minute."
            )
        errors = answer.get("errors") or []
        if errors:
            code = ((errors[0].get("extensions") or {}).get("code") or "").upper()
            kind = {"UNAUTHORIZED": TokenRefused, "NOT_FOUND": NotFound}.get(code, BufferError)
            raise kind(self._safe(_said(errors[0])))
        if response.status_code != 200 or not isinstance(answer.get("data"), dict):
            raise BufferError(
                f"Buffer answered with an error ({response.status_code}). Try again in a minute."
            )
        data: dict[str, Any] = answer["data"]
        return data

    async def channels(self) -> list[Listed]:
        """Every channel of every organization the token reaches, in Buffer's order."""
        organizations = (await self._ask(ORGANIZATIONS))["account"]["organizations"]
        found: list[Listed] = []
        for organization in organizations:
            data = await self._ask(CHANNELS, {"input": {"organizationId": organization["id"]}})
            found += [Listed.from_buffer(channel) for channel in data["channels"]]
        return found

    async def create_post(
        self,
        *,
        channel_id: str,
        service: str,
        text: str,
        when: str,
        card: LinkCard,
        due_at: datetime | None = None,
    ) -> PostState:
        """One post on one channel: to its queue, now, at `due_at`, or a draft
        in Buffer, which waits there until someone schedules it."""
        sent: dict[str, Any] = {
            "channelId": channel_id,
            "text": text_for(service, text, card.url),
            "schedulingType": "automatic",
            "mode": {
                "queue": "addToQueue",
                "now": "shareNow",
                "at": "customScheduled",
                "draft": "addToQueue",
            }[when],
            "saveToDraft": when == "draft",
            "assets": [],
        }
        if when == "at" and due_at is not None:
            sent["dueAt"] = _buffer_time(due_at)
        if service in CARDS:
            attachment: dict[str, Any] = {
                "url": card.url,
                "title": card.title,
                "description": card.description,
            }
            if card.thumbnail:
                attachment["thumbnail"] = {"url": card.thumbnail}
            sent["metadata"] = {"linkedin": {"linkAttachment": attachment}}
        answer = (await self._ask(CREATE, {"input": sent}, posting=True))["createPost"]
        if answer.get("__typename") != "PostActionSuccess":
            raise Refused(
                self._safe(
                    f"Buffer didn't take it: {answer.get('message') or answer.get('__typename')}"
                )
            )
        return PostState.from_buffer(answer["post"])

    async def delete_post(self, post_id: str) -> None:
        answer = (await self._ask(DELETE, {"input": {"id": post_id}}))["deletePost"]
        if answer.get("__typename") != "DeletePostSuccess":
            raise Refused(
                self._safe(
                    "Buffer didn't take it back: "
                    f"{answer.get('message') or answer.get('__typename')}"
                )
            )

    async def post_state(self, post_id: str) -> PostState:
        return PostState.from_buffer((await self._ask(POST, {"input": {"id": post_id}}))["post"])


def _said(error: dict[str, Any]) -> str:
    code = ((error.get("extensions") or {}).get("code") or "").upper()
    message = error.get("message") or "no reason given"
    if code == "UNAUTHORIZED":
        return REFUSED_TOKEN
    if code == "RATE_LIMIT_EXCEEDED":
        return _limited(None)
    if code == "FORBIDDEN":
        return f"Buffer's token isn't allowed to do that: {message}"
    return f"Buffer answered with an error: {message}"


def _limited(retry_after: str | None) -> str:
    said = (
        "Buffer's limit on requests is reached for now (100 every 15 minutes on the free plan), "
        "so nothing was sent."
    )
    try:
        minutes = max(1, math.ceil(int(retry_after or "") / 60))
    except ValueError:
        return f"{said} Try again in a few minutes."
    return f"{said} Try again in {minutes} minute{'s' if minutes != 1 else ''}."


# --- the post's address -----------------------------------------------------------------------


async def link_problem(url: str) -> str | None:
    """Why a post linking to `url` would lead nowhere, or None when the
    address answers as the thing: a 200 there, with no redirect, naming itself
    as its canonical address. A domain still pointing at an old site answers
    something else."""
    try:
        async with httpx.AsyncClient(
            transport=_installed.transport, timeout=LINK_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError:
        said = "didn't answer"
    else:
        if response.status_code != 200:
            said = f"answered {response.status_code}"
        elif url not in response.text:
            said = "answered, but the page there isn't this one"
        else:
            return None
    return (
        f"Its address, {url}, {said}, so a post would link to nothing. Sharing waits until it "
        "shows the page. A draft in Buffer can be made now."
    )
