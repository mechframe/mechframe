"""The bounce classifier and the bounce mailbox's reader (`bounces.py`;
`dev plans/contracts/campaigns.md` §2 and §7): each of the classifier's cases
from reports shaped as mail servers send them, the reader against a fake
IMAP server that records every command, and a run of the job against a fake
mailbox: read once, nothing without its variables, and a mailbox that can't
be reached leaving the rest alone."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from campaigns import bounces
from campaigns.jobs import read_mailbox
from campaigns.models import SetAside, Subscriber
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kernel import Database, clock, crypto

LOGIN = bounces.Login("mail.site.test", 993, "news@site.test", "pw", "Newsletter bounces")


def dsn(
    recipient: str,
    *,
    action: str = "failed",
    status: str = "5.1.1",
    diagnostic: str = "smtp; 550 5.1.1 <{r}>: Recipient address rejected: User unknown",
    token: str | None = None,
) -> bytes:
    """A bounce report as Postfix sends one (RFC 3464), returning the headers of
    the copy it's about: with `token`, that copy's List-Unsubscribe."""
    return (
        "From: MAILER-DAEMON@mail.example.net\r\n"
        "To: news@site.test\r\n"
        "Subject: Undelivered Mail Returned to Sender\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/report; report-type=delivery-status; boundary="B0UND"\r\n'
        "\r\n"
        "--B0UND\r\n"
        "Content-Type: text/plain; charset=us-ascii\r\n"
        "\r\n"
        "This is the mail system at host mail.example.net.\r\n"
        "\r\n"
        "--B0UND\r\n"
        "Content-Type: message/delivery-status\r\n"
        "\r\n"
        "Reporting-MTA: dns; mail.example.net\r\n"
        "Arrival-Date: Mon, 23 Nov 2026 10:00:00 +0000\r\n"
        "\r\n"
        f"Final-Recipient: rfc822; {recipient}\r\n"
        f"Original-Recipient: rfc822;{recipient}\r\n"
        f"Action: {action}\r\n"
        f"Status: {status}\r\n"
        "Remote-MTA: dns; mx.example.org\r\n"
        f"Diagnostic-Code: {diagnostic.format(r=recipient)}\r\n"
        "\r\n"
        "--B0UND\r\n"
        "Content-Type: text/rfc822-headers\r\n"
        "\r\n"
        "From: Test Site <news@site.test>\r\n"
        f"To: {recipient}\r\n"
        "Subject: Winter shows\r\n"
        f"{unsubscribe(token)}"
        "\r\n"
        "--B0UND--\r\n"
    ).encode()


def unsubscribe(token: str | None) -> str:
    """The returned copy's one-click header, folded as a mail server may fold it."""
    if token is None:
        return ""
    return (
        "List-Unsubscribe:\r\n"
        f" <https://site.test/api/campaigns/unsubscribe?token={token}>\r\n"
        "List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n"
    )


def arf(
    recipient: str | None,
    *,
    feedback: str = "abuse",
    to: str | None = None,
    token: str | None = None,
) -> bytes:
    """A spam report as a feedback loop sends one (RFC 5965)."""
    rcpt = f"Original-Rcpt-To: <{recipient}>\r\n" if recipient else ""
    return (
        "From: feedback@mail.example.org\r\n"
        "To: news@site.test\r\n"
        "Subject: Abuse report\r\n"
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/report; report-type=feedback-report; boundary="ARF"\r\n'
        "\r\n"
        "--ARF\r\n"
        "Content-Type: text/plain\r\n"
        "\r\n"
        "This is an email abuse report.\r\n"
        "\r\n"
        "--ARF\r\n"
        "Content-Type: message/feedback-report\r\n"
        "\r\n"
        f"Feedback-Type: {feedback}\r\n"
        "User-Agent: SomeGenerator/1.0\r\n"
        "Version: 1\r\n"
        "Original-Mail-From: <news@site.test>\r\n"
        f"{rcpt}"
        "\r\n"
        "--ARF\r\n"
        "Content-Type: message/rfc822\r\n"
        "\r\n"
        "From: news@site.test\r\n"
        f"To: {to or recipient or 'redacted'}\r\n"
        "Subject: Winter shows\r\n"
        f"{unsubscribe(token)}"
        "\r\n"
        "The words.\r\n"
        "--ARF--\r\n"
    ).encode()


