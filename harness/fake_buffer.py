"""A stand-in for Buffer's API (decision 0067), so no test calls it: social's
unit tests, the contract suite and the end-to-end server all send social's
requests through `FakeBuffer.transport`.

Buffer is GraphQL at one address. The fake answers the five operations social
sends, by the words in the query: the account's organizations, an
organization's channels (`CHANNELS`, one of each kind social meets), a post
made (queued, a draft, or sent at once with its address on the network),
taken back, and read again. `posts` holds what was made, so a test can move a
post on (`posts[id]["status"] = "sent"`). A request with `REFUSED_TOKEN` is
refused as Buffer refuses a token it doesn't know.

`trouble` makes the next post's request go wrong, one way a call: `refuse`
(Buffer's typed error), `lose` (no answer after the request went), `limit` (a
429 with Retry-After) or `fault` (a 500). Any request to another host is a
link check of the site's own address: it answers 200 with a page naming the
address, unless the address is in `down`.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx

API_HOST = "api.buffer.com"
#: A token Buffer doesn't accept.
REFUSED_TOKEN = (
    "refused-buffer-token-for-the-tests-0001"  # noqa: S105 - a made-up token the fake refuses
)

#: The channels a token reaches: one organization's, in Buffer's order.
CHANNELS: tuple[dict[str, Any], ...] = (
    {"id": "ch-linkedin", "name": "Test Site", "service": "linkedin", "descriptor": "Page"},
    {"id": "ch-x", "name": "@testsite", "service": "twitter", "descriptor": "Profile"},
    {"id": "ch-bluesky", "name": "testsite.bsky.social", "service": "bluesky", "descriptor": ""},
    {"id": "ch-instagram", "name": "testsite", "service": "instagram", "descriptor": "Business"},
    {
        "id": "ch-gone",
        "name": "Old page",
        "service": "facebook",
        "descriptor": "Page",
        "isDisconnected": True,
    },
)


@dataclass
class Asked:
    """One request: its operation's first word after the brace, its variables, and the token."""

    operation: str
    variables: dict[str, Any]
    token: str


@dataclass
class FakeBuffer:
    asked: list[Asked] = field(default_factory=list)
    posts: dict[str, dict[str, Any]] = field(default_factory=dict)
    channels: list[dict[str, Any]] = field(default_factory=lambda: [dict(one) for one in CHANNELS])
    trouble: deque[str] = field(default_factory=deque)
    down: set[str] = field(default_factory=set)
    checked: list[str] = field(default_factory=list)
    #: The posts made so far, deleted ones included: each new one's id is the next,
    #: never one a deleted post freed (CodeRabbit on #152).
    numbered: int = 0

    def forget(self) -> None:
        """As new: nothing asked or made, the usual channels, no trouble."""
        self.asked.clear()
        self.posts.clear()
        self.channels = [dict(one) for one in CHANNELS]
        self.trouble.clear()
        self.down.clear()
        self.checked.clear()
        self.numbered = 0

    def made(self) -> list[dict[str, Any]]:
        """The posts made, oldest first, each with the input Buffer was sent."""
        return list(self.posts.values())

    # --- answering ------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != API_HOST:
            address = str(request.url)
            self.checked.append(address)
            if address in self.down:
                return httpx.Response(404, text="<html><body>Not here</body></html>")
            return httpx.Response(
                200, text=f'<html><head><link rel="canonical" href="{address}" /></head></html>'
            )
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        sent = json.loads(request.content or b"{}")
        query: str = sent.get("query", "")
        variables: dict[str, Any] = sent.get("variables") or {}
        operation = _operation(query)
        self.asked.append(Asked(operation, variables, token))
        if token == REFUSED_TOKEN:
            return _errors("Unauthorized", "UNAUTHORIZED")
        if operation == "createPost":
            return self._create(variables["input"], request)
        if operation == "account":
            return _data({"account": {"organizations": [{"id": "org-1", "name": "Test Site"}]}})
        if operation == "channels":
            return _data({"channels": [_channel(one) for one in self.channels]})
        if operation == "deletePost":
            post_id = variables["input"]["id"]
            if self.posts.pop(post_id, None) is None:
                return _errors("Post not found", "NOT_FOUND")
            return _data({"deletePost": {"__typename": "DeletePostSuccess"}})
        if operation == "post":
            post = self.posts.get(variables["input"]["id"])
            if post is None:
                return _errors("Post not found", "NOT_FOUND")
            return _data({"post": _post(post)})
        return _errors(f"The fake doesn't know {operation}.", "BAD_REQUEST")

    def _create(self, given: dict[str, Any], request: httpx.Request) -> httpx.Response:
        if self.trouble:
            kind = self.trouble.popleft()
            if kind == "refuse":
                return _data(
                    {
                        "createPost": {
                            "__typename": "InvalidInputError",
                            "message": "The text is too long.",
                        }
                    }
                )
            if kind == "lose":
                raise httpx.ReadTimeout("no answer", request=request)
            if kind == "limit":
                return httpx.Response(429, headers={"Retry-After": "120"}, json={"errors": []})
            if kind == "fault":
                return httpx.Response(500, text="Internal error")
        self.numbered += 1
        post_id = f"post-{self.numbered}"
        mode = given.get("mode")
        status = "draft" if given.get("saveToDraft") else "sent" if mode == "shareNow" else "buffer"
        post = {
            "id": post_id,
            "status": status,
            "dueAt": given.get("dueAt") or ("2026-11-25T15:00:00Z" if status == "buffer" else None),
            "sentAt": "2026-11-24T12:00:00Z" if status == "sent" else None,
            "externalLink": f"https://network.test/{post_id}" if status == "sent" else None,
            "error": None,
            "input": given,
        }
        self.posts[post_id] = post
        return _data({"createPost": {"__typename": "PostActionSuccess", "post": _post(post)}})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def _operation(query: str) -> str:
    """The first field asked for: `account`, `channels`, `createPost`, `deletePost` or `post`."""
    body = query.split("{", 1)[1] if "{" in query else query
    return body.strip().split("(", 1)[0].split("{", 1)[0].split()[0] if body.strip() else ""


def _channel(found: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": found["id"],
        "name": found["name"],
        "service": found["service"],
        "descriptor": found.get("descriptor", ""),
        "avatar": "",
        "organizationId": "org-1",
        "isDisconnected": bool(found.get("isDisconnected")),
        "isLocked": bool(found.get("isLocked")),
        "isQueuePaused": bool(found.get("isQueuePaused")),
    }


def _post(post: dict[str, Any]) -> dict[str, Any]:
    return {key: post[key] for key in ("id", "status", "dueAt", "sentAt", "externalLink", "error")}


def _data(data: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"data": data})


def _errors(message: str, code: str) -> httpx.Response:
    return httpx.Response(
        200, json={"errors": [{"message": message, "extensions": {"code": code}}]}
    )
