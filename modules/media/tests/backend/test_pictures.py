"""The media library's upload rules (`media.pictures`), ported from VybeSite's
`backend/tests/test_media.py`: an upload is judged by what is in it, never by
its name or the type the browser claimed; PNG, JPEG and WebP only, anything
else refused with a sentence; what is stored is our own re-encoding of it,
turned the way the camera meant, at most 2400 px a side, in sRGB, and without
metadata of any kind, so a photo never tells the world where it was taken.
Every image here is made with Pillow."""

from __future__ import annotations

import hashlib
import io
import os
import struct
import subprocess
import sys
import warnings
import zlib
from pathlib import Path

import pytest
from media import pictures
from PIL import ExifTags, Image, ImageCms, PngImagePlugin

BACKEND = Path(__file__).resolve().parents[2] / "backend"


# --- making images ----------------------------------------------------------------


def encoded(image: Image.Image, kind: str, **params) -> bytes:
    out = io.BytesIO()
    image.save(out, kind, **params)
    return out.getvalue()


def opened(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


def photo(size=(320, 240)) -> Image.Image:
    """Something like a photograph: colour that changes across it and grain,
    so an encoder has real work to do."""
    across = Image.linear_gradient("L").resize(size)
    down = Image.linear_gradient("L").rotate(90).resize(size)
    grain = Image.effect_noise(size, 40).convert("L")
    return Image.merge("RGB", (across, grain, down))


def png_claiming(width: int, height: int) -> bytes:
    """A tiny PNG whose header claims `width` x `height`. A header is all a
    decompression bomb needs: it promises more pixels than memory can hold."""
    data = bytearray(encoded(Image.new("1", (1, 1)), "PNG"))
    # IHDR follows the 8-byte signature and its own length: its type, then
    # width, height and five bytes more, then the CRC of all of that.
    header = b"IHDR" + struct.pack(">II", width, height) + bytes(data[24:29])
    data[12:29] = header
    data[29:33] = struct.pack(">I", zlib.crc32(header))
    return bytes(data)


def with_xmp(jpeg: bytes, packet: bytes) -> bytes:
    """The JPEG with an XMP packet in an APP1 segment of its own, where
    cameras and editors put it."""
    body = b"http://ns.adobe.com/xap/1.0/\x00" + packet
    return jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(body) + 2) + body + jpeg[2:]


SVG = (
    b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    b"<script>alert(1)</script></svg>"
)
HTML = b"<!doctype html><html><body><script>alert(1)</script></body></html>"
TEXT = b"Only words, in a file called photo.jpg.\n"
GIF = encoded(Image.new("RGB", (8, 8), (200, 30, 30)), "GIF")
# An iPhone's photo: an ISO box whose brand says HEIC, which browsers can't show.
HEIC = struct.pack(">I", 24) + b"ftypheic" + b"\x00\x00\x00\x00" + b"mif1heic" + b"\x00" * 64
# An AVIF can carry the same generic brand (mif1) first, and is no HEIC.
AVIF = struct.pack(">I", 28) + b"ftypmif1" + b"\x00\x00\x00\x00" + b"mif1avifmiaf" + b"\x00" * 64
_NOISY_JPEG = encoded(photo((300, 300)), "JPEG", quality=90)
TRUNCATED_JPEG = _NOISY_JPEG[: len(_NOISY_JPEG) // 2]
CORRUPT_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


# --- what is taken -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "content_type", "extension"),
    [
        ("PNG", "image/png", "png"),
        ("JPEG", "image/jpeg", "jpg"),
        ("WEBP", "image/webp", "webp"),
    ],
)
def test_each_kind_taken_is_kept_as_that_kind(kind, content_type, extension):
    stored = pictures.prepare(encoded(photo(), kind))

    assert (stored.content_type, stored.extension) == (content_type, extension)
    assert opened(stored.data).format == kind
    assert (stored.width, stored.height) == (320, 240) == opened(stored.data).size
    assert stored.sha256 == hashlib.sha256(stored.data).hexdigest()


