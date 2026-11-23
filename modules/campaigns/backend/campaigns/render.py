"""The email as a subscriber gets it (`dev plans/contracts/campaigns.md` §2,
"The email", and §5), from VybeSite's `render_service.py`: its footer, its
preheader and its one-click headers.

- **The HTML part** is the body's Markdown made HTML by `kernel.markdown.render`
  (cleaned to the kernel's allowlist), each tag given its inline style, in a
  single column of 600px built of tables with inline styles: no stylesheet, no
  web font and no image of the frame's own, since at least one major mail app
  strips or ignores each. The colours are written as values (an email can't
  read CSS variables), a neutral palette that reads in a mail app's light and
  dark modes alike; dark mode is the mail app's.
- **The text part** is the Markdown as written, which reads as plain text, with
  the site's own links made absolute. `kernel.markdown.plain` runs the blocks
  together and drops each link's address, which a text part needs.
- **The footer** is the footer note, the site's name with the postal address
  (CAN-SPAM) and "Unsubscribe", the person's own link to the confirm page.
- **The preheader** is the preview text, hidden, so the inbox shows it rather
  than the body's first line.
- **Headers:** RFC 8058's `List-Unsubscribe` (the API's address, which takes
  the one-click POST) and `List-Unsubscribe-Post`, which only work together.

Links aren't rewritten and nothing tracks opens (§6).
"""

from __future__ import annotations

import html as html_escape
import re
import string
from dataclasses import dataclass
from urllib.parse import quote

from kernel import markdown

CONFIRM_PAGE = "/newsletter/confirm"
UNSUBSCRIBE_PAGE = "/newsletter/unsubscribe"
UNSUBSCRIBE_API = "/api/campaigns/unsubscribe"
ONE_CLICK = "List-Unsubscribe=One-Click"
TEST_MARK = "[Test] "

#: The frame's colours, as values.
PAGE = "#f4f4f5"
PAPER = "#ffffff"
INK = "#1f2328"
MUTED = "#5b616b"
LINE = "#e4e4e7"
LINK = "#1d4ed8"
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
MONO = "SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace"

#: Each tag the cleaned body may hold, and its inline style.
_STYLES = {
    "p": "margin:0 0 16px;",
    "h2": f"margin:24px 0 12px;font-size:22px;line-height:1.3;color:{INK};",
    "h3": f"margin:20px 0 10px;font-size:18px;line-height:1.35;color:{INK};",
    "h4": f"margin:16px 0 8px;font-size:16px;line-height:1.4;color:{INK};",
    "h5": f"margin:16px 0 8px;font-size:15px;line-height:1.4;color:{INK};",
    "h6": f"margin:16px 0 8px;font-size:14px;line-height:1.4;color:{INK};",
    "ul": "margin:0 0 16px;padding:0 0 0 24px;",
    "ol": "margin:0 0 16px;padding:0 0 0 24px;",
    "li": "margin:0 0 6px;",
    "blockquote": f"margin:0 0 16px;padding:0 0 0 16px;border-left:3px solid {LINE};color:{MUTED};",
    "pre": f"margin:0 0 16px;padding:12px;background-color:{PAGE};font-family:{MONO};font-size:13px;white-space:pre-wrap;",
    "code": f"font-family:{MONO};font-size:0.92em;",
    "hr": f"border:0;border-top:1px solid {LINE};margin:24px 0;",
    "a": f"color:{LINK};text-decoration:underline;",
    "img": "display:block;max-width:100%;height:auto;border:0;margin:0 0 16px;",
    "table": "border-collapse:collapse;margin:0 0 16px;",
    "th": f"border:1px solid {LINE};padding:6px 8px;text-align:left;",
    "td": f"border:1px solid {LINE};padding:6px 8px;",
}
_TAG = re.compile(r"<(" + "|".join(_STYLES) + r")(?=[\s>/])")
_SITE_LINK = re.compile(r'\b(href|src)="/(?!/)')
_MARKDOWN_LINK = re.compile(r"(\]\()/(?!/)")


@dataclass(frozen=True)
class Footer:
    note: str
    site_name: str
    #: Its lines as typed; "" while it isn't set.
    postal_address: str


@dataclass(frozen=True)
class Parts:
    """What's the same in every subscriber's copy."""

    subject: str
    preview: str
    body_html: str
    body_text: str
    footer: Footer
    site_url: str


def footer_note(template: str, site_name: str) -> str:
    """The footer's note, with `${site_name}` filled in and nothing else read."""
    return string.Template(template).safe_substitute(site_name=site_name)


def absolute(html: str, site_url: str) -> str:
    """The site's own links and images made absolute: an email isn't on the site."""
    return _SITE_LINK.sub(lambda match: f'{match.group(1)}="{site_url}/', html)


def styled(html: str) -> str:
    """Each tag of the cleaned body given its inline style."""
    return _TAG.sub(lambda match: f'<{match.group(1)} style="{_STYLES[match.group(1)]}"', html)


