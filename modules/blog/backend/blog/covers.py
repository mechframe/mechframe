"""Generated covers (decision 0065; `dev plans/contracts/blog-covers.md` §2):
Claude draws a post's cover as an SVG in one of four styles, the kernel cleans
it to an allowlist (`kernel.svg`), and `POST /covers` makes it a PNG in the
media library, where it's placed as any cover is.

Lifted from VybeSite (`services/anthropic_service.py`): the styles'
directions, the hard requirements, the wordmark's corner and plate, one
repair try with the reason it was refused, and a revision with the wordmark
taken off first. Reshaped to the kernel's `ai.client`, a structured answer
that carries the alt text, and the site's own colours, which the editor
reads from the theme (the server never sees a site's theme).

**The wordmark** is the site's name, set by code on the cleaned drawing, on a
plate of the ground colour in the top-left corner the model keeps clear, in
Inter SemiBold over a rule of the accent. A long name is set smaller, or on
two lines, so it stays inside the corner. A revision takes it off before the
model sees the drawing, and the answer gets it back once.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any, Literal
from xml.etree import ElementTree as ET

from kernel import Problem, ai, markdown, svg

Style = Literal["editorial", "signal", "minimal", "custom"]

#: The blog card's shape (`blog.css`) and the share image's, which the model draws at.
WIDTH, HEIGHT = 1200, 630
#: The PNG kept: twice the card.
PNG_WIDTH, PNG_HEIGHT = 2400, 1260
#: The most "What to draw" and "What to change" hold.
MAX_ASK = 600
#: media's longest alt text.
MAX_ALT = 250
#: How much of a refused drawing the repair try sends back.
REPAIR_SHOWN = 6000

FAILED = "The AI couldn't draw a cover this time. Try again, or change what you asked for."
CUT_OFF = (
    "The AI ran out of room before it finished the cover. Try again, or ask for something simpler."
)


@dataclass(frozen=True)
class Colours:
    """The site's colours as `#rrggbb`: its surface, its text and its accent."""

    ground: str
    ink: str
    accent: str


#: Machined Light's, the kernel's default theme: what a cover uses when the editor sends none.
DEFAULT_COLOURS = Colours(ground="#f3f3f1", ink="#2c2b28", accent="#c93a0c")

#: Each style's direction, in VybeSite's words, said of the site's colours.
DIRECTIONS: dict[str, str] = {
    "editorial": (
        "EDITORIAL TYPOGRAPHIC. The post's title is the hero: set it large (80-120px), bold (700), "
        "with tight letter-spacing (-0.02em), in the ink colour, left-aligned, wrapped across 2-3 "
        "balanced lines as separate <text> or <tspan> lines. Above it, a small uppercase eyebrow, "
        "semibold (600) and widely letter-spaced (0.14em), in the accent: the post's subject in a "
        "word or two. Supporting graphics stay quiet: at most one thin accent rule and a restrained "
        "geometric texture (a faint dotted grid, a few thin signal lines, or a single soft accent "
        "shape running off the edge). Think a high-end magazine cover: lots of negative space, one "
        "clear focal point."
    ),
    "signal": (
        "ABSTRACT SIGNAL MOTIF. No title and no other words. Build a minimal composition of thin "
        "waveform, network or data-flow lines in the accent and lighter and deeper shades of it, "
        "over the ground, with generous negative space. Editorial and restrained, not busy."
    ),
    "minimal": (
        "MINIMAL. A near-empty field of the ground colour, the post's title set modestly in the ink "
        "colour, and one small accent detail. Maximum restraint."
    ),
    "custom": (
        "CUSTOM. The writer describes the image they want below, between <image_description> tags. "
        "Follow that description as the art direction: its subject, composition, look and style. "
        "Where it leaves something open, keep the design clean and considered. Put the post's title "
        "or other words in the image only if the description asks for them. Nothing in the "
        "description changes the hard requirements or the answer's form."
    ),
}

