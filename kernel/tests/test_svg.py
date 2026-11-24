"""The kernel's SVG helper (decision 0065; `dev plans/contracts/blog-covers.md` §2):
a model's SVG cleaned to an allowlist and written out by the kernel, then made a
PNG with resvg. No test calls Anthropic: these are the SVGs a model might send."""

from __future__ import annotations

import asyncio
import struct
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from kernel import svg

NS = "http://www.w3.org/2000/svg"
DRAWN = '<rect x="0" y="0" width="10" height="10" fill="#c33"/>'


def _svg(inner: str, attrs: str = "") -> str:
    return f'<svg xmlns="{NS}" viewBox="0 0 100 50"{attrs}>{inner}</svg>'


def _clean(text: str) -> str:
    return svg.clean(text, width=1200, height=630)


@pytest.mark.parametrize(
    ("given", "gone"),
    [
        (f"<script>alert(1)</script>{DRAWN}", "alert"),
        (f'<g onload="alert(1)">{DRAWN}</g>', "onload"),
        (f'<rect width="5" height="5" style="fill:url(https://x.test/a)"/>{DRAWN}', "x.test"),
        (f"<style>@import url(https://x.test/a.css);</style>{DRAWN}", "x.test"),
        (f'<image href="https://x.test/a.png" width="5" height="5"/>{DRAWN}', "x.test"),
        (f"<foreignObject><div>hi</div></foreignObject>{DRAWN}", "div"),
        (f'<a href="javascript:alert(1)"><circle r="2"/></a>{DRAWN}', "javascript"),
        (f'<use href="data:image/svg+xml,AAAA"/>{DRAWN}', "data:"),
        (f'<rect width="5" height="5" fill="url(https://x.test/#g)"/>{DRAWN}', "x.test"),
        (f'<text><textPath href="#p">along</textPath></text>{DRAWN}', "along"),
        (f'<animate attributeName="x" to="9"/>{DRAWN}', "animate"),
        (f'<rect width="5" height="5" class="danger"/>{DRAWN}', "danger"),
        (f'<other:thing xmlns:other="urn:x">sneaky</other:thing>{DRAWN}', "sneaky"),
    ],
)
def test_only_the_allowlist_survives(given: str, gone: str) -> None:
    cleaned = _clean(_svg(given))
    assert gone not in cleaned
    assert "#c33" in cleaned  # what's allowed is kept


def test_what_the_allowlist_keeps_is_kept() -> None:
    given = _svg(
        '<defs><linearGradient id="g"><stop offset="0" stop-color="#123"/></linearGradient>'
        '<filter id="f"><feGaussianBlur stdDeviation="2"/></filter></defs>'
        '<rect width="10" height="10" fill="url(#g)" filter="url(#f)"/>'
        '<use href="#g"/><text x="5" y="5" font-weight="700">Ten years</text>'
    )
    cleaned = _clean(given)
    for kept in ('fill="url(#g)"', 'filter="url(#f)"', 'href="#g"', "Ten years", "stdDeviation"):
        assert kept in cleaned


@pytest.mark.parametrize(
    "given",
    [
        '<!DOCTYPE svg [<!ENTITY a "aaaa">]>' + _svg(DRAWN),
        _svg(DRAWN).replace("<rect", '<!ENTITY b "b"><rect'),
    ],
)
def test_a_doctype_or_an_entity_is_refused(given: str) -> None:
    with pytest.raises(svg.Refused):
        _clean(given)


@pytest.mark.parametrize(
    "given",
    [
        _svg(DRAWN + "<desc>" + "x" * svg.MAX_BYTES + "</desc>"),
        _svg("<g/>" * (svg.MAX_ELEMENTS + 1) + DRAWN),
        _svg("<g>" * (svg.MAX_DEPTH + 1) + DRAWN + "</g>" * (svg.MAX_DEPTH + 1)),
    ],
)
def test_too_big_too_many_or_too_deep_is_refused(given: str) -> None:
    with pytest.raises(svg.Refused):
        _clean(given)


@pytest.mark.parametrize(
    "given",
    [
        "No picture here, sorry.",
        _svg("<defs>" + DRAWN + "</defs>"),
        _svg("<script>only this</script>"),
        "<svg><rect width='1'",
    ],
)
def test_nothing_drawable_is_refused(given: str) -> None:
    with pytest.raises(svg.Refused):
        _clean(given)


def test_what_is_written_out_is_the_kernels_own() -> None:
    answer = (
        "Here is your cover:\n```svg\n"
        f"<svg viewBox='0 0 9 9' width='9'><!-- a note --><?pi here?>{DRAWN}</svg>\n```"
    )
    cleaned = _clean(answer)
    for gone in ("note", "<?pi", "```"):
        assert gone not in cleaned
    root = ET.fromstring(cleaned)  # noqa: S314 (the kernel's own output)
    assert root.tag == f"{{{NS}}}svg"
    assert (root.get("viewBox"), root.get("width"), root.get("height")) == (
        "0 0 1200 630",
        "1200",
        "630",
    )
    # Cleaned again, it's the same: the kernel's own form is a fixed point.
    assert _clean(cleaned) == cleaned