PLAIN = (
    b"From: rae@example.org\r\nTo: news@site.test\r\nSubject: Hello\r\n"
    b"Content-Type: text/plain\r\n\r\nNot a report.\r\n"
)


# --- the classifier -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("permanent", "code", "words", "set_aside", "why"),
    [
        (True, "5.1.1", "User unknown", "bounced", "address: 5.1.1"),
        (True, "5.1.2", "Domain not found", "bounced", "address: 5.1.2"),
        (False, "4.4.7", "Delivery time expired", None, "temporary: 4.4.7"),
        (True, "4.2.2", "Mailbox full, try later", None, "temporary: 4.2.2"),
        (True, "5.7.1", "Message rejected", None, "blocked: 5.7.1"),
        (True, "5.1.8", "Bad sender's address", None, "blocked: 5.1.8, the sender's address"),
        (True, "5.1.0", "Sender address rejected", None, "blocked: 5.1.0, the sender's address"),
        (True, "5.1.1", "rejected by policy", None, "blocked: 5.1.1, 'policy'"),
        (True, "5.1.1", "listed on Spamhaus", None, "blocked: 5.1.1, 'spamhaus'"),
        (True, "5.2.2", "Mailbox full", None, "unclear: 5.2.2"),
        (True, "5.5.0", "Requested action not taken: mailbox unavailable", None, "unclear: 5.5.0"),
        (True, "", "Something went wrong", None, "unclear: no status code"),
    ],
)
def test_each_of_the_classifier_s_cases(
    permanent: bool, code: str, words: str, set_aside: str | None, why: str
) -> None:
    assert bounces.classify(permanent=permanent, code=code, words=words) == bounces.Verdict(
        set_aside,  # type: ignore[arg-type]
        why,
    )


def test_a_status_code_is_never_read_from_a_longer_number() -> None:
    assert bounces.status_code_of("Postfix 4.94.2 and 5.1.1.3 then 550 5.1.1 user") == "5.1.1"
    assert bounces.status_code_of("no code here", "") == ""


def test_a_spam_report_is_a_complaint_and_not_spam_is_not() -> None:
    assert bounces.complaint("abuse").set_aside == "complained"
    assert bounces.complaint("Fraud").set_aside == "complained"
    assert bounces.complaint("not-spam").set_aside is None


# --- reading a report ------------------------------------------------------------------


def test_a_bounce_for_a_dead_address_sets_it_aside() -> None:
    assert bounces.read_report(dsn("gone@example.org")) == [
        ("gone@example.org", bounces.Verdict("bounced", "address: 5.1.1"))
    ]


def test_a_policy_block_a_delay_and_a_full_mailbox_set_nobody_aside() -> None:
    blocked = dsn(
        "fan@example.org",
        status="5.7.1",
        diagnostic="smtp; 550-5.7.1 [203.0.113.9] Our system has detected that this message is likely unsolicited mail",
    )
    delayed = dsn("fan@example.org", action="delayed", status="4.4.7", diagnostic="")
    full = dsn("fan@example.org", status="5.2.2", diagnostic="smtp; 552 5.2.2 Mailbox full")
    for raw in (blocked, delayed, full):
        [(address, verdict)] = bounces.read_report(raw) or []
        assert address == "fan@example.org"
        assert verdict.set_aside is None, verdict


def test_a_report_of_a_delivery_that_went_through_names_nobody() -> None:
    assert bounces.read_report(dsn("fan@example.org", action="delivered", status="2.0.0")) == []


def test_a_spam_report_names_its_recipient() -> None:
    assert bounces.read_report(arf("fan@example.org")) == [
        ("fan@example.org", bounces.Verdict("complained", "spam report: abuse"))
    ]


def test_a_spam_report_without_original_rcpt_to_reads_the_returned_message_s_to() -> None:
    assert bounces.read_report(arf(None, to="fan@example.org")) == [
        ("fan@example.org", bounces.Verdict("complained", "spam report: abuse"))
    ]


def test_a_message_that_isn_t_a_report_is_none() -> None:
    assert bounces.read_report(PLAIN) is None
    assert bounces.is_report("multipart/report; report-type=delivery-status") is True
    assert bounces.is_report('multipart/report; report-type="feedback-report"') is True
    assert bounces.is_report("multipart/report; report-type=disposition-notification") is False
    assert bounces.is_report("text/plain") is False


