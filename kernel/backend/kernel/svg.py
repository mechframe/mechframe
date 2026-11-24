"""A model's SVG, cleaned to an allowlist and made a PNG (decision 0065;
`dev plans/contracts/blog-covers.md` §2).

    cleaned = svg.clean(answer, width=1200, height=630)   # svg.Refused(reason) if it can't be
    png = await svg.png(cleaned, width=2400, height=1260)

**Clean.** The first `<svg>…</svg>` in the answer is parsed and rebuilt from
the allowlist below, then written out by the kernel, so what's stored and
rendered is never the model's own text. A DOCTYPE or an entity is refused
before parsing. So is anything over `MAX_BYTES`, `MAX_ELEMENTS` or
`MAX_DEPTH`, and anything with nothing drawable left. An element not listed
goes with everything it holds; an attribute not listed goes alone. A link
(`href`, `url(…)`) is kept only to an `#id` in the same drawing. Every
`font-family` becomes the kernel's own font, the only one `png` loads. The
reason a `Refused` carries is written for the model's one repair try.

**PNG.** resvg (resvg-py) draws it in a worker thread, with the kernel's
fonts (`fonts/`) and never the system's, in at most `RENDER_SECONDS`.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import resvg_py

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)

MAX_BYTES = 100_000
MAX_ELEMENTS = 5_000
MAX_DEPTH = 32
RENDER_SECONDS = 10.0

#: The one font a drawing may use: the kernel's, bundled in `fonts/` (OFL-1.1).
FONT_FAMILY = "Inter"
FONTS = Path(__file__).resolve().parent / "fonts"

#: Elements kept, by their local name.
ELEMENTS = frozenset(
    {
        "svg", "g", "defs", "title", "desc", "path", "rect", "circle", "ellipse", "line",
        "polyline", "polygon", "text", "tspan", "linearGradient", "radialGradient", "stop",
        "clipPath", "mask", "pattern", "filter", "use",
        "feBlend", "feColorMatrix", "feComponentTransfer", "feFuncR", "feFuncG", "feFuncB",
        "feFuncA", "feComposite", "feDisplacementMap", "feFlood", "feGaussianBlur", "feMerge",
        "feMergeNode", "feOffset", "feTurbulence",
    }
)  # fmt: skip
#: What counts as drawn, outside `defs`.
DRAWABLE = frozenset(
    {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "use"}
)
#: Elements whose words are kept.
WORDED = frozenset({"text", "tspan", "title", "desc"})

#: Attributes kept on any element that is kept; `href` only to a local `#id`.
ATTRIBUTES = frozenset(
    {
        "id", "href",
        # geometry
        "x", "y", "width", "height", "rx", "ry", "cx", "cy", "r", "fx", "fy", "fr", "x1", "y1",
        "x2", "y2", "points", "d", "transform", "viewBox", "preserveAspectRatio", "pathLength",
        # painting
        "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity",
        "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray",
        "stroke-dashoffset", "opacity", "clip-path", "clip-rule", "mask", "filter", "color",
        "display", "visibility", "mix-blend-mode", "isolation", "paint-order", "vector-effect",
        # gradients, patterns, clips and masks
        "offset", "stop-color", "stop-opacity", "gradientUnits", "gradientTransform",
        "spreadMethod", "patternUnits", "patternContentUnits", "patternTransform",
        "clipPathUnits", "maskUnits", "maskContentUnits",
        # filters
        "filterUnits", "primitiveUnits", "in", "in2", "result", "mode", "values", "type",
        "operator", "k1", "k2", "k3", "k4", "stdDeviation", "dx", "dy", "baseFrequency",
        "numOctaves", "seed", "stitchTiles", "scale", "xChannelSelector", "yChannelSelector",
        "flood-color", "flood-opacity", "tableValues", "slope", "intercept", "amplitude",
        "exponent", "edgeMode",
        # text
        "font-family", "font-size", "font-weight", "font-style", "letter-spacing",
        "word-spacing", "text-anchor", "dominant-baseline", "alignment-baseline",
        "baseline-shift", "text-decoration", "lengthAdjust", "textLength",
    }
)  # fmt: skip

_FOUND = re.compile(r"<svg\b.*?</svg\s*>", re.IGNORECASE | re.DOTALL)
#: A declaration other than a comment or CDATA: a DOCTYPE or an entity.
_DECLARED = re.compile(r"<!(?!--|\[CDATA\[)")
_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)
_LOCAL = re.compile(r"#[A-Za-z_][\w.:-]*")
_NEVER = ("javascript:", "data:", "expression(", "@import", "<")


class Refused(ValueError):
    """Why a drawing can't be cleaned, in words for the model's repair try."""


def _local(tag: str) -> str | None:
    """An SVG element's local name; None for one in another namespace."""
    if tag.startswith("{"):
        namespace, _, name = tag[1:].partition("}")
        return name if namespace == SVG_NS else None
    return tag