def test_a_jpeg_is_stored_progressive_and_in_rgb():
    # A grey JPEG goes back out in colour channels, as every JPEG does here.
    shown = opened(pictures.prepare(encoded(Image.new("L", (64, 64), 128), "JPEG")).data)

    assert shown.mode == "RGB"
    assert shown.info.get("progressive")


def test_a_cameras_multi_picture_jpeg_is_taken_as_a_jpeg_of_its_first_picture():
    """Cameras and phones write MPO: a JPEG with more pictures after the first
    (a second view, a depth map). Pillow opens it as "MPO" with frames, which
    is neither another kind nor an animation: the first picture is the photo."""
    first, second = photo((320, 240)), Image.new("RGB", (160, 120), (200, 30, 30))
    upload = encoded(first, "MPO", save_all=True, append_images=[second])
    assert Image.open(io.BytesIO(upload)).format == "MPO"

    stored = pictures.prepare(upload)

    assert (stored.content_type, stored.extension) == ("image/jpeg", "jpg")
    assert opened(stored.data).format == "JPEG"
    assert (stored.width, stored.height) == (320, 240)


def test_a_webp_is_taken_by_a_process_that_has_never_saved_one(tmp_path):
    """Pillow loads its WebP plugin only when something asks for it. Every
    test here has made a WebP first, so this one asks a fresh interpreter, as
    a fresh server is, to take one."""
    upload = tmp_path / "photo.webp"
    upload.write_bytes(encoded(photo((64, 48)), "WEBP"))
    code = (
        "import sys; from media import pictures; "
        "print(pictures.prepare(open(sys.argv[1], 'rb').read()).content_type)"
    )

    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    taken = subprocess.run(  # noqa: S603 (this interpreter, on a file the test wrote)
        [sys.executable, "-c", code, str(upload)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert taken.stdout.strip() == "image/webp", taken.stderr[-2000:]


def test_a_cmyk_jpeg_comes_out_in_rgb():
    # Print files are CMYK, which some browsers draw in the wrong colours.
    shown = opened(
        pictures.prepare(encoded(Image.new("CMYK", (32, 32), (0, 255, 255, 0)), "JPEG")).data
    )

    assert shown.mode == "RGB"
    red, green, blue = shown.getpixel((16, 16))
    assert red > 200
    assert green < 60
    assert blue < 60


@pytest.mark.parametrize("kind", ["PNG", "WEBP"])
def test_transparency_is_kept_in_a_png_and_a_webp(kind):
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    image.paste((10, 102, 194, 255), (16, 16, 48, 48))

    shown = opened(pictures.prepare(encoded(image, kind)).data).convert("RGBA")

    assert shown.getpixel((2, 2))[3] == 0
    assert shown.getpixel((32, 32))[3] == 255


def test_a_palette_png_keeps_its_transparent_colour():
    image = Image.new("P", (32, 32), 1)
    image.putpalette([0, 0, 0, 10, 102, 194] + [0] * 762)
    image.paste(0, (0, 0, 16, 16))

    shown = opened(pictures.prepare(encoded(image, "PNG", transparency=0)).data).convert("RGBA")

    assert shown.getpixel((4, 4))[3] == 0
    assert shown.getpixel((24, 24)) == (10, 102, 194, 255)


def test_a_16_bit_grey_png_keeps_its_greys():
    # Pillow's own conversion clips 16-bit grey to white instead of scaling it.
    grey = Image.new("I;16", (2, 1))
    grey.putpixel((0, 0), 65535)
    grey.putpixel((1, 0), 32768)

    shown = opened(pictures.prepare(encoded(grey, "PNG")).data)

    assert shown.mode == "L"
    assert (shown.getpixel((0, 0)), shown.getpixel((1, 0))) == (255, 128)


def _refusal(data: bytes) -> pictures.Refused:
    with pytest.raises(pictures.Refused) as refused:
        pictures.prepare(data)
    sentence = str(refused.value)
    assert sentence[0].isupper(), sentence
    assert sentence.endswith("."), sentence
    return refused.value


@pytest.mark.parametrize(
    ("data", "says"),
    [
        pytest.param(SVG, "SVG", id="svg"),
        pytest.param(GIF, "GIF", id="gif"),
        pytest.param(HEIC, "HEIC", id="heic"),
        pytest.param(AVIF, "PNG, JPEG or WebP", id="avif"),
        pytest.param(HTML, "PNG, JPEG or WebP", id="html"),
        pytest.param(TEXT, "PNG, JPEG or WebP", id="text"),
        pytest.param(b"", "PNG, JPEG or WebP", id="empty"),
        pytest.param(TRUNCATED_JPEG, "damaged", id="truncated-jpeg"),
        pytest.param(CORRUPT_PNG, "damaged", id="corrupt-png"),
    ],
)
def test_anything_but_a_whole_png_jpeg_or_webp_is_refused(data, says):
    refusal = _refusal(data)

    assert refusal.status == (422 if says == "damaged" else 415)
    assert refusal.code == ("media.unreadable" if says == "damaged" else "media.not_an_image")
    assert says in str(refusal)


def test_a_file_over_15_mb_is_refused_as_too_large():
    refusal = _refusal(b"\x89PNG\r\n\x1a\n" + bytes(pictures.MAX_UPLOAD_BYTES))

    assert (refusal.status, refusal.code) == (413, "media.too_large")
    assert "15 MB" in str(refusal)


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (8000, 7500),  # 60 MP: over our cap, under Pillow's own
        (10000, 10000),  # 100 MP: Pillow warns
        (15000, 15000),  # 225 MP: Pillow raises
    ],
)
@pytest.mark.parametrize("warnings_are", ["error", "default", "ignore"])
def test_a_pixel_bomb_is_refused_however_pillow_takes_it(width, height, warnings_are):
    """Refused from its header, before a pixel is decoded, whether Pillow
    stays quiet, warns or raises, and whatever the process does with
    warnings: Pillow's warning never escapes as a 500 or into the log."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter(warnings_are)
        refusal = _refusal(png_claiming(width, height))

    assert (refusal.status, refusal.code) == (413, "media.too_large")
    assert "megapixels" in str(refusal)
    assert not [w for w in caught if issubclass(w.category, Image.DecompressionBombWarning)]


@pytest.mark.parametrize("kind", ["PNG", "WEBP"])
def test_an_animated_image_is_refused(kind):
    frames = [Image.new("RGB", (8, 8), colour) for colour in ((200, 30, 30), (30, 30, 200))]

    refusal = _refusal(encoded(frames[0], kind, save_all=True, append_images=frames[1:]))

    assert "animated" in str(refusal)


def test_an_image_still_over_8_mb_once_cleaned_is_refused(monkeypatch):
    monkeypatch.setattr(pictures, "MAX_STORED_BYTES", 1000)

    refusal = _refusal(encoded(photo((200, 200)), "PNG"))

    assert (refusal.status, refusal.code) == (413, "media.too_large")
    assert "MB" in str(refusal)


# --- what is stored ----------------------------------------------------------------

XMP = (
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>Pat Example</dc:creator>'
    b"</rdf:Description></rdf:RDF></x:xmpmeta>"
)
TELLING = (b"Phonemaker", b"Pocket 15", b"Pat Example", b"adobe:ns:meta", b"Taken at home")


def _carrying_everything(kind: str) -> bytes:
    """An upload carrying all a camera or an editor writes about a photo: the
    maker and model, where it was taken, who made it, a comment."""
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Phonemaker"
    exif[ExifTags.Base.Model] = "Pocket 15"
    exif[ExifTags.IFD.GPSInfo] = {
        ExifTags.GPS.GPSLatitudeRef: "N",
        ExifTags.GPS.GPSLatitude: (30.0, 19.0, 55.0),
        ExifTags.GPS.GPSLongitudeRef: "W",
        ExifTags.GPS.GPSLongitude: (81.0, 39.0, 21.0),
    }
    if kind == "JPEG":
        return with_xmp(encoded(photo(), "JPEG", exif=exif, comment=b"Taken at home"), XMP)
    if kind == "PNG":
        text = PngImagePlugin.PngInfo()
        text.add_itxt("XML:com.adobe.xmp", XMP.decode())
        text.add_text("Comment", "Taken at home")
        return encoded(photo(), "PNG", exif=exif, pnginfo=text)
    return encoded(photo(), "WEBP", exif=exif, xmp=XMP)


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "WEBP"])
def test_gps_exif_xmp_and_comments_are_gone(kind):
    upload = _carrying_everything(kind)
    # The upload carries them, so their absence below means something.
    assert opened(upload).getexif().get_ifd(ExifTags.IFD.GPSInfo)
    assert {b"Phonemaker", b"Pocket 15", b"Pat Example"} <= {t for t in TELLING if t in upload}

    stored = pictures.prepare(upload)
    shown = opened(stored.data)

    assert not shown.getexif()
    assert not shown.getexif().get_ifd(ExifTags.IFD.GPSInfo)
    for key in ("exif", "xmp", "XML:com.adobe.xmp", "comment", "Comment", "icc_profile"):
        assert key not in shown.info, key
    for telling in TELLING:
        assert telling not in stored.data, telling


def test_orientation_6_is_applied_so_the_sides_swap():
    # Stored as the sensor saw it, with a red corner top left, and EXIF saying
    # to turn it a quarter clockwise to show it.
    image = Image.new("RGB", (300, 200), (255, 255, 255))
    image.paste((255, 0, 0), (0, 0, 60, 60))
    exif = Image.Exif()
    exif[ExifTags.Base.Orientation] = 6

    stored = pictures.prepare(encoded(image, "JPEG", exif=exif, quality=95))
    shown = opened(stored.data)

    assert (stored.width, stored.height) == (200, 300) == shown.size
    red, green, blue = shown.getpixel((shown.width - 15, 15))
    corner = "the red corner turned to the top right"
    assert red > 200, corner
    assert green < 60, corner
    assert blue < 60, corner
    assert ExifTags.Base.Orientation not in shown.getexif()


@pytest.mark.parametrize(
    ("size", "scaled"),
    [
        ((4000, 1000), (2400, 600)),
        ((1000, 4000), (600, 2400)),
        ((4000, 4000), (2400, 2400)),
        ((2400, 100), (2400, 100)),
        ((100, 50), (100, 50)),
    ],
)
def test_the_longest_side_is_scaled_to_2400_and_nothing_grows(size, scaled):
    stored = pictures.prepare(encoded(Image.new("RGB", size, (10, 102, 194)), "PNG"))

    assert (stored.width, stored.height) == scaled == opened(stored.data).size


def test_a_large_jpeg_is_scaled_too():
    stored = pictures.prepare(encoded(photo((4000, 3000)), "JPEG"))

    assert (stored.width, stored.height) == (2400, 1800)


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "WEBP"])
def test_a_colour_profile_is_applied_then_dropped(kind):
    """Untagged sRGB is what every browser and email app assumes, so the
    pixels are put in sRGB by the image's own profile and the profile goes."""
    colour = (10, 102, 194)
    upload = encoded(Image.new("RGB", (32, 32), colour), kind, icc_profile=SRGB)
    assert "icc_profile" in opened(upload).info

    shown = opened(pictures.prepare(upload).data)

    assert "icc_profile" not in shown.info
    assert all(
        abs(a - b) <= 6
        for a, b in zip(shown.convert("RGB").getpixel((16, 16)), colour, strict=False)
    )


