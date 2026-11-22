"""Builds a site's app from the kernel and its modules (SPEC.md sections 6 and 12).

Lifted from VybeSite `main.py`. A site's `backend/app/main.py` is:

    from app import installed
    from app.modules import MODULE_IDS   # written by `mechframe add` and `remove`
    from app.site.pages import SITE_PAGES  # the site's own pages
    from kernel import create_app
    from kernel.config import KernelConfig

    app = create_app(modules=installed(MODULE_IDS), config=KernelConfig(), site=SITE_PAGES)

What it does, in order:
1. Reads the config and refuses to start on unsafe secrets (outside DEBUG).
2. Sets up logging and, when SENTRY_DSN is set, error tracking.
3. Checks MODULES against the installed modules and their requirements.
4. Mounts the kernel's routes at /api/kernel, auth's at /api/auth, and each
   module's router at /api/<id>, behind `require_module(id)`.
5. Adds the middleware: SecurityHeaders (outermost), WwwRedirect, CORS (when
   CORS_ORIGINS is set), SameOriginWrites, BodyLimit, SessionCookies (a
   replaced session token reaches the browser on any answer, errors too) and
   UnexpectedErrors (innermost, so even a 500 carries the security headers).
6. Answers every error as problem details.
7. Installs the mailer (`mailer=`, else SMTP when SMTP_HOST is set, else
   Resend when only RESEND_API_KEY is, else `LogMailer`, which sends nothing)
   behind `kernel.email.Checked`, as
   `app.state.mailer`, and the breach lookup new passwords are checked against
   (`breach_lookup=`, else Have I Been Pwned's range API), as
   `app.state.breach_lookup`.
8. Checks the kernel's own email templates (`kernel.auth.mails`), every
   module's, and the site's rewording of them
   (`emails=`), refusing to start on a bad one, and installs them with the
   mailer for `kernel.email.send`.
9. Checks the kernel's events and every module's (`kernel.events.build`)
   and installs them for `kernel.events.emit` (decision 0036); installs the
   modules that may write to the audit log, and how long it's kept
   (`kernel.audit.install`, decision 0037); checks each module's notification
   keys against its templates and installs them, the kernel's own first
   (`kernel.notifications`, decision 0038); checks what each module lets
   people report and installs it, with the filters' settings section
   (`kernel.moderation`, decision 0039); checks each module's publishable
   models, vocabularies and search sources against its manifest and installs
   them (`kernel.lifecycle`, `kernel.taxonomy` and `kernel.search`, decision
   0052), the kernel's search listening to its own content events; checks the
   kernel's jobs and every module's, their listeners' deliveries among them
   (`kernel.jobs.build`), and builds the site's worker as `app.state.worker`.
   With JOBS_IN_WEB on (the default) the lifespan runs it in this process; a
   site that runs `kernel.worker.serve` as a service of its own turns it off
   (decision 0035).
10. Checks every module's public and member pages (`kernel.server_copy`:
    `routes.public` and `pages` together, no two patterns answering one
    address at one rank) and the shell (`WEB_DIST`, refused without its
    markers), registers the settings section `kernel.site`, and registers,
    after every other route, the kernel's files (`/sitemap.xml`,
    `/robots.txt`, `/llms.txt`) and the catch-all that answers every address
    outside the API (`kernel.shell`, decision 0041); HEAD is answered as GET.
    The site's own pages (`site=`, its `app/site/pages.py`'s `SITE_PAGES`) join
    the modules', always on (decision 0048).

Steps 1 to 3, 7 and 8, the events' and jobs' checks and registering each
module's settings model, and checking the pages, are `assemble`, which
`kernel.worker.create_worker` shares, so a worker process starts on exactly
what the web app would.

The API docs (/docs, /redoc, /openapi.json) are served only with DEBUG on: on
a live site they would map every route for anyone.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from kernel import (
    attention,
    audit,
    bot,
    consent,
    email,
    error_tracking,
    events,
    jobs,
    lifecycle,
    logs,
    moderation,
    notifications,
    openapi,
    privacy,
    search,
    server_copy,
    setup,
    shell,
    taxonomy,
)
from kernel.admin import router as admin_router
from kernel.auth import sign_up
from kernel.auth.codes import router as codes_router
from kernel.auth.dependencies import SessionCookies
from kernel.auth.devices import router as devices_router
from kernel.auth.email_change import router as email_change_router
from kernel.auth.exports import MAKE as MAKE_EXPORT
from kernel.auth.exports import PRUNE as PRUNE_EXPORTS
from kernel.auth.exports import router as exports_router
from kernel.auth.factor_undo import router as factor_undo_router
from kernel.auth.mails import TEMPLATES as KERNEL_MAILS
from kernel.auth.passkeys import router as passkeys_router
from kernel.auth.password_change import router as password_change_router
from kernel.auth.passwords import Passwords, RangeLookup, ask_range
from kernel.auth.permissions import KERNEL_PERMISSION_WORDS
from kernel.auth.resets import router as resets_router
from kernel.auth.roles import router as roles_router
from kernel.auth.routes import router as auth_router
from kernel.auth.sign_up import router as sign_up_router
from kernel.auth.summary import router as summary_router
from kernel.auth.totp import router as totp_router
from kernel.auth.unverified import REMOVE as REMOVE_UNVERIFIED
from kernel.config import KernelConfig, get_config, modules_allowed, refuse_unsafe
from kernel.db import Database
from kernel.email import Checked, Mailer, Template, build_templates
from kernel.errors import BodyLimit, UnexpectedErrors, install_handlers
from kernel.logs import AccessLog
from kernel.mail_adapters import mailer_from_config
from kernel.modules import InstalledModule, ModuleRegistry, require_module
from kernel.ratelimit import RateLimiter
from kernel.routes import router as kernel_router
from kernel.security import ContentSecurityPolicy, SameOriginWrites, SecurityHeaders, WwwRedirect
from kernel.settings import settings
from kernel.version import __version__
from kernel.worker import Worker

log = logging.getLogger(__name__)

#: The kernel's own jobs: queued mail, pruning the queue, removing accounts
#: whose address isn't verified (decision 0035), and pruning the audit log
#: (decision 0037), the notices (decision 0038) and closed moderation cases
#: (decision 0039), publishing what's due, rebuilding site search on
#: demand, and making and pruning the account's exports (decision 0052).
KERNEL_JOBS: tuple[jobs.Job, ...] = (
    email.SEND_MAIL,
    jobs.PRUNE,
    REMOVE_UNVERIFIED,
    audit.PRUNE,
    notifications.PRUNE,
    moderation.PRUNE,
    lifecycle.PUBLISH_DUE,
    search.REINDEX,
    MAKE_EXPORT,
    PRUNE_EXPORTS,
)

#: The kernel's own listeners: site search hearing content published and
#: unpublished (decision 0052, hook 3). Each is delivered by a job of its own.
KERNEL_LISTENERS: tuple[events.Listener, ...] = (search.ON_PUBLISHED, search.ON_UNPUBLISHED)


def _permissions_listed(installed: Iterable[InstalledModule]) -> tuple[dict[str, str], ...]:
    """The kernel's permissions, then each installed module's, in their
    manifests' order: `{key, description, owner}`, the owner being `kernel`
    or the module's id. A key already listed isn't listed again."""
    listed = [
        {"key": key, "description": words, "owner": "kernel"}
        for key, words in KERNEL_PERMISSION_WORDS.items()
    ]
    seen = set(KERNEL_PERMISSION_WORDS)
    for module in installed:
        for permission in module.manifest.raw.get("permissions", []):
            if not isinstance(permission, dict) or not isinstance(permission.get("key"), str):
                continue
            if permission["key"] in seen:
                continue
            seen.add(permission["key"])
            words = permission.get("description")
            listed.append(
                {
                    "key": permission["key"],
                    "description": words if isinstance(words, str) else "",
                    "owner": module.id,
                }
            )
    return tuple(listed)


@dataclass(frozen=True)
class Assembled:
    """What the web app and a worker process are both built from."""

    config: KernelConfig
    installed: tuple[InstalledModule, ...]
    registry: ModuleRegistry
    mailer: Checked
    jobs: tuple[jobs.Job, ...]
    #: The modules' public and member pages (kernel.server_copy).
    public: server_copy.Routes

    def database(self) -> Database:
        return Database(
            self.config.database_url,
            pool_size=self.config.db_pool_size,
            max_overflow=self.config.db_max_overflow,
        )


def assemble(
    *,
    modules: Iterable[InstalledModule] = (),
    config: KernelConfig | None = None,
    mailer: Mailer | None = None,
    emails: Mapping[str, Template] | None = None,
    role: Literal["web", "worker"] = "web",
    site: server_copy.SitePages | None = None,
) -> Assembled:
    """Reads and checks the config, the modules, their mail templates, events
    and jobs, and installs the mailer and templates for `kernel.email` and the
    events for `kernel.events`.
    Raises RuntimeError("Refusing to start: ...") on anything it can't take."""
    config = config or get_config()
    refuse_unsafe(config)
    logs.configure(config.log_format, config.log_level)
    error_tracking.init(config, role)

    installed = tuple(modules)
    try:
        allowed = modules_allowed(config, {module.id for module in installed})
        registry = ModuleRegistry(installed, allowed, ttl=config.modules_cache_seconds)
    except ValueError as error:
        raise RuntimeError(f"Refusing to start: {error}") from error
    try:
        templates = build_templates(
            [
                ("kernel", {**KERNEL_MAILS, **notifications.TEMPLATES, **moderation.TEMPLATES}),
                *((module.id, module.emails) for module in installed),
            ],
            emails or {},
        )
        kinds = notifications.build(
            [
                ("kernel", moderation.NOTIFICATIONS),
                *(
                    (module.id, module.manifest.raw.get("notifications") or [])
                    for module in installed
                ),
            ],
            templates,
        )
        reportable = moderation.build((module.id, module.reportable) for module in installed)
        publishable = lifecycle.build(installed)
        vocabularies = taxonomy.build(installed)
        sources = search.build(installed)
        providers = bot.build(installed)
        asked = consent.build(installed)
        data_hooks = privacy.build(installed)
        needs = attention.build(installed)
        steps = setup.build(installed)
        public = server_copy.build(installed, site)
        catalog = events.build(
            [
                ("kernel", events.KERNEL_PAYLOADS, KERNEL_LISTENERS, None),
                *(
                    (
                        module.id,
                        module.payloads,
                        module.listeners,
                        module.manifest.raw.get("events") or {},
                    )
                    for module in installed
                ),
            ],
            allowed=registry.allowed,
        )
        declared = jobs.build(
            [
                ("kernel", (*KERNEL_JOBS, *(item.job for item in KERNEL_LISTENERS)), None),
                *(
                    (
                        module.id,
                        (*module.jobs, *(listener.job for listener in module.listeners)),
                        module.manifest.raw.get("jobs") or [],
                    )
                    for module in installed
                ),
            ]
        )
    except ValueError as error:
        raise RuntimeError(f"Refusing to start: {error}") from error
    checked = Checked(mailer if mailer is not None else mailer_from_config(config))
    email.install(checked, templates, site_name=config.site_name, site_url=config.site_url)
    events.install(catalog)
    audit.install((module.id for module in installed), keep_days=config.audit_keep_days)
    notifications.install(kinds)
    moderation.install(reportable)
    lifecycle.install(publishable)
    taxonomy.install(vocabularies)
    search.install(sources, language=config.search_language)
    bot.install(providers)
    consent.install(asked)
    privacy.install(data_hooks)
    attention.install(needs)
    setup.install(steps)
    server_copy.install(site_name=config.site_name, site_url=config.site_url)
    # Here, not in create_app: a job in a worker of its own reads its module's
    # settings too (Codex on #63).
    settings.register(moderation.SECTION, moderation.Filters)
    settings.register(server_copy.SECTION, server_copy.SiteSettings)
    settings.register(bot.SECTION, bot.Choice)
    settings.register(sign_up.SECTION, sign_up.settings_model(config.sign_up_mode))
    for module in installed:
        if module.settings is not None:
            settings.register(module.id, module.settings)
    return Assembled(config, installed, registry, checked, declared, public)


