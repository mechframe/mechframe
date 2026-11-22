"""kernel.markdown: what a person writes in Markdown, made HTML on the server
and cleaned (decision 0055; SPEC.md 15, "User HTML").

Ported from VybeSite's body tests (`tests/test_body_sanitising.py`): what an
author pastes into a body can't reach a reader, and what the editor makes
comes out as python-markdown made it.
"""

from __future__ import annotations

import html as html_escape
import re

import pytest

from kernel import markdown, server_copy

_ADDRESS = re.compile(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)


def addresses(out: str) -> list[str]:
    """Every href and src, as a browser's URL parser reads them (WHATWG URL):
    entities decoded, a tab or a newline anywhere dropped, control characters
    and spaces at either end gone, in lower case. A space inside stays, so
    `java    script:` (python-markdown expands a tab) is a path on the site."""
    found = []
    for parts in _ADDRESS.findall(out):
        address = html_escape.unescape("".join(parts))
        address = "".join(ch for ch in address if ch not in "\t\n\r")
        found.append(address.strip("".join(chr(n) for n in range(33))).lower())
    return found


# --- what the editor makes ------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "made"),
    [
        (
            "Some **bold** and _italic_ words.",
            "<p>Some <strong>bold</strong> and <em>italic</em> words.</p>",
        ),
        ("## A heading", "<h2>A heading</h2>"),
        ("### A smaller one", "<h3>A smaller one</h3>"),
        ("> A pull quote", "<blockquote>\n<p>A pull quote</p>\n</blockquote>"),
        ("[Credits](/credits)", '<p><a href="/credits">Credits</a></p>'),
        (
            "[Mail us](mailto:hello@example.com)",
            '<p><a href="mailto:hello@example.com">Mail us</a></p>',
        ),
        (
            '[Credits](/credits "The people")',
            '<p><a href="/credits" title="The people">Credits</a></p>',
        ),
        ("- one\n- two", "<ul>\n<li>one</li>\n<li>two</li>\n</ul>"),
        ("3. three\n4. four", '<ol start="3">\n<li>three</li>\n<li>four</li>\n</ol>'),
        ("Line one  \nline two", "<p>Line one<br>\nline two</p>"),
        ("---", "<hr>"),
        ("`code`", "<p><code>code</code></p>"),
        ("```\nfenced\n```", "<pre><code>fenced\n</code></pre>"),
        (
            "![The crew](https://cdn.example.com/crew.jpg)",
            '<p><img alt="The crew" src="https://cdn.example.com/crew.jpg"></p>',
        ),
    ],
)
def test_what_the_editor_makes_comes_out_as_made(text: str, made: str) -> None:
    assert markdown.render(text) == made


def test_a_table_keeps_its_rows_and_loses_its_alignment() -> None:
    out = markdown.render("| Track | Length |\n| :-- | --: |\n| Catalyst | 3:12 |")
    assert "<table>" in out
    assert "<th>Track</th>" in out
    assert "<td>3:12</td>" in out
    # An inline style is what the CSP refuses, so alignment goes and the cell stays.
    assert "style" not in out


def test_a_sane_list_never_joins_two_lists() -> None:
    out = markdown.render("- one\n- two\n\n1. first\n2. second")
    assert out.count("<ul>") == 1
    assert out.count("<ol>") == 1


@pytest.mark.parametrize(
    "text", ["# The title again", "<h1>Pasted</h1>", '<h1 class="x">Pasted</h1>']
)
def test_an_h1_becomes_an_h2_since_the_page_has_its_own(text: str) -> None:
    out = markdown.render(text)
    assert "<h1" not in out
    assert out.startswith("<h2>")
    assert out.endswith("</h2>")


def test_an_h1_written_as_code_stays_code() -> None:
    out = markdown.render("`<h1>`")
    assert out == "<p><code>&lt;h1&gt;</code></p>"


# --- what can't reach a reader --------------------------------------------------


@pytest.mark.parametrize(
    ("pasted", "gone"),
    [
        ("<script>alert(1)</script>", ["<script", "alert(1)"]),
        ("<style>body{display:none}</style>", ["<style", "display:none"]),
        ('<iframe src="https://evil.example"></iframe>', ["<iframe", "evil.example"]),
        ('<form action="https://evil.example"><input name="card"></form>', ["<form", "<input"]),
        ('<p onclick="steal()">Hi</p>', ["onclick", "steal()"]),
        ('<img src="x" onerror="steal()">', ["onerror"]),
        ('<a href="#" style="position:fixed">Hi</a>', ["style"]),
        ('<object data="x.swf"></object>', ["<object"]),
        ('<svg onload="steal()"></svg>', ["<svg", "onload"]),
    ],
)
def test_pasted_html_is_cleaned_away(pasted: str, gone: list[str]) -> None:
    out = markdown.render(f"Before\n\n{pasted}\n\nAfter")
    for piece in gone:
        assert piece not in out
    assert "Before" in out
    assert "After" in out


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
    ],
)
def test_an_unsafe_address_goes_and_its_words_stay(link: str) -> None:
    for text in (f"[Click]({link})", f'<a href="{link}">Click</a>', f'<img src="{link}" alt="x">'):
        out = markdown.render(text)
        assert all(
            not found.startswith(("javascript", "data", "vbscript")) for found in addresses(out)
        )
    assert "Click" in markdown.render(f"[Click]({link})")


def test_the_result_is_stable_when_cleaned_again() -> None:
    text = (
        "## Heading\n\nSome **bold**, a [link](/about) and `code`.\n\n> Quote\n\n"
        "- a\n- b\n\n![Art](https://cdn.example.com/a.png)\n\n| a | b |\n| - | - |\n| 1 | 2 |"
    )
    once = markdown.render(text)
    assert str(server_copy.cleaned(once)) == once


def test_nothing_written_is_nothing_made() -> None:
    assert markdown.render("") == ""
    assert markdown.render("   \n\n ") == ""


# --- the words alone ------------------------------------------------------------


def test_plain_gives_the_words_with_a_space_between_blocks() -> None:
    text = "## About us\n\nWe make **music** & art.\n\n- One\n- Two\n\n<script>x()</script>"
    assert markdown.plain(text) == "About us We make music & art. One Two"


def test_plain_keeps_an_images_alt_out_and_a_links_words_in() -> None:
    assert markdown.plain("See [the credits](/credits). ![A photo](https://x.example/p.png)") == (
        "See the credits."
    )


@pytest.mark.parametrize(
    ("text", "limit", "made"),
    [
        ("Short words.", 160, "Short words."),
        ("One two three four five", 13, "One two…"),
        ("Onetwothreefourfive", 8, "Onetwot…"),
        ("One two three", 13, "One two three"),
        ("One two, three", 9, "One two…"),
    ],
)
def test_excerpt_cuts_at_a_word_within_the_limit(text: str, limit: int, made: str) -> None:
    out = markdown.excerpt(text, limit)
    assert out == made
    assert len(out) <= limit