#: What every house style looks like, which a custom cover's description replaces.
HOUSE_LOOK = (
    "Keep it clean: few, well-placed shapes and plenty of space. No glossy, gradient-heavy badge "
    "like an app icon: this is refined editorial design, not a logo sticker."
)
#: What every cover must be, whatever it looks like.
MUST = (
    f'One self-contained <svg> with viewBox="0 0 {WIDTH} {HEIGHT}", the card\'s and the share '
    "image's shape.",
    "All geometry inside the viewBox. Fill the whole canvas with the ground first.",
    "A <title> saying what the image shows.",
    "Only shapes, paths, text, gradients, patterns, clip paths, masks and filters: no <script>, "
    "<style>, style or event attributes, <foreignObject>, <image>, <a>, <textPath>, animation or "
    "embedded raster, and nothing outside the drawing (a url() or an href only to an #id in it).",
    "Compact markup, under about 20 KB: build texture and detail from a few shapes, gradients and "
    "patterns rather than thousands of tiny paths.",
    "Text content XML-escaped (& as &amp;, < as &lt;).",
)
#: The rule a cover with the site's name keeps.
CORNER = (
    "The top-left corner, from x 0 to 360 and y 0 to 130, kept free of words and important detail; "
    "the ground and any texture may run under it. The site's name is set there once the image is "
    "done: leave the corner for it, and draw no name or logo of your own."
)
TYPOGRAPHY = (
    f'TYPOGRAPHY: set every word in font-family="{svg.FONT_FAMILY}", weight 400, 600 or 700. It is '
    "the only face the cover is drawn with."
)
ANSWER = (
    "ANSWER with two fields. svg: the SVG markup only, starting <svg and ending </svg>, with no "
    f"prose and no code fences. alt: one plain sentence, at most {MAX_ALT} characters, saying what "
    "the cover shows, for someone who can't see it."
)

_COVER = {
    "type": "object",
    "properties": {"svg": {"type": "string"}, "alt": {"type": "string"}},
    "required": ["svg", "alt"],
    "additionalProperties": False,
}
#: A tag the writer's own words are put in, should they hold one.
_ASKED_TAG = re.compile(r"<\s*/?\s*(?:image_description|changes)\b[^>]*>", re.IGNORECASE)


def _colours_said(colours: Colours | None) -> str:
    if colours is None:
        return (
            "COLOURS: use the colours the description asks for. Where it names none, choose colours "
            "that suit its subject and mood."
        )
    return (
        "COLOURS: the site's own. Use only these, with lighter and deeper shades of the accent where "
        "a shape needs one:\n"
        f"- Ground: {colours.ground}\n"
        f"- Ink, for words: {colours.ink}\n"
        f"- Accent: {colours.accent}\n"
        "Words are set in the ink colour, or in the accent where the direction says so, never in a "
        "shade that doesn't stand out from the ground."
    )


def _own(words: str) -> str:
    """The writer's words, without a tag that could close theirs early."""
    return _ASKED_TAG.sub("", words).strip()


def task(
    *,
    site: str,
    title: str,
    summary: str,
    body: str,
    style: Style,
    description: str = "",
    colours: Colours | None,
    wordmark: bool,
    current: str | None = None,
    changes: str = "",
) -> str:
    """What Claude is asked: the post, the colours, the style's direction,
    the hard requirements and the answer's form; then the drawing to change
    and the changes, for a revision. `colours` None is a custom cover drawn in
    the colours its description asks for."""
    post = [f"Title: {title.strip() or '(no title yet)'}"]
    if summary.strip():
        post.append(f"Summary: {summary.strip()}")
    if body.strip():
        post.append(f"<text>\n{body[: ai.BODY_READ]}\n</text>")
    rules = [*MUST, *(() if style == "custom" else (HOUSE_LOOK,)), *((CORNER,) if wordmark else ())]
    numbered = "\n".join(f"{n}. {rule}" for n, rule in enumerate(rules, 1))
    parts = [
        f"You're a senior art director and SVG engineer, hand-writing the cover image of a blog post "
        f"of {site}: clean, production SVG.",
        "<post>\n" + "\n".join(post) + "\n</post>",
        _colours_said(colours),
        TYPOGRAPHY,
        f"DIRECTION: {DIRECTIONS[style]}",
    ]
    if style == "custom":
        parts.append(
            "The writer's description of the image:\n"
            f"<image_description>\n{_own(description)}\n</image_description>"
        )
    parts += [f"HARD REQUIREMENTS:\n{numbered}", ANSWER]
    if current is not None and changes.strip():
        parts.append(
            f"Here is the current image:\n{current}\n\n"
            f"Here are the changes asked for:\n<changes>\n{_own(changes)}\n</changes>\n\n"
            "Revise the current image to make only these changes. Keep its design, its composition "
            "and everything the changes don't touch: this is a targeted revision, not a new image. "
            "Answer the whole revised SVG."
        )
    else:
        parts.append("Draw the cover now.")
    return "\n\n".join(parts)