def _attribute(key: str) -> str | None:
    """An attribute's name as kept: plain, or xlink's href as href."""
    if key.startswith("{"):
        namespace, _, name = key[1:].partition("}")
        return "href" if namespace == XLINK_NS and name == "href" else None
    return key


def _value_kept(name: str, value: str) -> bool:
    low = value.lower()
    if any(never in low for never in _NEVER):
        return False
    if name == "href":
        return _LOCAL.fullmatch(value.strip()) is not None
    return all(_LOCAL.fullmatch(target.strip()) for _, target in _URL.findall(value))


class _Walk:
    def __init__(self) -> None:
        self.elements = 0
        self.drawn = 0

    def copy(self, source: ET.Element, depth: int, in_defs: bool) -> ET.Element | None:
        name = _local(source.tag) if isinstance(source.tag, str) else None
        if name is None or name not in ELEMENTS:
            return None
        self.elements += 1
        if self.elements > MAX_ELEMENTS:
            raise Refused(f"The drawing has over {MAX_ELEMENTS} elements. Draw it more simply.")
        if depth > MAX_DEPTH:
            raise Refused(f"The drawing nests deeper than {MAX_DEPTH}. Flatten its groups.")
        kept: dict[str, str] = {}
        for key, value in source.attrib.items():
            attribute = _attribute(key)
            if attribute in ATTRIBUTES and _value_kept(attribute, value):
                kept[attribute] = FONT_FAMILY if attribute == "font-family" else value
        if name == "use" and "href" not in kept:
            return None  # a use pointing anywhere but this drawing
        if name in ("text", "tspan"):
            kept["font-family"] = FONT_FAMILY
        made = ET.Element(f"{{{SVG_NS}}}{name}", dict(sorted(kept.items())))
        if name in WORDED:
            made.text = source.text
        if name in DRAWABLE and not in_defs:
            self.drawn += 1
        inside_defs = in_defs or name in ("defs", "clipPath", "mask", "pattern")
        for child in source:
            copied = self.copy(child, depth + 1, inside_defs)
            if copied is not None:
                copied.tail = child.tail if name in ("text", "tspan") else None
                made.append(copied)
        return made


def clean(text: str, *, width: int, height: int) -> str:
    """The first SVG in `text`, rebuilt from the allowlist, `width` by `height`.
    Raises Refused when there's none, or nothing drawable is left."""
    if _DECLARED.search(text):
        raise Refused("The answer declares a DOCTYPE or an entity. Leave them out.")
    found = _FOUND.search(text)
    if found is None:
        raise Refused("There's no complete <svg>…</svg> in the answer. Answer one SVG.")
    drawing = found.group(0)
    if len(drawing.encode("utf-8")) > MAX_BYTES:
        raise Refused(f"The SVG is over {MAX_BYTES // 1000} KB. Draw it more simply.")
    try:
        # A DOCTYPE or entity was refused above, so there's nothing to expand or fetch.
        parsed = ET.fromstring(drawing)  # noqa: S314
    except ET.ParseError:
        raise Refused("The SVG isn't well-formed XML. Answer one well-formed SVG.") from None
    walk = _Walk()
    root = walk.copy(parsed, 1, False)
    if root is None or _local(parsed.tag) != "svg":
        raise Refused("The answer's outer element isn't an <svg>.")
    if walk.drawn == 0:
        raise Refused("Nothing is drawn: every shape is missing, inside defs or not allowed.")
    attributes = dict(root.attrib)
    attributes.update(
        {
            "viewBox": f"0 0 {width} {height}",
            "width": str(width),
            "height": str(height),
            "font-family": FONT_FAMILY,
        }
    )
    root.attrib.clear()
    root.attrib.update(dict(sorted(attributes.items())))
    return ET.tostring(root, encoding="unicode")


def _fonts() -> list[str]:
    return sorted(str(path) for path in FONTS.glob("*.ttf")) if FONTS.is_dir() else []


async def png(drawing: str, *, width: int, height: int) -> bytes:
    """A cleaned SVG as a PNG, `width` by `height`, with the kernel's fonts
    only. Refused when it takes longer than `RENDER_SECONDS`."""

    def render() -> bytes:
        return bytes(
            resvg_py.svg_to_bytes(
                svg_string=drawing,
                width=width,
                height=height,
                skip_system_fonts=True,
                font_files=_fonts(),
                font_family=FONT_FAMILY,
                sans_serif_family=FONT_FAMILY,
            )
        )

    try:
        return await asyncio.wait_for(asyncio.to_thread(render), RENDER_SECONDS)
    except TimeoutError:
        raise Refused("The drawing took too long to render. Draw it more simply.") from None
