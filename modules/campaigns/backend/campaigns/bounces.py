"""Bounces and spam reports (`dev plans/contracts/campaigns.md` §2, "Bounces by
SMTP", and §8, 5): what a failure means for the address, and the reader of the
bounce mailbox.

**The classifier** is VybeSite's (`services/bounce_classifier.py`), reshaped
from Mailgun's events to the reports a mailbox gets and to Resend's webhook.
The rules, in the order they're applied:

1. **Temporary is a soft bounce.** A delayed message, a 4.x.x code, or a
   provider's "transient": nothing is decided about the address.
2. **A block sets nobody aside.** A refusal because of who sent the message or
   what it says: an x.7.x code (security and policy), 5.1.7 and 5.1.8 (the
   sender's address), a 5.1.x that says it's about the sender, and a receiver
   whose words say blocked, spam, policy or reputation whatever its code.
3. **Only the address sets it aside.** Any other 5.1.x: no such user, no such
   domain, a malformed address.
4. **Anything else is unclear and sets nobody aside:** a full mailbox, a
   disabled one, a routing failure, no code at all.

A block outranks an address code, so a gateway answering "5.1.1 rejected by
policy" to everyone at a company sets none of them aside. Calling a dead
address unclear costs another attempt; calling a block a dead address loses a
person for good, so every doubt falls on the side that sets nobody aside. A
spam report (RFC 5965's `abuse` or `fraud`) is a person's own decision, and
always sets the address aside.

**The reader** logs in to the bounce mailbox over IMAP while its three
variables are set (`CAMPAIGNS_BOUNCE_IMAP_HOST`, `_USERNAME`, `_PASSWORD`; a
host may end in `:port`, 993 by default). It asks the server for messages
whose Content-Type header is `multipart/report`, peeks at each one's
Content-Type (`BODY.PEEK`, which marks nothing read), and opens only a bounce
report (RFC 3464, `report-type=delivery-status`) or a spam report (RFC 5965,
`report-type=feedback-report`), peeking again. Once it's handled, the report
moves to the folder `CAMPAIGNS_BOUNCE_IMAP_FOLDER` ("Newsletter bounces" by
default), so it's read once. Nothing else in the mailbox is opened, flagged or
moved.
"""

from __future__ import annotations

import contextlib
import email as mail
import email.policy
import imaplib
import os
import re
import socket
import ssl
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from email.message import Message
from email.parser import BytesHeaderParser, HeaderParser
from email.utils import getaddresses
from typing import Any, Literal, Protocol

SetAsideWhy = Literal["bounced", "complained"]

HOST = "CAMPAIGNS_BOUNCE_IMAP_HOST"
USERNAME = "CAMPAIGNS_BOUNCE_IMAP_USERNAME"
PASSWORD = "CAMPAIGNS_BOUNCE_IMAP_PASSWORD"  # noqa: S105 (the variable's name, not a password)
FOLDER = "CAMPAIGNS_BOUNCE_IMAP_FOLDER"
DEFAULT_FOLDER = "Newsletter bounces"
PORT = 993
#: How long one call to the mailbox may take.
TIMEOUT = 30.0
#: Reports read in one run; the rest wait for the next.
PER_RUN = 200
#: What's read of a report: its delivery status comes before the message it
#: returns, so the start of it is enough.
READ_BYTES = 256 * 1024
#: The length of a set-aside row's `detail`.
DETAIL_MAX = 300

# An enhanced status code (RFC 3463): class, subject 0-7, detail. Not part of a
# longer dotted number, so an address like 5.1.1.3 or a version like 4.94.2 is
# not read as one.
_STATUS_CODE = re.compile(r"(?<![\d.])([245])\.([0-7])\.(\d{1,3})(?!\.?\d)")

#: The two 5.1.x codes about the sender's address rather than the recipient's.
SENDER_CODES = frozenset({"5.1.7", "5.1.8"})

#: Words a receiver uses when it refuses the sender or the message. Checked
#: whatever the code says, because some gateways put a block behind an address
#: code, and there it must not set anyone aside.
BLOCK_WORDS = (
    "blocklist",
    "block list",
    "blocked",
    "blacklist",
    "denylist",
    "spamhaus",
    "spamcop",
    "reputation",
    "spam",
    "policy",
    "dmarc",
    "banned",
)

#: RFC 5965's feedback types that are a person's complaint.
COMPLAINTS = frozenset({"abuse", "fraud"})


@dataclass(frozen=True)
class Verdict:
    """One failure's verdict: whether the address is set aside, and why."""

    set_aside: SetAsideWhy | None
    #: Kept as the set-aside row's detail: "address: 5.1.1", "blocked: 5.7.1".
    why: str


def status_code_of(*texts: str) -> str:
    """The first enhanced status code in `texts`, or "" when there is none."""
    for text in texts:
        match = _STATUS_CODE.search(text or "")
        if match:
            return match.group(0)
    return ""


