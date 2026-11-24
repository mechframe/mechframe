"""discography: its publishable content (kernel.lifecycle, hook 1, decision 0052):
a release is drafted, scheduled for its release day and published, and its
tracks go live with it. module.json's `content_types` names
`discography.release` with `"lifecycle": true`."""

from __future__ import annotations

from discography.models import Release

PUBLISHABLE: tuple[type, ...] = (Release,)
