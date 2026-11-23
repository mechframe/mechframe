"""The MechFrame kernel: the always-installed core every module depends on.

This file is the kernel's public surface (SPEC.md section 6). Modules and
sites import from `kernel` only; every other name in this package is private
and may change in any release. The surface follows semver with `__version__`.

Built so far (K1): the database, settings, module switches, crypto, errors,
rate limits, access marks and the app factory. From K2: the access
dependencies (`current_user`, `optional_user`, `require_permission`,
`require_owner_or`, `require_recent_auth`). From K3: `storage`, `email`,
`jobs`, `events`, `audit`, `notifications`, `moderation` and `server_copy`.
From K4: `Answer`, `answer`, `Id` and `When`, for every route's answer model.
The contract hooks (decision 0052): `lifecycle`, `taxonomy`, `search`, `seed`,
`bot` with its `BotProof`, `consent`, `privacy` with its `Subject`, and the
Dashboard's `attention` and `setup`.
"""

from kernel import (
    ai,
    attention,
    audit,
    bot,
    consent,
    crypto,
    email,
    events,
    jobs,
    lifecycle,
    moderation,
    notifications,
    privacy,
    search,
    seed,
    server_copy,
    setup,
    storage,
    taxonomy,
)
from kernel.access import public
from kernel.answers import Answer, Id, When, answer
from kernel.app import create_app
from kernel.auth.dependencies import (
    OwnerOr,
    current_user,
    optional_user,
    require_owner_or,
    require_permission,
    require_recent_auth,
)
from kernel.bot import BotProof
from kernel.db import Base, Database, for_saving, get_db, one_row_only
from kernel.errors import Problem
from kernel.modules import InstalledModule, Manifest, load_module, require_module
from kernel.ratelimit import rate_limit
from kernel.settings import settings
from kernel.version import __version__

__all__ = [
    "Answer",
    "Base",
    "BotProof",
    "Database",
    "Id",
    "InstalledModule",
    "Manifest",
    "OwnerOr",
    "Problem",
    "When",
    "__version__",
    "ai",
    "answer",
    "attention",
    "audit",
    "bot",
    "consent",
    "create_app",
    "crypto",
    "current_user",
    "email",
    "events",
    "for_saving",
    "get_db",
    "jobs",
    "lifecycle",
    "load_module",
    "moderation",
    "notifications",
    "one_row_only",
    "optional_user",
    "privacy",
    "public",
    "rate_limit",
    "require_module",
    "require_owner_or",
    "require_permission",
    "require_recent_auth",
    "search",
    "seed",
    "server_copy",
    "settings",
    "setup",
    "storage",
    "taxonomy",
]
