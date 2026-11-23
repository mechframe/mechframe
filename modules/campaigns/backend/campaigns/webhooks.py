"""Resend's webhook (`dev plans/contracts/campaigns.md` §2): only for a site
that sends by Resend because its host blocks SMTP (decision 0033). Its
bounces and complaints set addresses aside, as the bounce mailbox's do.

Resend signs each delivery the Svix way: `svix-id`, `svix-timestamp` and
`svix-signature` (`v1,<base64>`, space-separated, one per key in rotation),
an HMAC-SHA256 of `<id>.<timestamp>.<body>` keyed with the secret's base64
after `whsec_`. The check comes first and fails closed: without
`CAMPAIGNS_RESEND_WEBHOOK_SECRET`, or with a time more than 5 minutes off,
nothing is read. A delivery id seen before is a replay, refused.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from campaigns import bounces

SECRET = "CAMPAIGNS_RESEND_WEBHOOK_SECRET"  # noqa: S105 (the variable's name)
#: How far a delivery's time may be from now.
TOLERANCE = 300
_STAMP = re.compile(r"[0-9]{1,12}")


def secret_from(environ: Mapping[str, str] | None = None) -> bytes | None:
    """The signing key, or None while it's unset or isn't one."""
    value = ((os.environ if environ is None else environ).get(SECRET) or "").strip()
    if not value:
        return None
    try:
        return base64.b64decode(value.removeprefix("whsec_"), validate=True)
    except (binascii.Error, ValueError):
        return None


def signed(secret: bytes, delivery_id: str, timestamp: str, body: bytes) -> str:
    """The `v1,` signature Svix sends for this delivery."""
    content = f"{delivery_id}.{timestamp}.".encode() + body
    digest = hmac.new(secret, content, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def verified(
    secret: bytes | None, headers: Mapping[str, str], body: bytes, now: datetime
) -> str | None:
    """The delivery's id when its signature is good and its time is near; else None."""
    if secret is None:
        return None
    delivery_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    given = headers.get("svix-signature", "")
    # ASCII digits, a few: "²" or a thousand digits would raise rather than
    # refuse, and so would a signature beyond ASCII (CodeRabbit on #134).
    if not (delivery_id and _STAMP.fullmatch(timestamp) and given):
        return None
    if abs(now.timestamp() - int(timestamp)) > TOLERANCE:
        return None
    expected = signed(secret, delivery_id, timestamp, body).encode()
    if not any(hmac.compare_digest(expected, each.encode()) for each in given.split()):
        return None
    return delivery_id


def _recipients(data: Mapping[str, Any]) -> list[str]:
    to = data.get("to")
    found = to if isinstance(to, list) else [to]
    return [each.strip() for each in found if isinstance(each, str) and "@" in each]


def verdicts(event: Mapping[str, Any]) -> list[tuple[str, bounces.Verdict]]:
    """What a Resend event says of its recipients: a bounce through the
    classifier, a complaint set aside; any other event, nothing."""
    kind = event.get("type")
    data = event.get("data")
    if not isinstance(data, Mapping):
        return []
    if kind == "email.complained":
        return [(address, bounces.complaint("abuse")) for address in _recipients(data)]
    if kind != "email.bounced":
        return []
    bounce = data.get("bounce")
    bounce = bounce if isinstance(bounce, Mapping) else {}
    kind_of = str(bounce.get("type") or "").strip().lower()
    sub = str(bounce.get("subType") or "").strip().lower()
    words = str(bounce.get("message") or "")
    # No code is no verdict on the address: a General bounce can be a policy
    # block, and NoEmail says only that the address couldn't be read back
    # (CodeRabbit on #134). Every doubt sets nobody aside.
    code = bounces.status_code_of(words)
    if sub in ("suppressed", "onaccountsuppressionlist"):
        # A repeat of the provider's own list, not a new failure: nothing decided.
        return [
            (address, bounces.Verdict(None, f"the provider's list: {sub}"))
            for address in _recipients(data)
        ]
    verdict = bounces.classify(permanent=kind_of == "permanent", code=code, words=words)
    return [(address, verdict) for address in _recipients(data)]


def parsed(body: bytes) -> Mapping[str, Any]:
    try:
        event = json.loads(body)
    except (UnicodeDecodeError, ValueError):
        return {}
    return event if isinstance(event, Mapping) else {}
