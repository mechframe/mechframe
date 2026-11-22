# 0054: A module's routes may take a larger body than the site's

- **Status:** Decided; applied with the media module (feat/media). The owner chose it on 2026-11-21 ("Per route limit"), over raising MAX_BODY_BYTES for the whole site or uploading straight to the bucket.
- **Context:** The kernel refuses any request body over MAX_BODY_BYTES (1 MB by default) with 413 `kernel.too_large`, before a route reads it (`BodyLimit`, K1). The media library takes a phone's photo, up to 15 MB, so no such upload ever reached it. Media's HTTP tests found this.
- **Decision:**
  1. A module's `__init__.py` may give `BODY_LIMITS`: `(method, path under /api/<id>, bytes)` entries, such as `("POST", "/admin/images", 16 * 1024 * 1024)`. A path's `{name}` parts match one segment.
  2. While the module is on, those routes take up to their own limit, judged by Content-Length or as the body streams in. Every other route keeps MAX_BODY_BYTES, and so do those routes while the module is off.
  3. The start refuses an entry whose method isn't POST, PUT or PATCH, whose path doesn't start with `/`, or whose limit isn't 1 to 64 MB (`kernel.app.MAX_ROUTE_BODY_BYTES`).
- **Rejected:**
  - Raising MAX_BODY_BYTES site-wide, since every route would then read 16 MB.
  - A browser upload straight to the bucket with a signed link, which is more moving parts. The re-encode would still need the bytes.
- **Consequences:** A route that declares a larger limit reads it into memory, so it reads within limits as media does (`file.read(MAX + 1)`). The module contract lint checks that a module's BODY_LIMITS name its own upload routes.
