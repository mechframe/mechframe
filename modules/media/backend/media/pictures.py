"""What the media library stores for an upload (`dev plans/contracts/media.md`).

Lifted from VybeSite's media library (`backend/app/services/media_service.py`),
whose rules hold whole. An upload is a file from a person served back to the
world, so:

- **Judged by what is in the file,** never by its name or the type the browser
  claimed: Pillow opens it as a PNG, JPEG or WebP, or it is refused with a
  sentence. Not SVG, a document with its own scripting; not GIF, HEIC or AVIF.
- **Read within limits:** at most 15 MB, and at most about 50 megapixels,
  judged from the header before a pixel is decoded, so a small file that would
  unpack to gigabytes (a decompression bomb) is refused cheaply. Pillow's own
  warning about one becomes that refusal, never a 500.
- **Stored as our own encoding of it,** never the bytes uploaded: turned the
  way its EXIF orientation says, at most 2400 px on its longest side, the same
  kind it came as, and with no metadata at all. EXIF (and GPS with it), XMP,
  comments and text are dropped, so a photo never tells anyone where it was
  taken or on what. **Colour profiles (ICC)** are applied, then dropped: the
  pixels are converted from the image's own profile to sRGB, which browsers
  assume when an image carries none. A profile that can't be read is dropped
  and the pixels kept as they are.
- **Smaller copies** at 480, 960 and 1600 px wide, each below the image's own
  width, for a page's `srcset`, made with it.

Everything here decodes and encodes images, which takes a moment: callers run
it off the event loop (`asyncio.to_thread`).
"""

from __future__ import annotations

import hashlib
import io
import struct
import warnings
from dataclasses import dataclass

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

MB = 1024 * 1024
#: The most an upload may be: a phone's photo is a few MB.
MAX_UPLOAD_BYTES = 15 * MB
#: The most our encoding of it may be.
MAX_STORED_BYTES = 8 * MB
#: About 50 megapixels: room for a 48-megapixel phone photo, and far short of
#: what a small file can claim to unpack to.
MAX_PIXELS = 50_000_000
#: The longest side stored, in pixels.
MAX_SIDE = 2400
#: For JPEG and WebP.
QUALITY = 85
#: The widths a smaller copy is made at, smallest first.
WIDTHS = (480, 960, 1600)

#: The kinds taken, as Pillow names them: (content type, extension).
KINDS = {
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "WEBP": ("image/webp", "webp"),
}
EXTENSIONS = dict(KINDS.values())

NOT_AN_IMAGE = (
    "That isn't a PNG, JPEG or WebP image, whatever its name says. "
    "Those are the kinds the media library takes."
)
DAMAGED = (
    "That image couldn't be read: it may be damaged or cut short. "
    "Save it again and upload the new file."
)
ANIMATED = (
    "That image is animated, and only still images are taken. "
    "Upload one frame as a PNG, JPEG or WebP."
)
NAMED = {
    "GIF": "That is a GIF. Images here are PNG, JPEG or WebP: save it as one of those and upload it again.",
    "HEIC": (
        "That is a HEIC photo, which most browsers can't show. "
        "Save it as a JPEG and upload it again."
    ),
    "SVG": (
        "That is an SVG, a document that can carry its own scripts, so it isn't taken. "
        "Upload it as a PNG instead."
    ),
}

# What Pillow raises for a file it can't read: OSError for most, and a parser
# may raise any of the rest. Caught only around Pillow's own calls.
_UNREADABLE = (
    OSError,
    SyntaxError,
    ValueError,
    EOFError,
    IndexError,
    TypeError,
    KeyError,
    ZeroDivisionError,
    struct.error,
)

# An ISO media file's brands that mean HEIF/HEIC, an iPhone's photo format,
# and those that mean AVIF, which may name the generic HEIF ones too.
_HEIF_BRANDS = {
    b"heic",
    b"heix",
    b"heim",
    b"heis",
    b"hevc",
    b"hevx",
    b"hevm",
    b"hevs",
    b"mif1",
    b"msf1",
}
_AVIF_BRANDS = {b"avif", b"avis"}

# Pillow's 16-bit grey modes, which its own conversion to 8 bits clips.
_SIXTEEN_BIT_GREY = {"I", "I;16", "I;16B", "I;16L", "I;16N"}


