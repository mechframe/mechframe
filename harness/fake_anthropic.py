"""A stand-in for Anthropic's API (decision 0058), so no test calls it: the
kernel's unit tests, the contract suite and the end-to-end server all send
`kernel.ai`'s requests through `FakeAnthropic.transport`.

It records every request (`asked`) and answers the queued answers in order
(`queue`). With none queued, a message answers "Words for the test.", or,
when the request asks for structured output, an object its JSON Schema
describes: each string "Words for the test.", but a string named `svg`, which
is `COVER`, a small drawing the kernel's SVG cleaner keeps (blog's generated
covers, decision 0065); each list of strings one of them. A models list answers what a real key sees (`MODELS`, newest first),
two to a page, honouring `limit` and `after_id`: a key's check (`limit=1`)
gets one, and the AI's model list (decision 0064) reads every page.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx2

MODEL = "claude-opus-5-5"
WORDS = "Words for the test."
#: A structured answer's `svg`: a small drawing at the blog card's shape that
#: `kernel.svg.clean` keeps, so a cover is drawn end to end in every suite.
COVER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">'
    "<title>A test cover</title>"
    '<rect width="1200" height="630" fill="#101828"/>'
    '<circle cx="840" cy="315" r="160" fill="#c93a0c"/>'
    '<text x="80" y="420" font-size="96" font-weight="700" fill="#f9fafb">Test</text>'
    "</svg>"
)

#: The models list, newest first, as Anthropic answers it: an older Opus and a
#: kind the dropdown doesn't offer among them.
MODELS = (
    ("claude-opus-5-5", "Claude Opus 5.5", "2026-09-01T00:00:00Z"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5", "2026-09-01T00:00:00Z"),
    ("claude-haiku-5-5", "Claude Haiku 5.5", "2026-08-15T00:00:00Z"),
    ("claude-fable-5-1", "Claude Fable 5.1", "2026-06-01T00:00:00Z"),
    ("claude-opus-5", "Claude Opus 5", "2026-03-01T00:00:00Z"),
)
#: The most a page holds, so a list of five takes three.
PAGE = 2


def message(words: str, *, stop_reason: str = "end_turn") -> dict[str, Any]:
    """A Messages API answer holding `words`."""
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": [{"type": "text", "text": words}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def _filled(schema: dict[str, Any], name: str = "") -> Any:
    """The smallest answer a JSON Schema allows, with words in it, and a
    drawing in a string named `svg`."""
    kind = schema.get("type")
    if kind == "object":
        return {
            each: _filled(part, each) for each, part in (schema.get("properties") or {}).items()
        }
    if kind == "array":
        return [_filled(schema.get("items") or {"type": "string"})]
    return COVER if name == "svg" else WORDS


def _key_of(request: httpx2.Request) -> str:
    """The key a request was sent with: SDK 2.x sends it as a bearer token,
    1.x in `x-api-key`."""
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[len("bearer ") :]
    return request.headers.get("x-api-key", "")


def _page(params: Any) -> dict[str, Any]:
    """One page of `MODELS`, after `after_id`, at most `limit` and `PAGE`."""
    ids = [model_id for model_id, _, _ in MODELS]
    after = params.get("after_id")
    start = ids.index(after) + 1 if after in ids else 0
    size = min(int(params.get("limit") or 20), PAGE)
    shown = MODELS[start : start + size]
    data = [
        {"id": model_id, "type": "model", "display_name": name, "created_at": created}
        for model_id, name, created in shown
    ]
    return {
        "data": data,
        "has_more": start + size < len(MODELS),
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
    }


@dataclass
class Asked:
    """One request the fake was sent."""

    method: str
    path: str
    #: The key it was sent with: the tests check which key was used.
    key: str
    beta: str
    body: dict[str, Any]
    #: The query string's values: a models list's `limit` and `after_id`.
    query: dict[str, str] = field(default_factory=dict)


@dataclass
class FakeAnthropic:
    asked: list[Asked] = field(default_factory=list)
    #: `(status, json)` answers, taken first in, first out.
    queued: list[tuple[int, dict[str, Any]]] = field(default_factory=list)

    def queue(
        self,
        words: str | None = None,
        *,
        answer: Any = None,
        status: int = 200,
        stop_reason: str = "end_turn",
    ) -> None:
        """The next answer: `words` as a message's text, or `answer` (an
        object) as its JSON text, or an error `status`."""
        if status != 200:
            payload: dict[str, Any] = {
                "type": "error",
                "error": {"type": "api_error", "message": "The fake's refusal."},
            }
        else:
            text = (
                json.dumps(answer)
                if answer is not None
                else (words if words is not None else WORDS)
            )
            payload = message(text, stop_reason=stop_reason)
        self.queued.append((status, payload))

    def forget(self) -> None:
        self.asked.clear()
        self.queued.clear()

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        body: dict[str, Any] = json.loads(request.content) if request.content else {}
        self.asked.append(
            Asked(
                method=request.method,
                path=request.url.path,
                key=_key_of(request),
                beta=request.headers.get("anthropic-beta", ""),
                body=body,
                query=dict(request.url.params),
            )
        )
        if self.queued:
            status, payload = self.queued.pop(0)
            return httpx2.Response(status, json=payload)
        if request.url.path.endswith("/models"):
            return httpx2.Response(200, json=_page(request.url.params))
        shape = ((body.get("output_config") or {}).get("format") or {}).get("schema")
        words = json.dumps(_filled(shape)) if shape else WORDS
        return httpx2.Response(200, json=message(words))

    @property
    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handle)


__all__ = ["COVER", "MODEL", "MODELS", "WORDS", "Asked", "FakeAnthropic", "message"]