def test_the_login_needs_all_three_variables() -> None:
    whole = {
        bounces.HOST: "mail.site.test:1993",
        bounces.USERNAME: "news@site.test",
        bounces.PASSWORD: "secret words",
    }
    assert bounces.login_from(whole) == bounces.Login(
        "mail.site.test", 1993, "news@site.test", "secret words", "Newsletter bounces"
    )
    assert bounces.login_from({**whole, bounces.HOST: "mail.site.test"}) == bounces.Login(
        "mail.site.test", 993, "news@site.test", "secret words", "Newsletter bounces"
    )
    assert bounces.login_from({**whole, bounces.FOLDER: "INBOX.Read"}).folder == "INBOX.Read"  # type: ignore[union-attr]
    for name in (bounces.HOST, bounces.USERNAME, bounces.PASSWORD):
        assert bounces.login_from({**whole, name: ""}) is None


# --- the IMAP reader -------------------------------------------------------------------


class FakeImap:
    """An IMAP server's answers as imaplib gives them, recording each command."""

    def __init__(self, messages: dict[str, bytes], capabilities: tuple[str, ...]) -> None:
        self.inbox = dict(messages)
        self.moved: dict[str, list[str]] = {}
        self.flags: dict[str, set[str]] = {uid: set() for uid in messages}
        self.capabilities = capabilities
        self.calls: list[tuple[str, ...]] = []
        self.made: list[str] = []
        self.out = False

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        return "OK", [b"Logged in"]

    def select(self, box: str) -> tuple[str, list[bytes]]:
        self.calls.append(("SELECT", box))
        return "OK", [str(len(self.inbox)).encode()]

    def create(self, name: str) -> tuple[str, list[bytes]]:
        self.made.append(name)
        return "OK", [b"Created"]

    def logout(self) -> tuple[str, list[bytes]]:
        self.out = True
        return "BYE", [b""]

    def _header(self, uid: str) -> bytes:
        head = self.inbox[uid].split(b"\r\n\r\n", 1)[0]
        found = re.search(rb"(?im)^content-type:.*(?:\r\n[ \t].*)*", head)
        return (found.group(0) if found else b"") + b"\r\n\r\n"

    def uid(self, command: str, *args: Any) -> tuple[str, list[Any]]:
        self.calls.append((command, *(str(each) for each in args)))
        if command == "SEARCH":
            wanted = [
                uid
                for uid in self.inbox
                if "\\Deleted" not in self.flags[uid]
                and b"multipart/report" in self._header(uid).lower()
            ]
            return "OK", [" ".join(wanted).encode()]
        if command == "FETCH":
            uid, item = args
            assert "PEEK" in item, item
            if "HEADER.FIELDS" in item:
                data = self._header(uid)
            else:
                limit = int(re.search(r"<0\.(\d+)>", item).group(1))  # type: ignore[union-attr]
                data = self.inbox[uid][:limit]
            return "OK", [(f"1 (UID {uid} BODY[] {{{len(data)}}}".encode(), data), b")"]
        if command == "MOVE":
            uid, folder = args
            self.moved.setdefault(folder, []).append(uid)
            del self.inbox[uid]
            return "OK", [b"Moved"]
        if command == "COPY":
            uid, folder = args
            self.moved.setdefault(folder, []).append(uid)
            return "OK", [b"Copied"]
        if command == "STORE":
            uid, _, flags = args
            self.flags[uid].add(flags.strip("()"))
            return "OK", [b"Stored"]
        if command == "EXPUNGE":
            (uid,) = args
            del self.inbox[uid]
            return "OK", [b"Expunged"]
        raise AssertionError(f"unexpected {command}")


MAILBOX = {"1": PLAIN, "2": dsn("gone@example.org"), "3": arf("fan@example.org")}


def _connect(fake: FakeImap) -> Callable[..., FakeImap]:
    def connect(host: str, port: int, timeout: float) -> FakeImap:
        assert (host, port) == ("mail.site.test", 993)
        return fake

    return connect


def test_the_reader_peeks_at_headers_and_opens_only_reports() -> None:
    fake = FakeImap(MAILBOX, ("IMAP4REV1", "MOVE"))
    box = bounces.ImapMailbox(LOGIN, connect=_connect(fake))
    found = box.reports()
    assert [uid for uid, _ in found] == ["2", "3"]
    fetched = [call for call in fake.calls if call[0] == "FETCH"]
    assert all("PEEK" in call[2] for call in fetched)
    # The plain message was never fetched at all: the search left it out.
    assert not any(call[1] == "1" for call in fetched)
    assert not any(call[0] == "STORE" for call in fake.calls)