def _red_and_green_swapped() -> bytes:
    """An RGB profile whose red and green colorants trade places in its tag
    table: in an image carrying it, a pixel of full red means green."""
    profile = bytearray(SRGB)
    [count] = struct.unpack(">I", profile[128:132])
    tags = {bytes(profile[at : at + 4]): at for at in range(132, 132 + 12 * count, 12)}
    red, green = tags[b"rXYZ"] + 4, tags[b"gXYZ"] + 4
    profile[red : red + 8], profile[green : green + 8] = (
        profile[green : green + 8],
        profile[red : red + 8],
    )
    return bytes(profile)


def test_the_pixels_are_converted_by_the_images_own_profile():
    """Proof the profile is applied, not just dropped: dropping it would leave
    the pixel red."""
    upload = encoded(
        Image.new("RGB", (32, 32), (255, 0, 0)), "PNG", icc_profile=_red_and_green_swapped()
    )

    red, green, blue = opened(pictures.prepare(upload).data).convert("RGB").getpixel((16, 16))

    assert green > 200
    assert red < 60
    assert blue < 60


def test_a_palette_png_with_a_profile_is_converted_before_the_profile_goes() -> None:
    """CodeRabbit on #116: a palette's colours are in its profile's space too."""
    palette = Image.new("RGB", (32, 32), (255, 0, 0)).convert("P", palette=Image.Palette.ADAPTIVE)
    upload = encoded(palette, "PNG", icc_profile=_red_and_green_swapped())

    red, green, _ = opened(pictures.prepare(upload).data).convert("RGB").getpixel((16, 16))

    assert green > 200
    assert red < 60


