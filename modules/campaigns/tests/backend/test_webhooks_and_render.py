"""Resend's signature and its events (`webhooks.py`), the email's frame and
footer (`render.py`) and the bodies' checks (`schemas.py`)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from campaigns import render, webhooks
from campaigns.schemas import CampaignEmailChange, NewSubscription, Settings
from pydantic import ValidationError

KEY = b"a signing key of thirty-two bytes"
SECRET = "whsec_" + base64.b64encode(KEY).decode()
NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
BODY = b'{"type":"email.bounced","data":{"to":["gone@example.org"]}}'


def _headers(body: bytes = BODY, at: datetime = NOW, key: bytes = KEY) -> dict[str, str]:
    stamp = str(int(at.timestamp()))
    return {
        "svix-id": "msg_2abc",
        "svix-timestamp": stamp,
        "svix-signature": webhooks.signed(key, "msg_2abc", stamp, body),
    }


# --- the signature ---------------------------------------------------------------------


def test_a_good_signature_names_its_delivery() -> None:
    secret = webhooks.secret_from({webhooks.SECRET: SECRET})
    assert secret == KEY
    assert webhooks.verified(secret, _headers(), BODY, NOW) == "msg_2abc"


def test_a_rotated_key_s_signature_beside_the_new_one_is_taken() -> None:
    headers = _headers()
    headers["svix-signature"] = f"v1,bm90IHRoaXMgb25l {headers['svix-signature']}"
    assert webhooks.verified(KEY, headers, BODY, NOW) == "msg_2abc"


@pytest.mark.parametrize(
    "change",
    ["body", "key", "stale", "future", "no-id", "no-signature", "no-secret"],
)
def test_anything_else_is_refused(change: str) -> None:
    headers = _headers(key=b"another key entirely, 32 bytes!!" if change == "key" else KEY)
    body = BODY
    secret: bytes | None = KEY
    now = NOW
    if change == "body":
        body = BODY.replace(b"gone", b"kept")
    elif change == "stale":
        now = NOW + timedelta(seconds=webhooks.TOLERANCE + 1)
    elif change == "future":
        now = NOW - timedelta(seconds=webhooks.TOLERANCE + 1)
    elif change == "no-id":
        headers.pop("svix-id")
    elif change == "no-signature":
        headers.pop("svix-signature")
    elif change == "no-secret":
        secret = None
    assert webhooks.verified(secret, headers, body, now) is None


def test_the_secret_fails_closed() -> None:
    assert webhooks.secret_from({}) is None
    assert webhooks.secret_from({webhooks.SECRET: "whsec_not base64!"}) is None


# --- Resend's events -------------------------------------------------------------------


def _bounce(kind: str, sub: str, message: str = "") -> dict[str, object]:
    return {
        "type": "email.bounced",
        "data": {
            "to": ["gone@example.org"],
            "bounce": {"type": kind, "subType": sub, "message": message},
        },
    }


def test_a_permanent_bounce_sets_the_address_aside() -> None:
    [(address, verdict)] = webhooks.verdicts(
        _bounce("Permanent", "General", "550 5.1.1 The email account does not exist")
    )
    assert (address, verdict.set_aside, verdict.why) == (
        "gone@example.org",
        "bounced",
        "address: 5.1.1",
    )
    # No code is no verdict on the address (CodeRabbit on #134): every doubt sets nobody aside.
    for sub in ("NoEmail", "General"):
        [(_, no_code)] = webhooks.verdicts(_bounce("Permanent", sub))
        assert no_code.set_aside is None, sub


@pytest.mark.parametrize(
    ("stamp", "signature"),
    [
        ("²", None),  # a digit beyond ASCII
        ("9" * 400, None),  # past any time
        ("1" * 5000, None),  # past int()'s digits
        (None, "v1,ünïcode"),  # a signature beyond ASCII
    ],
)
def test_a_malformed_header_is_refused_not_raised(stamp: str | None, signature: str | None) -> None:
    """CodeRabbit on #134: an anonymous request is 401, never a 500."""
    headers = _headers()
    if stamp is not None:
        headers["svix-timestamp"] = stamp
    if signature is not None:
        headers["svix-signature"] = signature
    assert webhooks.verified(KEY, headers, BODY, NOW) is None


def test_a_soft_bounce_a_block_and_the_provider_s_own_list_set_nobody_aside() -> None:
    for event in (
        _bounce("Transient", "MailboxFull", "452 4.2.2 Mailbox full"),
        _bounce("Permanent", "General", "550 5.7.1 Message rejected due to policy"),
        _bounce("Permanent", "Suppressed"),
        _bounce("Undetermined", "Undetermined"),
    ):
        [(_, verdict)] = webhooks.verdicts(event)
        assert verdict.set_aside is None, event