class Refused(ValueError):
    """An upload not taken: the sentence saying why, and its problem code and status."""

    def __init__(self, sentence: str, code: str, status: int) -> None:
        super().__init__(sentence)
        self.code = code
        self.status = status


def _too_large(sentence: str) -> Refused:
    return Refused(sentence, "media.too_large", 413)


def _not_an_image(sentence: str) -> Refused:
    return Refused(sentence, "media.not_an_image", 415)


def _unreadable() -> Refused:
    return Refused(DAMAGED, "media.unreadable", 422)


@dataclass(frozen=True)
class Prepared:
    """What is stored for an upload: our encoding of it, its measure, and its smaller copies."""

    content_type: str
    extension: str
    data: bytes
    width: int
    height: int
    sha256: str
    #: (width, bytes) for each of `WIDTHS` below `width`, smallest first.
    sizes: tuple[tuple[int, bytes], ...] = ()


def _megabytes(size: int) -> str:
    return f"{size / MB:g} MB"


def _too_many_pixels() -> str:
    return (
        f"That image has more than {MAX_PIXELS // 1_000_000} megapixels, too many to take "
        "safely. Make it smaller and upload it again."
    )


def widths_below(width: int) -> tuple[int, ...]:
    """The copies made of an image `width` px wide: each width below its own."""
    return tuple(each for each in WIDTHS if each < width)


def prepare(data: bytes) -> Prepared:
    """What to store for an upload, with its smaller copies, or `Refused` saying why not."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise _too_large(
            f"That file is over {_megabytes(MAX_UPLOAD_BYTES)}. "
            "Make the image smaller and upload it again."
        )
    image = _opened(data)
    # A JPEG carrying more pictures after the first (MPO, which cameras and
    # phones write: a second view, a depth map) opens as "MPO" with frames. It
    # is no animation: its first picture is the photo, and the one that loads.
    kind = "JPEG" if image.format == "MPO" else str(image.format)
    if kind != "JPEG" and getattr(image, "is_animated", False):
        raise _not_an_image(ANIMATED)
    # From the header alone: nothing has been decoded yet.
    if image.width * image.height > MAX_PIXELS:
        raise _too_large(_too_many_pixels())
    try:
        image.load()
        ImageOps.exif_transpose(image, in_place=True)
    except _UNREADABLE:
        raise _unreadable() from None

    image = _pixels_for(kind, _in_srgb(image))
    if max(image.size) > MAX_SIDE:
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    stored = _encoded(kind, image)
    if len(stored) > MAX_STORED_BYTES:
        raise _too_large(
            f"That image is still over {_megabytes(MAX_STORED_BYTES)} once resized and cleaned. "
            "Save it as a JPEG, or smaller, and upload it again."
        )
    content_type, extension = KINDS[kind]
    sizes = tuple(
        (width, resized(stored, content_type, width)) for width in widths_below(image.width)
    )
    return Prepared(
        content_type=content_type,
        extension=extension,
        data=stored,
        width=image.width,
        height=image.height,
        sha256=hashlib.sha256(stored).hexdigest(),
        sizes=sizes,
    )


def _opened(data: bytes) -> Image.Image:
    """`data` opened as a PNG, JPEG or WebP, judged by its content alone, with
    its size read from its header and not a pixel decoded; or `Refused`."""
    try:
        # Past its own limit, higher than ours, Pillow warns of a possible
        # decompression bomb, and past twice that it raises. The warning is
        # made an error here, so it is refused below rather than printed or
        # raised as a 500. The filter is process-wide: two uploads at once can
        # leave it on a moment longer or take it off a moment early, and
        # either way the pixel check in `prepare` still refuses the image.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            return Image.open(io.BytesIO(data), formats=list(KINDS))
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise _too_large(_too_many_pixels()) from None
    except UnidentifiedImageError:
        seen = _looks_like(data)
        if seen in KINDS:
            raise _unreadable() from None
        raise _not_an_image(NAMED.get(seen or "", NOT_AN_IMAGE)) from None
    except _UNREADABLE:
        raise _unreadable() from None


def _looks_like(data: bytes) -> str | None:
    """What the first bytes say a file is, for the wording of a refusal only:
    what is taken is decided by Pillow opening it."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "GIF"
    brands = _iso_brands(data)
    # An AVIF may name the generic HEIF brand too, so its own brand wins.
    if brands & _HEIF_BRANDS and not brands & _AVIF_BRANDS:
        return "HEIC"
    if b"<svg" in data[:1024].lower():
        return "SVG"
    return None