def test_a_handled_report_moves_once_and_nothing_else_moves() -> None:
    fake = FakeImap(MAILBOX, ("IMAP4REV1", "MOVE"))
    box = bounces.ImapMailbox(LOGIN, connect=_connect(fake))
    for uid, _ in box.reports():
        box.done(uid)
    assert fake.moved == {'"Newsletter bounces"': ["2", "3"]}
    assert set(fake.inbox) == {"1"}
    assert fake.made == ['"Newsletter bounces"']
    assert box.reports() == []
    box.close()
    assert fake.out


def test_without_move_a_report_is_copied_and_only_it_is_expunged() -> None:
    fake = FakeImap(MAILBOX, ("IMAP4REV1", "UIDPLUS"))
    box = bounces.ImapMailbox(LOGIN, connect=_connect(fake))
    box.done("2")
    assert ("EXPUNGE", "2") in fake.calls
    assert not any(call == ("EXPUNGE",) for call in fake.calls)
    assert set(fake.inbox) == {"1", "3"}


def test_without_uidplus_a_report_is_flagged_deleted_and_never_read_again() -> None:
    fake = FakeImap(MAILBOX, ("IMAP4REV1",))
    box = bounces.ImapMailbox(LOGIN, connect=_connect(fake))
    box.done("2")
    assert fake.flags["2"] == {"\\Deleted"}
    assert not any(call[0] == "EXPUNGE" for call in fake.calls)
    assert [uid for uid, _ in box.reports()] == ["3"]


# --- the job's run, against a fake mailbox ---------------------------------------------


class FakeMailbox:
    def __init__(self, reports: list[tuple[str, bytes]], *, fail_reading: bool = False) -> None:
        self.waiting = list(reports)
        self.done_with: list[str] = []
        self.fail_reading = fail_reading
        self.closed = False

    def reports(self, limit: int = 200) -> list[tuple[str, bytes]]:
        if self.fail_reading:
            raise OSError("the connection dropped")
        return list(self.waiting)

    def done(self, uid: str) -> None:
        self.done_with.append(uid)
        self.waiting = [(each, raw) for each, raw in self.waiting if each != uid]

    def close(self) -> None:
        self.closed = True


async def _subscriber(db: AsyncSession, address: str) -> str:
    """A subscriber, committed: its token."""
    token = uuid.uuid4().hex
    db.add(
        Subscriber(
            id=uuid.uuid4(),
            email=address,
            email_normal=address.lower(),
            source="form",
            status="subscribed",
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            token_sealed=crypto.seal(token),
            created_at=clock.now(),
        )
    )
    await db.commit()
    return token


async def _aside(db: AsyncSession, address: str) -> SetAside | None:
    found = await db.scalar(select(SetAside).where(SetAside.email_normal == address.lower()))
    return found


def _sessions(database: Database) -> Callable[[], Any]:
    @asynccontextmanager
    async def sessions() -> AsyncIterator[AsyncSession]:
        async with database.sessions() as session:
            yield session

    return sessions


def _address(name: str) -> str:
    return f"{name}-{uuid.uuid4().hex[:10]}@example.org"


@pytest.mark.db
async def test_a_run_sets_aside_the_newsletter_s_addresses_and_reads_each_report_once(
    database: Database, db: AsyncSession
) -> None:
    gone, fan, stranger = _address("gone"), _address("fan"), _address("stranger")
    gone_token = await _subscriber(db, gone)
    fan_token = await _subscriber(db, fan)
    box = FakeMailbox(
        [
            ("1", PLAIN),
            ("2", dsn(gone, token=gone_token)),
            ("3", arf(fan, token=fan_token)),
            ("4", dsn(stranger)),  # a sign-in link that bounced: not the newsletter's
            ("5", dsn(fan, status="5.7.1", diagnostic="smtp; 550 5.7.1 blocked", token=fan_token)),
        ]
    )
    handled = await read_mailbox(_sessions(database), LOGIN, lambda login: box)
    assert handled == 4
    assert box.done_with == ["2", "3", "4", "5"]  # the plain message is left where it is
    assert box.closed
    assert (await _aside(db, gone)).why == "bounced"  # type: ignore[union-attr]
    assert (await _aside(db, fan)).why == "complained"  # type: ignore[union-attr]
    assert await _aside(db, stranger) is None
    again = await read_mailbox(_sessions(database), LOGIN, lambda login: box)
    assert again == 0