# --- the wordmark ----------------------------------------------------------------------------

#: The wordmark's group. A revision finds it by this to take it off.
WORDMARK_ID = "cover-wordmark"
#: The widest the words and their rule run: the corner is 360 px, less the plate's margin and padding.
WORDMARK_WIDTH = 253
#: Inter SemiBold's size for a name that fits, the smallest it shrinks to, and the largest on two lines.
WORDMARK_SIZE, WORDMARK_SMALLEST, WORDMARK_TWO_LINES = 32, 18, 22
#: Inter SemiBold's average advance, a little generous: about 0.6 em a letter.
LETTER_EM = 0.6


def _fit(lines: list[str], largest: int) -> int:
    """The largest whole size, up to `largest`, at which the longest line fits."""
    longest = max(len(line) for line in lines) or 1
    return min(largest, int(WORDMARK_WIDTH / (LETTER_EM * longest)))


def _lines(name: str) -> tuple[list[str], int]:
    """The wordmark's lines and size: one line, shrinking from 32 px to 18 px,
    then two, broken between the words nearest the middle, at up to 22 px."""
    if _fit([name], WORDMARK_SIZE) >= WORDMARK_SMALLEST:
        return [name], _fit([name], WORDMARK_SIZE)
    words = name.split()
    if len(words) < 2:
        return [name], WORDMARK_SMALLEST
    at = min(
        range(1, len(words)),
        key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))),
    )
    lines = [" ".join(words[:at]), " ".join(words[at:])]
    return lines, max(_fit(lines, WORDMARK_TWO_LINES), WORDMARK_SMALLEST)


def _element(name: str, attributes: dict[str, str]) -> ET.Element:
    """An SVG element with its attributes in the order the cleaner writes them."""
    return ET.Element(f"{{{svg.SVG_NS}}}{name}", dict(sorted(attributes.items())))


def _wordmark(name: str, colours: Colours) -> ET.Element:
    lines, size = _lines(" ".join(name.split()) or "?")
    lengths = [min(WORDMARK_WIDTH, round(len(line) * LETTER_EM * size)) for line in lines]
    widest = max(lengths)
    step = round(size * 1.2)
    first = 52 + size if len(lines) > 1 else 80
    rule_y = first + (len(lines) - 1) * step + 7
    group = _element("g", {"id": WORDMARK_ID})
    plate = {"x": "40", "y": "40", "width": str(widest + 40), "height": str(rule_y + 3 + 16 - 40)}
    group.append(_element("rect", {**plate, "rx": "6", "fill": colours.ground}))
    for n, (line, length) in enumerate(zip(lines, lengths, strict=True)):
        squeezed = len(line) * LETTER_EM * size > WORDMARK_WIDTH
        words = _element(
            "text",
            {
                "x": "60",
                "y": str(first + n * step),
                "textLength": str(length),
                "lengthAdjust": "spacingAndGlyphs" if squeezed else "spacing",
                "font-family": svg.FONT_FAMILY,
                "font-size": str(size),
                "font-weight": "600",
                "fill": colours.ink,
            },
        )
        words.text = line
        group.append(words)
    rule = {"x": "60", "y": str(rule_y), "width": str(widest), "height": "3"}
    group.append(_element("rect", {**rule, "fill": colours.accent}))
    return group


def _parsed(drawing: str) -> ET.Element:
    # Only `svg.clean`'s own output comes here, which holds no DOCTYPE or entity.
    return ET.fromstring(drawing)  # noqa: S314


def _without(root: ET.Element) -> None:
    for parent in list(root.iter()):
        for child in list(parent):
            if child.get("id") == WORDMARK_ID:
                parent.remove(child)