def _iso_brands(data: bytes) -> set[bytes]:
    """The brands an ISO media file (HEIC, AVIF) names in its first box,
    `ftyp`: the major brand, then the compatible ones after a version."""
    if data[4:8] != b"ftyp":
        return set()
    box = data[8 : min(int.from_bytes(data[:4], "big"), 64)]
    return {box[:4]} | {box[at : at + 4] for at in range(8, len(box) - 3, 4)}


def _in_srgb(image: Image.Image) -> Image.Image:
    """The pixels in sRGB by the image's own colour profile, which is dropped
    with the rest of its metadata when it is encoded. CMYK, a print format,
    always comes out in RGB."""
    profile = image.info.get("icc_profile")
    if profile and image.mode in ("RGB", "RGBA", "CMYK"):
        if image.mode == "RGB" and "transparency" in image.info:
            # A see-through colour lives in `info`, which the converted image
            # doesn't carry: make it alpha first.
            image = image.convert("RGBA")
        try:
            converted = ImageCms.profileToProfile(
                image,
                ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                ImageCms.createProfile("sRGB"),
                outputMode="RGBA" if image.mode == "RGBA" else "RGB",
            )
        except (ImageCms.PyCMSError, OSError, ValueError, TypeError):
            pass  # A profile that can't be read or applied: the pixels as they are.
        else:
            if converted is not None:
                return converted
    if image.mode == "CMYK":
        return image.convert("RGB")
    return image


def _pixels_for(kind: str, image: Image.Image) -> Image.Image:
    """The image in a mode its kind stores well. JPEG is RGB. WebP is RGB, or
    RGBA when anything is transparent. A PNG keeps grey as grey and, unless it
    is about to be resized, a palette as a palette, with its transparency."""
    if image.mode in _SIXTEEN_BIT_GREY:
        # Pillow's own conversion clips 16-bit grey to white: scale it instead.
        image = image.convert("I").point(lambda value: value / 256).convert("L")
        image.info.pop("transparency", None)  # a 16-bit value, meaningless now
    if kind == "JPEG":
        target = "RGB"
    elif kind == "PNG" and image.mode == "P" and max(image.size) <= MAX_SIDE:
        return image
    else:
        alpha = image.has_transparency_data
        if kind == "PNG" and image.mode in ("1", "L", "LA", "La"):
            target = "LA" if alpha else "L"
        else:
            target = "RGBA" if alpha else "RGB"
    return image if image.mode == target else image.convert(target)


def _encoded(kind: str, image: Image.Image) -> bytes:
    """The image as a file of its kind, carrying its pixels and nothing else.

    `info` holds what Pillow read from the upload (EXIF, XMP, comments, text,
    the colour profile), and its encoders copy some of it unasked, so it is
    emptied first. A palette's transparency is the one thing kept: it says
    which colours are see-through, so it is part of the picture."""
    params = {}
    if image.mode == "P" and "transparency" in image.info:
        params["transparency"] = image.info["transparency"]
    image.info = {}
    out = io.BytesIO()
    if kind == "JPEG":
        image.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    elif kind == "PNG":
        image.save(out, "PNG", optimize=True, **params)
    else:
        image.save(out, "WEBP", quality=QUALITY)
    return out.getvalue()


def resized(data: bytes, content_type: str, width: int) -> bytes:
    """A copy of a stored image, `width` px wide, of its kind.

    A palette (which `prepare` keeps for a PNG it doesn't resize) is made
    colour first, which Pillow scales smoothly; it scales a palette by its
    nearest pixel. Nothing stored is one-bit: `prepare` makes that grey."""
    kind = next(name for name, (each, _) in KINDS.items() if each == content_type)
    image: Image.Image = Image.open(io.BytesIO(data), formats=[kind])
    image.load()
    if image.mode == "P":
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
    height = max(1, round(image.height * width / image.width))
    copy = image.resize((width, height), Image.Resampling.LANCZOS)
    return _encoded(kind, _pixels_for(kind, copy))