#: The most a module's route may take (decision 0054): media's uploads ask for 16 MB.
MAX_ROUTE_BODY_BYTES = 64 * 1024 * 1024
_BODY_METHODS = ("POST", "PUT", "PATCH")
_PATH_PART = re.compile(r"\\{[a-z_][a-z0-9_]*\\}")
#: A path's `{name}` part, for a sample request when two limits are compared.
_SAMPLE_PART = re.compile(r"\{[a-z_][a-z0-9_]*\}")


def _larger_bodies(
    installed: Iterable[InstalledModule], modules_on: Callable[[], frozenset[str]]
) -> Callable[[str, str], int | None]:
    """The limit a module's route takes over the site's MAX_BODY_BYTES while
    the module is on (its `__init__.py`'s BODY_LIMITS, decision 0054), by
    method and path. ValueError at the start for an entry the kernel can't keep."""
    routes: list[tuple[str, str, re.Pattern[str], int, str]] = []
    for module in installed:
        for entry in module.body_limits:
            method, path, size = entry
            where = f"{module.id}'s BODY_LIMITS entry {entry!r}"
            if method not in _BODY_METHODS:
                raise ValueError(f"{where}: its method is POST, PUT or PATCH.")
            if not (isinstance(path, str) and path.startswith("/")):
                raise ValueError(f"{where}: its path starts with /, under /api/{module.id}.")
            if (
                isinstance(size, bool)
                or not isinstance(size, int)
                or not 0 < size <= MAX_ROUTE_BODY_BYTES
            ):
                raise ValueError(f"{where}: its limit is 1 to {MAX_ROUTE_BODY_BYTES:,} bytes.")
            shape = _PATH_PART.sub("[^/]+", re.escape(path))
            pattern = re.compile(f"/api/{re.escape(module.id)}{shape}")
            # Which applied would hang on their order (CodeRabbit on #116): refuse
            # two of one method whose paths can be one request's.
            sample = f"/api/{module.id}" + _SAMPLE_PART.sub("x", path)
            for owner, wanted, other, _size, other_path in routes:
                if owner != module.id or wanted != method:
                    continue
                other_sample = f"/api/{module.id}" + _SAMPLE_PART.sub("x", other_path)
                if other.fullmatch(sample) or pattern.fullmatch(other_sample):
                    raise ValueError(
                        f"{where} and {(method, other_path)!r} both match one request. "
                        "Give each request one limit."
                    )
            routes.append((module.id, method, pattern, size, path))

    def larger(method: str, path: str) -> int | None:
        if not routes:
            return None
        on = modules_on()
        for owner, wanted, pattern, size, _path in routes:
            if method == wanted and owner in on and pattern.fullmatch(path):
                return size
        return None

    return larger