def classify(*, permanent: bool, code: str, words: str) -> Verdict:
    """The verdict on one failure: `permanent` as the report or the provider
    says, its status code, and the receiver's words."""
    words = " ".join(words.split()).lower()
    detail = code or "no status code"
    if not permanent or code.startswith("4."):
        return Verdict(None, f"temporary: {detail}"[:DETAIL_MAX])
    if code and code.split(".")[1] == "7":
        return Verdict(None, f"blocked: {code}")
    if code in SENDER_CODES or (code.startswith("5.1.") and "sender" in words):
        return Verdict(None, f"blocked: {code}, the sender's address")
    word = next((each for each in BLOCK_WORDS if each in words), None)
    if word is not None:
        return Verdict(None, f"blocked: {code or 'no code'}, '{word}'"[:DETAIL_MAX])
    if code.startswith("5.1."):
        return Verdict("bounced", f"address: {code}")
    return Verdict(None, f"unclear: {detail}"[:DETAIL_MAX])


def complaint(feedback_type: str) -> Verdict:
    kind = feedback_type.strip().lower() or "unknown"
    if kind in COMPLAINTS:
        return Verdict("complained", f"spam report: {kind}")
    return Verdict(None, f"feedback: {kind}"[:DETAIL_MAX])


# --- reading a report --------------------------------------------------------------------


def _address(field: str) -> str | None:
    """The address in a recipient field: `rfc822; user@example.com`."""
    kind, semi, rest = (field or "").partition(";")
    value = rest if semi else kind
    found = [address for _, address in getaddresses([value.strip()]) if "@" in address]
    return found[0].strip() if len(found) == 1 else None


def _report_type(message: Message) -> str:
    if message.get_content_type() != "multipart/report":
        return ""
    return str(message.get_param("report-type", "") or "").strip().lower()


def _fields(part: Message) -> list[Message]:
    """A report part's header blocks: Python parses message/delivery-status as
    a list of them, and other message/* parts as one message."""
    payload = part.get_payload()
    if isinstance(payload, list):
        return [each for each in payload if isinstance(each, Message)]
    if isinstance(payload, str):
        blocks = re.split(r"\r?\n\s*\r?\n", payload.strip())
        parser = HeaderParser(policy=mail.policy.compat32)
        return [parser.parsestr(block) for block in blocks if block.strip()]
    return []


def _delivery_status(message: Message) -> list[tuple[str, Verdict]]:
    for part in message.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        found = []
        # The first block is about the message; each after it is a recipient.
        for block in _fields(part)[1:]:
            address = _address(str(block.get("Final-Recipient") or "")) or _address(
                str(block.get("Original-Recipient") or "")
            )
            if address is None:
                continue
            action = str(block.get("Action") or "").strip().lower()
            if action not in ("failed", "delayed"):
                continue  # delivered, relayed or expanded: not a failure
            diagnostic = str(block.get("Diagnostic-Code") or "")
            code = status_code_of(str(block.get("Status") or ""), diagnostic)
            found.append(
                (address, classify(permanent=action == "failed", code=code, words=diagnostic))
            )
        return found
    return []


def _original_recipient(message: Message) -> str | None:
    for part in message.walk():
        kind = part.get_content_type()
        if kind == "message/rfc822":
            inner = part.get_payload()
            if isinstance(inner, list) and inner and isinstance(inner[0], Message):
                return _address(str(inner[0].get("To") or ""))
        elif kind == "text/rfc822-headers":
            text = part.get_payload(decode=True)
            if isinstance(text, bytes):
                headers = BytesHeaderParser(policy=mail.policy.compat32).parsebytes(text)
                return _address(str(headers.get("To") or ""))
    return None


def _feedback(message: Message) -> list[tuple[str, Verdict]]:
    for part in message.walk():
        if part.get_content_type() != "message/feedback-report":
            continue
        blocks = _fields(part)
        if not blocks:
            return []
        fields = blocks[0]
        verdict = complaint(str(fields.get("Feedback-Type") or ""))
        addresses = [
            address
            for address in (_address(str(each)) for each in fields.get_all("Original-Rcpt-To", []))
            if address
        ]
        if not addresses:
            original = _original_recipient(message)
            addresses = [original] if original else []
        return [(address, verdict) for address in addresses]
    return []


def read_report(raw: bytes) -> list[tuple[str, Verdict]] | None:
    """Each address a report names and its verdict; None for a message that
    isn't a bounce or spam report."""
    message = mail.message_from_bytes(raw, policy=mail.policy.compat32)
    kind = _report_type(message)
    if kind == "delivery-status":
        return _delivery_status(message)
    if kind == "feedback-report":
        return _feedback(message)
    return None


def is_report(content_type: str) -> bool:
    """Whether a Content-Type header is a bounce or a spam report's."""
    parsed = mail.message_from_string(
        f"Content-Type: {content_type}\n\n", policy=mail.policy.compat32
    )
    return _report_type(parsed) in ("delivery-status", "feedback-report")