def test_a_complaint_sets_the_address_aside_and_other_events_say_nothing() -> None:
    complained = {"type": "email.complained", "data": {"to": ["fan@example.org"]}}
    [(address, verdict)] = webhooks.verdicts(complained)
    assert (address, verdict.set_aside) == ("fan@example.org", "complained")
    assert webhooks.verdicts({"type": "email.delivered", "data": {"to": ["fan@example.org"]}}) == []
    assert webhooks.verdicts({"type": "email.bounced"}) == []
    assert webhooks.parsed(b"not json") == {}


# --- the email --------------------------------------------------------------------------

FOOTER = render.Footer(
    render.footer_note(Settings().footer_note, "Test Site"), "Test Site", "P.O. Box 12\nBoston, MA"
)


def _parts(body: str = "Hello.\n\n[The record](/music/one) and ![cover](/m/c.png)") -> render.Parts:
    return render.parts(
        "Winter shows", "Three nights in December", body, FOOTER, "https://site.test/"
    )


def test_the_footer_carries_the_note_the_name_the_address_and_the_person_s_link() -> None:
    link = render.unsubscribe_page("https://site.test", "t0ken")
    html = render.html(_parts(), link)
    text = render.text(_parts(), link)
    assert "You&#x27;re getting this because you asked for news from Test Site." in html
    assert "Test Site · P.O. Box 12, Boston, MA" in html
    assert 'href="https://site.test/newsletter/unsubscribe?token=t0ken"' in html
    assert text.endswith(
        "You're getting this because you asked for news from Test Site.\n"
        "Test Site\nP.O. Box 12\nBoston, MA\n"
        "Unsubscribe: https://site.test/newsletter/unsubscribe?token=t0ken\n"
    )


def test_the_body_s_own_links_are_absolute_and_every_tag_is_styled_inline() -> None:
    made = _parts()
    assert 'href="https://site.test/music/one"' in made.body_html
    assert 'src="https://site.test/m/c.png"' in made.body_html
    assert "<p>" not in made.body_html
    assert '<p style="' in made.body_html
    assert "<a style=" in made.body_html
    assert "[The record](https://site.test/music/one)" in made.body_text


def test_the_frame_is_one_column_of_600px_with_the_preheader_and_no_stylesheet() -> None:
    html = render.html(_parts(), "https://site.test/newsletter/unsubscribe")
    assert "max-width:600px" in html
    assert "Three nights in December" in html.split("<table", 1)[0]
    assert "<style" not in html
    assert "<link" not in html
    assert "<script" not in html
    assert "<title>Winter shows</title>" in html


def test_a_person_s_words_never_become_markup_in_the_frame() -> None:
    made = render.parts(
        "<b>Hi</b>", "<i>x</i>", "<script>alert(1)</script>", FOOTER, "https://site.test"
    )
    html = render.html(made, 'https://site.test/u?token=a"b')
    assert "<script>" not in html
    assert "<b>Hi</b>" not in html
    assert "<i>x</i>" not in html
    assert "token=a&quot;b" in html


def test_the_one_click_headers_go_together_and_name_the_api() -> None:
    assert render.headers("https://site.test", "t/k") == {
        "List-Unsubscribe": "<https://site.test/api/campaigns/unsubscribe?token=t%2Fk>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def test_text_a_person_didn_t_write_as_markdown_stays_words() -> None:
    assert render.escaped("Don't *stop* [now]") == "Don't \\*stop\\* \\[now\\]"


# --- the bodies -------------------------------------------------------------------------


def test_a_sign_up_takes_one_address_and_a_short_source() -> None:
    made = NewSubscription(email=" Rae@Example.com ", source="music-page")
    assert (made.email, made.source, made.name) == ("Rae@Example.com", "music-page", None)
    for bad in ({"email": "a@b.test, c@d.test"}, {"email": "a@b.test", "source": "Music Page"}):
        with pytest.raises(ValidationError):
            NewSubscription(**bad)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        NewSubscription(email="a@b.test", name="Two\nlines")


def test_the_settings_keep_the_address_s_lines_and_bound_the_pace() -> None:
    assert Settings(postal_address="  P.O. Box 12 \r\n\r\n Boston, MA ").postal_address == (
        "P.O. Box 12\nBoston, MA"
    )
    for pace in (0, 10_001):
        with pytest.raises(ValidationError):
            Settings(send_per_hour=pace)
    with pytest.raises(ValidationError):
        Settings(footer_note="Two\nlines")


def test_a_save_s_subject_is_one_line_and_never_empty() -> None:
    with pytest.raises(ValidationError):
        CampaignEmailChange(version=1, subject="Two\nlines")
    with pytest.raises(ValidationError):
        CampaignEmailChange(version=1, subject="   ")
    with pytest.raises(ValidationError):
        CampaignEmailChange(version=1, body="a" + chr(0))