def test_a_see_through_colour_survives_the_colour_profile():
    """A PNG can mark one colour see-through instead of carrying alpha. The
    conversion to sRGB makes a new image, which must keep that."""
    image = Image.new("RGB", (32, 32), (10, 102, 194))
    image.paste((255, 255, 255), (0, 0, 16, 16))
    upload = encoded(image, "PNG", transparency=(255, 255, 255), icc_profile=SRGB)
    assert opened(upload).info["transparency"] == (255, 255, 255)

    shown = opened(pictures.prepare(upload).data).convert("RGBA")

    assert shown.getpixel((4, 4))[3] == 0
    assert shown.getpixel((24, 24))[3] == 255


def test_a_profile_that_cannot_be_read_is_dropped_and_the_pixels_kept():
    upload = encoded(
        Image.new("RGB", (32, 32), (10, 102, 194)), "PNG", icc_profile=b"not a profile"
    )

    shown = opened(pictures.prepare(upload).data)

    assert "icc_profile" not in shown.info
    assert shown.convert("RGB").getpixel((16, 16)) == (10, 102, 194)


def test_the_same_upload_is_encoded_the_same_way_every_time():
    # Dedupe compares the re-encoded bytes, so they must not drift.
    upload = encoded(photo(), "JPEG")
    assert pictures.prepare(upload).sha256 == pictures.prepare(upload).sha256


# --- the fake table ----------------------------------------------------------------


# --- the smaller copies ---------------------------------------------------------------


def test_each_smaller_copy_is_made_below_the_images_width_of_its_kind() -> None:
    prepared = pictures.prepare(encoded(photo((1200, 900)), "JPEG"))

    assert [width for width, _ in prepared.sizes] == [480, 960]
    for width, data in prepared.sizes:
        copy = opened(data)
        assert copy.format == "JPEG"
        assert copy.size == (width, round(900 * width / 1200))
        assert not copy.info.get("exif")


def test_an_image_no_wider_than_the_smallest_copy_has_none() -> None:
    assert pictures.prepare(encoded(photo((480, 300)), "PNG")).sizes == ()


def test_a_palette_png_is_made_colour_before_it_is_scaled() -> None:
    palette = photo((1000, 500)).convert("P", palette=Image.Palette.ADAPTIVE, colors=16)

    prepared = pictures.prepare(encoded(palette, "PNG"))

    assert [width for width, _ in prepared.sizes] == [480, 960]
    assert opened(prepared.sizes[0][1]).mode == "RGB"