def parts(subject: str, preview: str, body: str, footer: Footer, site_url: str) -> Parts:
    site_url = site_url.rstrip("/")
    return Parts(
        subject=subject,
        preview=preview,
        body_html=styled(absolute(markdown.render(body), site_url)),
        body_text=_MARKDOWN_LINK.sub(lambda match: f"{match.group(1)}{site_url}/", body).strip(),
        footer=footer,
        site_url=site_url,
    )


def unsubscribe_page(site_url: str, token: str | None) -> str:
    """The footer's link: the page with one button, which a scanner opening it can't press."""
    base = f"{site_url.rstrip('/')}{UNSUBSCRIBE_PAGE}"
    return base if token is None else f"{base}?token={quote(token, safe='')}"


def confirm_page(site_url: str, token: str) -> str:
    return f"{site_url.rstrip('/')}{CONFIRM_PAGE}?token={quote(token, safe='')}"


def headers(site_url: str, token: str) -> dict[str, str]:
    """RFC 8058's one-click unsubscribe: both headers, which only work together."""
    api = f"{site_url.rstrip('/')}{UNSUBSCRIBE_API}?token={quote(token, safe='')}"
    return {"List-Unsubscribe": f"<{api}>", "List-Unsubscribe-Post": ONE_CLICK}


def _address_lines(address: str) -> list[str]:
    return [line.strip() for line in address.splitlines() if line.strip()]


def _footer_lead(footer: Footer) -> str:
    """The site's name and its address, on one line: "Vibrant Mindz · P.O. Box 12, Boston, MA"."""
    address = ", ".join(_address_lines(footer.postal_address))
    return " · ".join(part for part in (footer.site_name.strip(), address) if part)


def text(parts: Parts, unsubscribe: str) -> str:
    lines = ["", "-" * 40]
    if parts.footer.note.strip():
        lines.append(parts.footer.note.strip())
    lead = [parts.footer.site_name.strip(), *_address_lines(parts.footer.postal_address)]
    lines.extend(part for part in lead if part)
    lines.append(f"Unsubscribe: {unsubscribe}")
    body = parts.body_text or parts.subject
    return body.rstrip() + "\n" + "\n".join(lines) + "\n"


def _e(value: str) -> str:
    return html_escape.escape(value, quote=True)


def html(parts: Parts, unsubscribe: str) -> str:
    """The whole HTML part: a single column at 600px, every style inline."""
    preheader = (
        f'<div style="display:none;max-height:0;max-width:0;overflow:hidden;opacity:0;mso-hide:all;">'
        f"{_e(parts.preview)}{'&#8199;&#847; ' * 40}</div>"
        if parts.preview.strip()
        else ""
    )
    note = (
        f'<p style="margin:0 0 8px;">{_e(parts.footer.note)}</p>'
        if parts.footer.note.strip()
        else ""
    )
    lead = _footer_lead(parts.footer)
    lead_line = f'<p style="margin:0 0 8px;">{_e(lead)}</p>' if lead else ""
    body = parts.body_html or f'<p style="margin:0 0 16px;">{_e(parts.subject)}</p>'
    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="x-apple-disable-message-reformatting">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f"<title>{_e(parts.subject)}</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{PAGE};">'
        f"{preheader}"
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{PAGE};">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        f'style="width:100%;max-width:600px;background-color:{PAPER};border-radius:8px;">'
        f'<tr><td style="padding:24px 32px 0;font-family:{FONT};font-size:14px;font-weight:600;'
        f'line-height:1.4;color:{MUTED};">{_e(parts.footer.site_name)}</td></tr>'
        f'<tr><td style="padding:16px 32px 8px;font-family:{FONT};font-size:16px;line-height:1.6;'
        f'color:{INK};">{body}</td></tr>'
        f'<tr><td style="padding:16px 32px 28px;font-family:{FONT};font-size:13px;line-height:1.5;'
        f'color:{MUTED};border-top:1px solid {LINE};">'
        f"{note}{lead_line}"
        f'<p style="margin:0;"><a href="{_e(unsubscribe)}" style="color:{MUTED};'
        'text-decoration:underline;">Unsubscribe</a></p>'
        "</td></tr>"
        "</table>"
        "</td></tr>"
        "</table>"
        "</body>"
        "</html>"
    )


def preview_html(parts: Parts) -> str:
    """The body and the footer as the editor's Preview draws them in the kit's
    Prose: the admin's own styles, since its CSP allows no inline style."""
    body = markdown.render(parts.body_text) if parts.body_text else ""
    note = f"<p>{_e(parts.footer.note)}</p>" if parts.footer.note.strip() else ""
    lead = _footer_lead(parts.footer)
    lead_line = (
        f"<p>{_e(lead)}</p>"
        if parts.footer.postal_address
        else f"<p>{_e(parts.footer.site_name)} · (the postal address isn't set yet)</p>"
    )
    return f'{body}<hr>{note}{lead_line}<p><a href="{_e(unsubscribe_page(parts.site_url, None))}">Unsubscribe</a></p>'


def escaped(words: str) -> str:
    """Text a person didn't write as Markdown, made safe to put in some: each
    character Markdown reads escaped."""
    return re.sub(r"([\\`*_{}\[\]()#+\-.!<>|~])", r"\\\1", " ".join(words.split()))
