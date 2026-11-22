"""media: the library every module picks images from (`dev plans/contracts/media.md`).

Images are re-encoded without metadata (`pictures`), stored in the kernel's
public bucket with their smaller copies (`service`), and placed by other
modules through `public`. It loads nothing from elsewhere, so `CSP` is empty:
the public bucket's address is already one `img-src` allows (`https:`).
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
#: Its two upload routes take a phone's photo, past the site's MAX_BODY_BYTES: the
#: 15 MB `pictures` reads and the form's own few bytes (decision 0054).
BODY_LIMITS = (
    ("POST", "/admin/images", 16 * 1024 * 1024),
    ("PUT", "/admin/images/{image_id}/file", 16 * 1024 * 1024),
)
