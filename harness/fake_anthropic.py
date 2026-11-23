"""A stand-in for Anthropic's API (decision 0058), so no test calls it: the
kernel's unit tests, the contract suite and the end-to-end server all send
`kernel.ai`'s requests through `FakeAnthropic.transport`.

It records every request (`asked`) and answers the queued answers in order
(`queue`). With none queued, a message answers "Words for the test.", or,
when the request asks for structured output, an object its JSON Schema
describes: each string "Words for the test.", each list of strings one of
them. A models list answers one model, as a key's check expects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx2

MODEL = "claude-opus-5-5"
WORDS = "Words for the test."


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


def _filled(schema: dict[str, Any]) -> Any:
    """The smallest answer a JSON Schema allows, with words in it."""
    kind = schema.get("type")
    if kind == "object":
        return {name: _filled(part) for name, part in (schema.get("properties") or {}).items()}
    if kind == "array":
        return [_filled(schema.get("items") or {"type": "string"})]
    return WORDS


def _key_of(request: httpx2.Request) -> str:
    """The key a request was sent with: SDK 2.x sends it as a bearer token,
    1.x in `x-api-key`."""
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[len("bearer ") :]
    return request.headers.get("x-api-key", "")


@dataclass
class Asked:
    """One request the fake was sent."""

    method: str
    path: str
    #: The key it was sent with: the tests check which key was used.
    key: str
    beta: str
    body: dict[str, Any]


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
            )
        )
        if self.queued:
            status, payload = self.queued.pop(0)
            return httpx2.Response(status, json=payload)
        if request.url.path.endswith("/models"):
            model = {
                "id": MODEL,
                "type": "model",
                "display_name": "Claude",
                "created_at": "2026-01-01T00:00:00Z",
            }
            return httpx2.Response(
                200, json={"data": [model], "has_more": False, "first_id": MODEL, "last_id": MODEL}
            )
        shape = ((body.get("output_config") or {}).get("format") or {}).get("schema")
        words = json.dumps(_filled(shape)) if shape else WORDS
        return httpx2.Response(200, json=message(words))

    @property
    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self.handle)


__all__ = ["MODEL", "WORDS", "Asked", "FakeAnthropic", "message"]
