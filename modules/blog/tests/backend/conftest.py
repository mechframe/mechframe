"""The backend tests' own fixture: the kernel's registries hold blog's type
and its vocabulary, as an app with blog on does, for tests that call the
service without an app; and the media library's files have addresses. The
contract suite, which runs the app, never has it."""

from __future__ import annotations

import pytest

from kernel import audit, lifecycle, search, server_copy, storage, taxonomy
from kernel.settings import settings

FILES = "https://files.blog.test"


@pytest.fixture(autouse=True)
def blog_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit log takes blog's actions, and the lifecycle, search and
    taxonomy know its type, as an app with blog on does (`audit.install`,
    `lifecycle.install`, `search.install`, `taxonomy.install`)."""
    from blog.lifecycle import PUBLISHABLE
    from blog.search import SEARCH

    monkeypatch.setattr(audit, "_owners", audit._owners | {"blog", "media"})
    monkeypatch.setattr(lifecycle, "_publishable", {"blog.post": PUBLISHABLE[0]})
    monkeypatch.setattr(search, "_sources", {"blog.post": SEARCH[0]})
    category = taxonomy.Vocabulary("blog_category", "Categories", False, ("blog",))
    monkeypatch.setattr(
        taxonomy,
        "_declared",
        taxonomy.Declared({"blog_category": category}, {"blog.post": frozenset({"blog_category"})}),
    )
    monkeypatch.setattr(storage, "public_url", lambda key: f"{FILES}/{key}")
    # The site's identity, which a post's search title and the server copy read.
    monkeypatch.setitem(settings.models, server_copy.SECTION, server_copy.SiteSettings)
