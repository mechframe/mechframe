"""The backend tests' own fixtures: the kernel's registries hold
discography's type, actions and settings, as an app with it on does, for
tests that call the service without an app; storage is a dict in memory; and
events said are kept for the test to read."""

from __future__ import annotations

from typing import Any

import pytest

from kernel import audit, events, lifecycle, search, server_copy, storage
from kernel.settings import settings

FILES = "https://files.music.test"


class Store:
    """The two buckets, in memory: `storage.put`, `get`, `download` and `delete`."""

    def __init__(self) -> None:
        self.files: dict[tuple[str, bool], bytes] = {}
        self.on = True

    async def put(
        self,
        key: str,
        data: Any,
        *,
        content_type: str,
        public: bool = False,
        filename: str | None = None,
    ) -> storage.StoredFile:
        if not self.on:
            raise storage.StorageNotConfigured("Storage is off.")
        body = data if isinstance(data, bytes) else data.read()
        self.files[(key, public)] = body
        return storage.StoredFile(key, len(body), content_type, False)

    async def download(self, key: str, into: Any, *, public: bool = False) -> bool:
        found = self.files.get((key, public))
        if found is None:
            return False
        into.write(found)
        into.seek(0)
        return True

    async def delete(self, key: str, *, public: bool = False) -> None:
        self.files.pop((key, public), None)

    def keys(self, public: bool) -> list[str]:
        return sorted(key for key, is_public in self.files if is_public == public)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> Store:
    found = Store()
    monkeypatch.setattr(storage, "put", found.put)
    monkeypatch.setattr(storage, "download", found.download)
    monkeypatch.setattr(storage, "delete", found.delete)
    return found


@pytest.fixture(autouse=True)
def said(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    """Every event discography says, by name and payload."""
    heard: list[tuple[str, Any]] = []

    async def emit(db: Any, name: str, payload: Any) -> int:
        heard.append((name, payload))
        return 1

    monkeypatch.setattr(events, "emit", emit)
    return heard


@pytest.fixture(autouse=True)
def discography_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit log takes discography's actions; the lifecycle, search and
    settings know it, as an app with it on does; files have addresses."""
    from discography.lifecycle import PUBLISHABLE
    from discography.schemas import Settings
    from discography.search import SEARCH

    monkeypatch.setattr(audit, "_owners", audit._owners | {"discography", "media"})
    monkeypatch.setattr(lifecycle, "_publishable", {"discography.release": PUBLISHABLE[0]})
    monkeypatch.setattr(search, "_sources", {"discography.release": SEARCH[0]})
    monkeypatch.setattr(storage, "public_url", lambda key: f"{FILES}/{key}")
    monkeypatch.setitem(settings.models, "discography", Settings)
    monkeypatch.setitem(settings.models, server_copy.SECTION, server_copy.SiteSettings)