def create_app(
    *,
    modules: Iterable[InstalledModule] = (),
    config: KernelConfig | None = None,
    database: Database | None = None,
    mailer: Mailer | None = None,
    breach_lookup: RangeLookup | None = None,
    emails: Mapping[str, Template] | None = None,
    site: server_copy.SitePages | None = None,
) -> FastAPI:
    built = assemble(
        modules=modules, config=config, mailer=mailer, emails=emails, role="web", site=site
    )
    config, installed, registry = built.config, built.installed, built.registry
    try:
        app_shell = shell.Shell.load(config.web_dist)
    except ValueError as error:
        raise RuntimeError(f"Refusing to start: {error}") from error

    policy = ContentSecurityPolicy()
    for module in installed:
        # The category is the web app's to hold (kernel.consent): the policy doesn't change.
        for directive, source, _category in consent.entries(module):
            policy.allow(directive, source, module=module.id)

    owns_database = database is None
    db = database or built.database()
    worker = Worker(
        built.jobs,
        registry=registry,
        database=db,
        mailer=built.mailer,
        concurrency=config.jobs_concurrency,
        poll=config.jobs_poll_seconds,
        drain=config.jobs_drain_seconds,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            async with db.sessions() as session:
                await registry.on(session)
        except (SQLAlchemyError, OSError) as error:
            log.warning(
                "Couldn't read which modules are switched off (%s); taking every module "
                "MODULES allows as on until the database answers.",
                type(error).__name__,
            )
        stop = asyncio.Event()
        running = asyncio.create_task(worker.run(stop)) if config.jobs_in_web else None
        try:
            yield
        finally:
            if running is not None:
                stop.set()
                try:
                    await running
                except Exception as error:
                    log.warning("The web process's worker ended badly (%s).", type(error).__name__)
            if owns_database:
                await db.dispose()

    docs = {} if config.debug else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title=config.site_name, version=__version__, lifespan=lifespan, **docs)  # type: ignore[arg-type]
    app.state.config = config
    app.state.database = db
    app.state.modules = registry
    app.state.csp = policy
    app.state.limiter = RateLimiter(config.rate_limit_storage, enabled=config.rate_limit_enabled)
    app.state.client_ip_header = config.client_ip_header
    app.state.mailer = built.mailer
    app.state.worker = worker
    app.state.passwords = Passwords.from_config(config)
    app.state.breach_lookup = breach_lookup if breach_lookup is not None else ask_range
    #: Every permission the kernel or an installed module declares, with what
    #: it lets someone do and who declares it, in the manifests' order: the
    #: admin's Roles page lists them (K4.7), and an owner holds them all (14.8).
    app.state.permissions_listed = _permissions_listed(installed)
    app.state.declared_permissions = frozenset(item["key"] for item in app.state.permissions_listed)
    install_handlers(app)
    openapi.install(app)

    app.include_router(kernel_router, prefix="/api/kernel")
    app.include_router(admin_router, prefix="/api/kernel")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(sign_up_router, prefix="/api/auth")
    app.include_router(codes_router, prefix="/api/auth")
    app.include_router(resets_router, prefix="/api/auth")
    app.include_router(email_change_router, prefix="/api/auth")
    app.include_router(exports_router, prefix="/api/auth")
    app.include_router(password_change_router, prefix="/api/auth")
    app.include_router(totp_router, prefix="/api/auth")
    app.include_router(passkeys_router, prefix="/api/auth")
    app.include_router(devices_router, prefix="/api/auth")
    app.include_router(summary_router, prefix="/api/auth")
    app.include_router(factor_undo_router, prefix="/api/auth")
    app.include_router(roles_router, prefix="/api/auth")
    for module in installed:
        if module.router is not None:
            app.include_router(
                module.router,
                prefix=f"/api/{module.id}",
                dependencies=[Depends(require_module(module.id))],
            )
    # Last: the kernel's files, then every other address (kernel.shell).
    shell.install(app, built.public, app_shell)

    # Starlette runs the last added outermost.
    app.add_middleware(UnexpectedErrors)
    app.add_middleware(SessionCookies)
    app.add_middleware(
        BodyLimit,
        max_bytes=config.max_body_bytes,
        larger=_larger_bodies(installed, registry.on_cached),
    )
    origins = [config.site_url] + (config.cors_origins_list if config.debug else [])
    app.add_middleware(SameOriginWrites, origins=origins)
    if config.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins_list,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(WwwRedirect, site_url=config.site_url)
    app.add_middleware(
        SecurityHeaders,
        policy=policy,
        modules_on=registry.on_cached,
        refresh=lambda: registry.current(db.sessions),
        hsts_max_age=config.hsts_max_age,
        noindex=config.robots_noindex,
        https_site=config.site_url.strip().lower().startswith("https://"),
    )
    app.add_middleware(shell.HeadAsGet)  # every answer within, errors too, loses its body
    app.add_middleware(AccessLog)  # outermost: the whole request, the final status
    return app