# --- the mailbox -------------------------------------------------------------------------


@dataclass(frozen=True)
class Login:
    host: str
    port: int
    username: str
    password: str
    folder: str


def login_from(environ: Mapping[str, str] | None = None) -> Login | None:
    """The bounce mailbox's login from its variables, or None while any of the three is unset."""
    environ = os.environ if environ is None else environ
    host = (environ.get(HOST) or "").strip()
    username = (environ.get(USERNAME) or "").strip()
    password = environ.get(PASSWORD) or ""
    if not (host and username and password):
        return None
    name, colon, port = host.rpartition(":")
    number = int(port) if colon and port.isdigit() else PORT
    folder = (environ.get(FOLDER) or "").strip() or DEFAULT_FOLDER
    return Login(name if colon and port.isdigit() else host, number, username, password, folder)


class Mailbox(Protocol):
    """The bounce mailbox, as the job reads it. Every call may block: the job
    runs them in a thread."""

    def reports(self, limit: int = PER_RUN) -> list[tuple[str, bytes]]:
        """The reports waiting, each its id and its start, opened without marking it read."""
        ...

    def done(self, uid: str) -> None:
        """Moves a handled report to the folder of read ones."""
        ...

    def close(self) -> None: ...


#: The errors a mailbox can't be reached or read through.
UNREACHABLE: tuple[type[BaseException], ...] = (
    OSError,
    ssl.SSLError,
    socket.timeout,
    imaplib.IMAP4.error,
    imaplib.IMAP4.abort,
)


def _quoted(name: str) -> str:
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ok(answer: tuple[str, Any], what: str) -> Any:
    kind, data = answer
    if kind != "OK":
        raise imaplib.IMAP4.error(f"The mailbox refused {what}.")
    return data


class ImapMailbox:
    """The bounce mailbox over IMAP (imaplib), opened for reading and moving."""

    def __init__(
        self,
        login: Login,
        *,
        connect: Callable[..., Any] = imaplib.IMAP4_SSL,
        timeout: float = TIMEOUT,
    ) -> None:
        self.folder = login.folder
        self.imap = connect(login.host, login.port, timeout=timeout)
        try:
            _ok(self.imap.login(login.username, login.password), "the login")
            _ok(self.imap.select("INBOX"), "the inbox")
        except BaseException:
            self.close()
            raise
        self.capabilities = {str(each).upper() for each in getattr(self.imap, "capabilities", ())}
        self._folder_made = False

    def reports(self, limit: int = PER_RUN) -> list[tuple[str, bytes]]:
        data = _ok(
            self.imap.uid(
                "SEARCH", None, "NOT", "DELETED", "HEADER", "Content-Type", '"multipart/report"'
            ),
            "the search",
        )
        uids = [uid.decode() for uid in (data[0] or b"").split()][:limit]
        found = []
        for uid in uids:
            header = self._peek(uid, "BODY.PEEK[HEADER.FIELDS (CONTENT-TYPE)]")
            text = header.decode("utf-8", "replace") if header else ""
            value = mail.message_from_string(text, policy=mail.policy.compat32).get(
                "Content-Type", ""
            )
            if not is_report(str(value)):
                continue
            body = self._peek(uid, f"BODY.PEEK[]<0.{READ_BYTES}>")
            if body:
                found.append((uid, body))
        return found

    def _peek(self, uid: str, item: str) -> bytes | None:
        data = _ok(self.imap.uid("FETCH", uid, f"({item})"), "a fetch")
        for each in data or ():
            if isinstance(each, tuple) and len(each) >= 2 and isinstance(each[1], bytes):
                return each[1]
        return None

    def done(self, uid: str) -> None:
        folder = _quoted(self.folder)
        if not self._folder_made:
            # Made once; a server answers NO when it's there already.
            self.imap.create(folder)
            self._folder_made = True
        if "MOVE" in self.capabilities:
            _ok(self.imap.uid("MOVE", uid, folder), "the move")
            return
        _ok(self.imap.uid("COPY", uid, folder), "the copy")
        _ok(self.imap.uid("STORE", uid, "+FLAGS.SILENT", "(\\Deleted)"), "the flag")
        if "UIDPLUS" in self.capabilities:
            # Only this message: a plain EXPUNGE would take others marked deleted too.
            _ok(self.imap.uid("EXPUNGE", uid), "the expunge")

    def close(self) -> None:
        with contextlib.suppress(*UNREACHABLE):
            self.imap.logout()


def open_mailbox(login: Login) -> Mailbox:
    return ImapMailbox(login)


def handled(reports: Iterable[tuple[str, bytes]]) -> list[tuple[str, list[tuple[str, Verdict]]]]:
    """Each report's id and the addresses it names, a message that isn't a report left out."""
    found = []
    for uid, raw in reports:
        verdicts = read_report(raw)
        if verdicts is not None:
            found.append((uid, verdicts))
    return found