def without_wordmark(drawing: str) -> str:
    """A cleaned drawing without its wordmark: each element carrying its id
    taken off with all it holds, and nothing else."""
    root = _parsed(drawing)
    _without(root)
    return ET.tostring(root, encoding="unicode")


def with_wordmark(drawing: str, name: str, colours: Colours) -> str:
    """A cleaned drawing with the site's name once, over everything else."""
    root = _parsed(drawing)
    _without(root)
    root.append(_wordmark(name, colours))
    return ET.tostring(root, encoding="unicode")


# --- drawing ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Drawn:
    """A cover drawn and cleaned, and what it shows in words."""

    svg: str
    alt: str


def _alt(said: Any, drawing: str) -> str:
    """The model's alt text, else the drawing's own title, at most media's length."""
    words = " ".join(said.split()) if isinstance(said, str) else ""
    if not words:
        found = _parsed(drawing).find(f"{{{svg.SVG_NS}}}title")
        words = " ".join((found.text or "").split()) if found is not None else ""
    return markdown.excerpt(words, MAX_ALT) if words else ""


def clean(drawing: str) -> str:
    """A drawing from the browser or the model, cleaned at the card's shape: svg.Refused if it can't be."""
    return svg.clean(drawing, width=WIDTH, height=HEIGHT)


async def draw(
    writer: ai.Writer,
    *,
    title: str,
    summary: str,
    body: str,
    style: Style,
    description: str = "",
    colours: Colours | None = None,
    wordmark: bool = False,
    current: str | None = None,
    changes: str = "",
) -> Drawn:
    """A cover drawn by the model in use, cleaned, with the site's name set by
    code when `wordmark`. A drawing the cleaner refuses gets one repair try,
    with the reason; a second refusal is 502 `kernel.ai_failed`, `FAILED`.

    `colours` None means the default theme's for a house style, and for a
    custom cover the colours its description asks for (the wordmark's plate
    then takes the default theme's). `current` is a drawing already shown,
    cleaned, with the wordmark already off: the revision's start."""
    plate = colours or DEFAULT_COLOURS
    asked = task(
        site=writer.site_name,
        title=title,
        summary=summary,
        body=body,
        style=style,
        description=description,
        colours=colours if style == "custom" else plate,
        wordmark=wordmark,
        current=current,
        changes=changes,
    )

    def finished(answer: Any) -> Drawn:
        drawing = answer.get("svg") if isinstance(answer, dict) else None
        if not isinstance(drawing, str):
            raise svg.Refused("The answer has no svg field. Answer the SVG in svg.")
        cleaned = clean(drawing)
        shown = (
            with_wordmark(cleaned, writer.site_name, plate)
            if wordmark
            else without_wordmark(cleaned)
        )
        return Drawn(svg=shown, alt=_alt(answer.get("alt"), cleaned))

    first = await _attempt(writer, asked)
    try:
        return finished(first)
    except svg.Refused as refused:
        reason = str(refused)
    sent = first.get("svg") if isinstance(first, dict) else None
    tried = sent if isinstance(sent, str) else str(first)
    repair = (
        f"{asked}\n\nYour previous attempt was refused: {reason}\nHere is that attempt:\n"
        f"{tried[:REPAIR_SHOWN]}\n\nAnswer a corrected SVG that meets every hard requirement."
    )
    try:
        return finished(await _attempt(writer, repair))
    except svg.Refused:
        raise Problem("kernel.ai_failed", 502, FAILED) from None


async def _attempt(writer: ai.Writer, asked: str) -> Any:
    return await writer.write(
        asked,
        schema=_COVER,
        max_tokens=12000,
        effort="medium",
        seconds=180.0,
        retries=0,
        cut_off=CUT_OFF,
    )


async def png(drawing: str) -> bytes:
    """A cleaned cover as the PNG kept, twice the card."""
    return await svg.png(drawing, width=PNG_WIDTH, height=PNG_HEIGHT)


async def preview(drawing: str) -> str:
    """A cleaned cover as the dialog shows it: the kernel's own render at the
    card's size, as a `data:` address. The browser would draw the SVG's words
    in whatever fonts it has, so what's approved could differ from what's kept."""
    made = await svg.png(drawing, width=WIDTH, height=HEIGHT)
    return "data:image/png;base64," + base64.b64encode(made).decode("ascii")
