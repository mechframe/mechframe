"""media: the library every module picks images from (`dev plans/contracts/media.md`).

Images are re-encoded without metadata (`pictures`), stored in the kernel's
public bucket with their smaller copies (`service`), and placed by other
modules through `public`. It loads nothing from elsewhere, so `CSP` is empty:
the public bucket's address is already one `img-src` allows (`https:`).
"""

from typing import Any

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
BOT_PROVIDER: Any = None