@pytest.mark.db
async def test_nothing_is_read_without_the_mailbox_s_variables(database: Database) -> None:
    opened: list[bounces.Login] = []

    def opener(login: bounces.Login) -> FakeMailbox:
        opened.append(login)
        return FakeMailbox([])

    assert await read_mailbox(_sessions(database), None, opener) == 0
    assert opened == []


@pytest.mark.db
async def test_a_mailbox_that_can_t_be_reached_changes_nothing_and_raises_nothing(
    database: Database, db: AsyncSession
) -> None:
    gone = _address("gone")
    token = await _subscriber(db, gone)

    def unreachable(login: bounces.Login) -> FakeMailbox:
        raise TimeoutError("no answer")

    assert await read_mailbox(_sessions(database), LOGIN, unreachable) == 0
    dropping = FakeMailbox([("2", dsn(gone, token=token))], fail_reading=True)
    assert await read_mailbox(_sessions(database), LOGIN, lambda login: dropping) == 0
    assert dropping.closed
    assert await _aside(db, gone) is None


@pytest.mark.db
async def test_a_report_that_won_t_move_is_set_aside_and_the_rest_go_on(
    database: Database, db: AsyncSession
) -> None:
    first, second = _address("first"), _address("second")
    tokens = [await _subscriber(db, first), await _subscriber(db, second)]

    class Stuck(FakeMailbox):
        def done(self, uid: str) -> None:
            if uid == "1":
                raise OSError("the move failed")
            super().done(uid)

    box = Stuck([("1", dsn(first, token=tokens[0])), ("2", dsn(second, token=tokens[1]))])
    assert await read_mailbox(_sessions(database), LOGIN, lambda login: box) == 1
    assert box.done_with == ["2"]
    assert (await _aside(db, first)).why == "bounced"  # type: ignore[union-attr]
    assert (await _aside(db, second)).why == "bounced"  # type: ignore[union-attr]


def test_a_report_s_tokens_are_read_from_the_copy_it_returns() -> None:
    token = "Ab_c-" + "d" * 30
    assert bounces.tokens_in(dsn("gone@example.org", token=token)) == {token}
    assert bounces.tokens_in(arf("fan@example.org", token=token)) == {token}
    assert bounces.tokens_in(dsn("gone@example.org")) == set()
    # A token in the report's own words, not the returned copy, vouches for nobody.
    forged = dsn("gone@example.org", diagnostic=f"smtp; 550 5.1.1 ?token={token}")
    assert bounces.tokens_in(forged) == set()


@pytest.mark.db
async def test_a_forged_report_sets_nobody_aside(database: Database, db: AsyncSession) -> None:
    """CodeRabbit on #134: anyone can mail the bounce mailbox, so a report must
    return the address's own copy, its token, before it sets the address aside."""
    target, other = _address("target"), _address("other")
    await _subscriber(db, target)
    other_token = await _subscriber(db, other)
    box = FakeMailbox(
        [
            ("1", dsn(target)),  # no copy of ours
            ("2", dsn(target, token=other_token)),  # someone else's copy
            ("3", arf(target, token="x" * 32)),  # a token nobody holds
        ]
    )
    assert await read_mailbox(_sessions(database), LOGIN, lambda login: box) == 3
    assert box.done_with == ["1", "2", "3"]
    assert await _aside(db, target) is None


@pytest.mark.db
async def test_a_report_that_can_t_be_read_still_moves(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(raw: bytes) -> None:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")

    monkeypatch.setattr(bounces, "read_report", broken)
    box = FakeMailbox([("1", dsn("gone@example.org"))])
    assert await read_mailbox(_sessions(database), LOGIN, lambda login: box) == 1
    assert box.done_with == ["1"]


def test_the_limit_counts_only_real_reports() -> None:
    """CodeRabbit on #134: other multipart/reports, left in place, never crowd out bounces."""
    receipt = (
        b'Content-Type: multipart/report; report-type=disposition-notification; boundary="R"\r\n'
        b"\r\n--R--\r\n"
    )
    fake = FakeImap(
        {"1": receipt, "2": receipt, "3": receipt, "9": dsn("gone@example.org")},
        ("IMAP4REV1", "MOVE"),
    )
    box = bounces.ImapMailbox(LOGIN, connect=_connect(fake))
    assert [uid for uid, _ in box.reports(limit=1)] == ["9"]
