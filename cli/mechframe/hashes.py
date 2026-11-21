"""The hash a lock file records for each copied file (K5 contract §2)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def digest_bytes(data: bytes) -> str:
    """`sha256:` of `data` with `\\r\\n` read as `\\n`, so the line endings Git
    writes in a Windows checkout don't count as an edit."""
    return "sha256:" + hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def digest(path: Path) -> str:
    """A file's hash, as `digest_bytes` makes it from its bytes."""
    return digest_bytes(path.read_bytes())