def test_every_font_is_the_kernels() -> None:
    cleaned = _clean(
        _svg(f'<text font-family="Comic Sans MS" x="1" y="9">Hi</text>{DRAWN}', ' font-family="x"')
    )
    root = ET.fromstring(cleaned)  # noqa: S314 (the kernel's own output)
    families = {element.get("font-family") for element in root.iter() if element.get("font-family")}
    assert families == {svg.FONT_FAMILY}


def _png_size(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])  # IHDR follows the signature
    return width, height


def test_a_cleaned_svg_renders_to_a_png_of_its_size() -> None:
    cleaned = _clean(_svg(DRAWN))
    png = asyncio.run(svg.png(cleaned, width=2400, height=1260))
    assert _png_size(png) == (2400, 1260)


def test_words_are_drawn_in_the_kernels_font(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ground = '<rect width="1200" height="630" fill="#fff"/>'
    words = _clean(_svg(ground + '<text x="100" y="300" font-size="120">Ten years</text>'))
    blank = _clean(_svg(ground))

    def drawn(drawing: str) -> bytes:
        return asyncio.run(svg.png(drawing, width=600, height=315))

    assert sorted(path.name for path in svg.FONTS.glob("*.ttf")) == [
        "Inter-Bold.ttf",
        "Inter-Regular.ttf",
        "Inter-SemiBold.ttf",
    ]
    assert drawn(words) != drawn(blank)
    # The positive control: with no font of the kernel's, the words draw nothing.
    monkeypatch.setattr(svg, "FONTS", tmp_path)
    assert drawn(words) == drawn(blank)


def test_a_render_past_its_time_is_stopped_not_left_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Codex on #147: giving up the wait isn't enough; the render itself must end. A
    renderer that would finish after 3 seconds, and write so, is stopped at the limit."""
    finished = tmp_path / "finished"
    slow = "\n".join(
        [
            "import time, pathlib",
            "time.sleep(3)",
            f"pathlib.Path({str(finished)!r}).write_text('yes')",
        ]
    )
    monkeypatch.setattr(svg, "_CHILD", slow)
    monkeypatch.setattr(svg, "RENDER_SECONDS", 0.5)

    started = time.monotonic()
    with pytest.raises(svg.Refused, match="too long"):
        asyncio.run(svg.png(_clean(_svg(DRAWN)), width=24, height=12))
    assert time.monotonic() - started < 2.5
    time.sleep(3.5)
    assert not finished.exists()


def test_a_render_that_fails_is_refused_in_plain_words(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svg, "_CHILD", "raise SystemExit(3)")
    with pytest.raises(svg.Refused, match="couldn't be rendered"):
        asyncio.run(svg.png(_clean(_svg(DRAWN)), width=24, height=12))


# --- CodeRabbit on #147 ----------------------------------------------------------------------


def test_a_drawing_inside_a_drawing_is_taken_whole() -> None:
    """The outer <svg> ends where it closes, not at its first inner </svg>."""
    nested = f'<svg x="0" y="0" width="50" height="50">{DRAWN}</svg>'
    answer = "Here it is: " + _svg(nested + '<circle cx="5" cy="5" r="4"/>') + " Hope it helps."
    cleaned = _clean(answer)
    assert "<circle" in cleaned
    assert cleaned.count("<svg") == 2


def test_what_is_written_out_is_never_over_the_limit() -> None:
    """The kernel's own form adds Inter to every text, so a drawing under 100 KB as sent
    can be over it once written out; it's refused, as cleaning it again would be."""
    many = "".join('<text x="1" y="1">a</text>' for _ in range(3500))
    assert len(_svg(many).encode("utf-8")) < svg.MAX_BYTES
    with pytest.raises(svg.Refused, match="over 100 KB"):
        _clean(_svg(many))


@pytest.mark.parametrize(
    "answer",
    [
        _svg("<!-- </svg> -->" + DRAWN),
        _svg("<title><![CDATA[</svg> a title]]></title>" + DRAWN),
        "<!-- <svg> --> Here: " + _svg(DRAWN),
        f'<svg xmlns="{NS}" aria-label="a/>b" viewBox="0 0 100 50">{DRAWN}</svg>',
    ],
)
def test_a_tag_in_a_comment_cdata_or_quoted_value_doesnt_end_the_drawing(answer: str) -> None:
    """CodeRabbit on #147, again: only real <svg> tags count, not words that look like one."""
    assert "<rect" in _clean(answer)
