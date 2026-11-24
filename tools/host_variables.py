"""Every variable a MechFrame site reads from its host, in one guidebook.

    python -m tools.host_variables           # rewrite docs/HOST-VARIABLES.md
    python -m tools.host_variables --check   # exit 1 if it's stale or a variable is undescribed

The guidebook is for whoever puts a site on Railway or another host: what to type
before the first deploy, what each feature needs, what Railway sets by itself, and
every module's own variables. It's made from:

- the kernel's settings (`kernel/backend/kernel/config.py`), each described here in
  `KERNEL`: their defaults and allowed values are read from the settings themselves;
- the variables read outside those settings (`PROCESS`), and those only tests and
  local runs read (`LOCAL`), which never go on a live host;
- each module's `module.json`: its `env`, which the host holds, and its `settings`,
  which the site's admin holds (listed apart), the planned `modules/_<id>/`
  scaffolds among them, so the guidebook grows as modules are built;
- the site template's `.railway/railway.ts`, for what Railway sets by itself.

Edit those, never the guidebook, then run this tool. `tests/test_host_variables.py`
fails while the guidebook is stale, when a kernel setting has no description here,
and when the code, the template or a manifest names a variable it doesn't list.
"""

from __future__ import annotations

import json
import re
import sys
import typing
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import harness  # noqa: F401  (importing it puts the kernel's backend on sys.path)

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "HOST-VARIABLES.md"
MODULES = ROOT / "modules"
RAILWAY = ROOT / "templates" / "site" / ".railway" / "railway.ts"

#: How much a site needs a variable, in the order the guidebook explains them.
NEEDS = {
    "required": "Required",
    "recommended": "Recommended",
    "mail": "For mail",
    "storage": "For storage",
    "ai": "For the AI",
    "errors": "For error reports",
    "optional": "Optional",
    "tuning": "Tuning",
    "host": "The host gives it",
}

#: The kernel's groups, in order: (key, heading, what the group is).
GROUPS = [
    (
        "site",
        "The site itself",
        "Every site sets these. Outside `DEBUG`, the site refuses to start while `SITE_URL`, "
        "`SECRET_KEY` or `ENCRYPTION_KEYS` is missing, short or a placeholder, and says which.",
    ),
    (
        "edge",
        "Behind the host's edge",
        "How the site sits behind Railway's proxy (or another host's), and what it tells "
        "browsers and search engines.",
    ),
    (
        "accounts",
        "Accounts and passwords",
        "Who may make an account, and how hard each password is hashed.",
    ),
    (
        "mail",
        "Mail",
        "Nothing set sends nothing (sign-in links and notices are only logged). Set in part, "
        "the site refuses to start. SMTP comes first: with `SMTP_HOST` set, mail goes through "
        "any provider's SMTP. Only on a host that blocks outbound SMTP, such as Railway's Hobby "
        "plan, leave `SMTP_HOST` blank and set `RESEND_API_KEY`.",
    ),
    (
        "storage",
        "Storage",
        "An S3-compatible store, Cloudflare R2 on a live site. All blank: storage is off, and "
        "media's uploads answer 503. Set in part, the site refuses to start: the four private "
        "ones go together, and the public pair together.",
    ),
    (
        "jobs",
        "Background jobs",
        "The jobs worker sends mail, publishes what's scheduled and runs each module's jobs. "
        "By default it runs inside the web process: one service.",
    ),
    (
        "ai",
        "The AI's writing help",
        "Write with AI in every editor. A key an admin saves in Settings → AI wins over the "
        "host's; with neither, no AI shows.",
    ),
    (
        "content",
        "Search, consent and the audit log",
        "How site search reads words, what waits for a visitor's consent, and how long the "
        "audit log keeps its entries.",
    ),
    (
        "limits",
        "Rate limits",
        "Every form and sign-in is rate-limited per visitor, by the address `CLIENT_IP_HEADER` "
        "names.",
    ),
    (
        "errors",
        "Errors and logs",
        "Error reports go to Sentry once `SENTRY_DSN` is set; logs go to the host's log view.",
    ),
    (
        "tuning",
        "Database and process tuning",
        "The kernel's defaults suit a small site on one service. Change these only with a "
        "reason.",
    ),
]


@dataclass(frozen=True)
class Var:
    """One variable the guidebook describes."""

    name: str
    group: str
    need: str
    about: str
    secret: bool = False
    #: Shown instead of the setting's default (a local-only value, say).
    default: str | None = None
    #: Shown instead of what `railway.ts` says, where something else sets it.
    railway: str | None = None
    #: Read from the process's environment, never `.env` (which feeds only the
    #: kernel's settings).
    env_only: bool = False


#: Every kernel setting, by its variable's name (KernelConfig's field, upper-cased).
KERNEL = [
    # --- the site itself ---
    Var(
        "SITE_URL",
        "site",
        "required",
        "The site's own address, such as `https://www.example.org`: links in mail, the "
        "sitemap and the same-origin check use it. Outside `DEBUG` it must be https and not "
        "a placeholder or local address.",
    ),
    Var(
        "SECRET_KEY",
        "site",
        "required",
        "Signs links in mail and other signed values: at least 43 random characters. Make "
        'one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Changing it '
        "voids every link already sent.",
        secret=True,
    ),
    Var(
        "ENCRYPTION_KEYS",
        "site",
        "required",
        "Fernet keys, comma-separated, newest first: stored secrets (provider keys, "
        "authenticator secrets, newsletter links) are sealed with the first and opened with "
        'any. Make one with `python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"`. To rotate, put a new key in front and keep '
        "the old one behind it: what the old key sealed opens only while it's listed, so "
        "removing it makes that unreadable.",
        secret=True,
    ),
    Var(
        "DATABASE_URL",
        "site",
        "required",
        "The Postgres 16+ database, as `postgresql://user:password@host:port/name`. On Railway "
        "it's a reference to the `postgres` service beside the site.",
        secret=True,
        default="a local database (development only)",
    ),
    Var(
        "SITE_NAME",
        "site",
        "recommended",
        "The site's name, in titles, mail and the admin. `mechframe new` writes it into "
        "`railway.ts`.",
    ),
    Var(
        "DEBUG",
        "site",
        "optional",
        "`true` only for local development: it skips the start's safety checks and loosens "
        "same-origin rules. Never `true` on a live host.",
    ),
    Var(
        "MODULES",
        "site",
        "optional",
        "The modules this deploy may use, comma-separated, or `*` for every module the site "
        "has. A name the site doesn't have stops the start, so a typo never leaves a module "
        "off silently. The admin can still switch any of them off at runtime.",
    ),
    Var(
        "WEB_DIST",
        "site",
        "optional",
        "The built web app's folder, whose `index.html` every public address answers with. "
        "The site's Dockerfile sets it (`/app/web/dist`); blank serves the kernel's minimal "
        "page with no scripts.",
        railway="Set by the Dockerfile",
    ),
    # --- behind the edge ---
    Var(
        "CLIENT_IP_HEADER",
        "edge",
        "recommended",
        "The one header the host's edge writes the visitor's address into: `X-Real-IP` on "
        "Railway, `Fly-Client-IP` on Fly.io, `CF-Connecting-IP` behind Cloudflare. Blank, every "
        "visitor counts as the edge's address, so they all share one rate limit (the start "
        "warns). Blank for local runs with no proxy.",
    ),
    Var(
        "CORS_ORIGINS",
        "edge",
        "optional",
        "Other sites allowed to call this one's API from a browser, comma-separated. Blank "
        "for none, which suits a site whose web app it serves itself.",
    ),
    Var(
        "HSTS_MAX_AGE",
        "edge",
        "optional",
        "Strict-Transport-Security's max-age, in seconds. `0` sends none. Set `31536000` once "
        "the domain is settled and every part of it is on https.",
    ),
    Var(
        "ROBOTS_NOINDEX",
        "edge",
        "optional",
        "`true` on a copy no search engine should list, such as staging. Never on the live "
        "site.",
    ),
    Var(
        "MAX_BODY_BYTES",
        "edge",
        "tuning",
        "The largest request body accepted, in bytes; larger is 413. Uploads go to storage "
        "and aren't held to it.",
    ),
    # --- accounts ---
    Var(
        "SIGN_UP_MODE",
        "accounts",
        "optional",
        "Who may make an account: `open`, `invite` or `closed`. It's only the first value: "
        "once the site is up, Admin → Settings holds it.",
    ),
    Var(
        "ARGON2_MEMORY_KIB",
        "accounts",
        "tuning",
        "The memory each password hash uses, in KiB; never below OWASP's 19 MiB. Raise it "
        "where the host has memory to spare.",
    ),
    Var("ARGON2_TIME_COST", "accounts", "tuning", "Passes over that memory for each hash."),
    Var("ARGON2_LANES", "accounts", "tuning", "Lanes (parallelism) in each hash."),
    Var(
        "ARGON2_CONCURRENCY",
        "accounts",
        "tuning",
        "How many hashes run at once; each holds `ARGON2_MEMORY_KIB` while it runs.",
    ),
    # --- mail ---
    Var(
        "MAIL_FROM",
        "mail",
        "mail",
        "The one bare address every mail comes from, such as `hello@example.org`: no name or "
        "angle brackets. Required once SMTP or Resend is set.",
    ),
    Var(
        "MAIL_FROM_NAME",
        "mail",
        "optional",
        "The name shown beside `MAIL_FROM`; `SITE_NAME` while blank.",
    ),
    Var(
        "SMTP_HOST",
        "mail",
        "mail",
        "The mail provider's SMTP server. Setting it chooses SMTP.",
    ),
    Var(
        "SMTP_PORT",
        "mail",
        "mail",
        "`465` for implicit TLS, `587` (or any other) for STARTTLS.",
    ),
    Var(
        "SMTP_USERNAME",
        "mail",
        "mail",
        "The SMTP login, usually the sending mailbox. Set with `SMTP_PASSWORD` or neither.",
    ),
    Var(
        "SMTP_PASSWORD",
        "mail",
        "mail",
        "The SMTP login's password.",
        secret=True,
    ),
    Var(
        "RESEND_API_KEY",
        "mail",
        "mail",
        "Resend's API key, only on a host that blocks outbound SMTP, with `SMTP_HOST` blank. "
        "With both set, SMTP wins.",
        secret=True,
    ),
    # --- storage ---
    Var(
        "STORAGE_ENDPOINT_URL",
        "storage",
        "storage",
        "The store's endpoint: on R2, `https://<account>.r2.cloudflarestorage.com` (a bucket "
        "pasted onto it is dropped).",
    ),
    Var(
        "STORAGE_ACCESS_KEY_ID",
        "storage",
        "storage",
        "The access key's ID (R2: an API token's S3 access key ID).",
    ),
    Var(
        "STORAGE_SECRET_ACCESS_KEY",
        "storage",
        "storage",
        "The access key's secret.",
        secret=True,
    ),
    Var(
        "STORAGE_BUCKET",
        "storage",
        "storage",
        "The private bucket: its files are reached only through signed links.",
    ),
    Var(
        "STORAGE_PUBLIC_BUCKET",
        "storage",
        "storage",
        "The public bucket, served to anyone at `STORAGE_PUBLIC_URL`: media's images live "
        "here. Never the same bucket as `STORAGE_BUCKET`. Set with `STORAGE_PUBLIC_URL` or "
        "neither.",
    ),
    Var(
        "STORAGE_PUBLIC_URL",
        "storage",
        "storage",
        "The public bucket's address (R2: its custom domain), https outside `DEBUG`.",
    ),
    Var(
        "STORAGE_REGION",
        "storage",
        "tuning",
        "The store's region; R2 takes `auto`.",
    ),
    Var(
        "STORAGE_MAX_BYTES",
        "storage",
        "tuning",
        "The largest file the kernel stores, in bytes.",
    ),
    # --- jobs ---
    Var(
        "JOBS_IN_WEB",
        "jobs",
        "optional",
        "`true` runs the worker inside the web process. A site that runs its own worker "
        "service (`python -m app.worker`, for heavy jobs) sets `false` on the web service.",
    ),
    Var("JOBS_CONCURRENCY", "jobs", "tuning", "How many jobs one worker runs at once."),
    Var("JOBS_POLL_SECONDS", "jobs", "tuning", "How often a worker looks for due jobs."),
    Var(
        "JOBS_DRAIN_SECONDS",
        "jobs",
        "tuning",
        "On a redeploy, how long running jobs get to finish before they're left to their "
        "leases and run again later.",
    ),
    # --- the AI ---
    Var(
        "ANTHROPIC_API_KEY",
        "ai",
        "ai",
        "The Anthropic API key Write with AI uses, from the Anthropic console. Blank keeps "
        "the AI off until an admin saves a key in Settings → AI, which wins over this one.",
        secret=True,
    ),
    Var(
        "ANTHROPIC_MODEL",
        "ai",
        "optional",
        "The model every writing task asks for, until an admin saves one in Settings → AI.",
    ),
    Var(
        "AI_RATE_LIMIT",
        "ai",
        "optional",
        "The AI calls one person may make, every button sharing it: a count, then a period "
        "(`s`, `m`, `h` or `d`).",
    ),
    # --- search, consent, audit ---
    Var(
        "SEARCH_LANGUAGE",
        "content",
        "optional",
        "The language site search reads words in (`simple` stems nothing). After changing "
        "it, run the job `kernel.search_reindex` once.",
    ),
    Var(
        "CONSENT_MODE",
        "content",
        "optional",
        "`ask` holds a script or player a module puts in a category other than `necessary` "
        "(analytics, marketing, media) until the visitor allows it; `off` loads everything at "
        "once, for a site with nothing to ask.",
    ),
    Var(
        "AUDIT_KEEP_DAYS",
        "content",
        "optional",
        "Days an audit-log entry is kept before the nightly prune removes it.",
    ),
    # --- rate limits ---
    Var(
        "RATE_LIMIT_ENABLED",
        "limits",
        "tuning",
        "`false` turns every rate limit off: for tests, never a live site.",
    ),
    Var(
        "RATE_LIMIT_STORAGE",
        "limits",
        "tuning",
        "Where the counts live: `memory://` for one process; a `redis://` address once the "
        "site runs more than one.",
    ),
    # --- errors and logs ---
    Var(
        "SENTRY_DSN",
        "errors",
        "errors",
        "Sentry's DSN for the project that collects this site's errors. Blank sends none.",
    ),
    Var(
        "SENTRY_ENVIRONMENT",
        "errors",
        "optional",
        "The environment Sentry files errors under; `production` while blank.",
    ),
    Var(
        "LOG_FORMAT",
        "errors",
        "optional",
        "`json` for the host's log view, `text` for reading locally.",
    ),
    Var("LOG_LEVEL", "errors", "optional", "The least severe level logged."),
    # --- tuning ---
    Var("DB_POOL_SIZE", "tuning", "tuning", "Database connections each process keeps open."),
    Var(
        "DB_MAX_OVERFLOW",
        "tuning",
        "tuning",
        "Extra connections a busy process may open beyond the pool.",
    ),
    Var(
        "MODULES_CACHE_SECONDS",
        "tuning",
        "tuning",
        "How long each process trusts the list of modules switched off in the admin; `0` "
        "reads it on every request.",
    ),
]

#: Read by the site's processes outside the kernel's settings.
PROCESS = [
    Var(
        "PORT",
        "edge",
        "host",
        "The port the site listens on. Railway and most hosts give it; the Dockerfile falls "
        "back to `8000`.",
        default="`8000`",
        env_only=True,
    ),
    Var(
        "FORWARDED_ALLOW_IPS",
        "edge",
        "recommended",
        "Whose `X-Forwarded-*` headers the server trusts, for the request's scheme and the "
        "visitor's address. `*` on Railway, whose edge has no fixed addresses and is the only "
        "way in; the edge's addresses on a host where they're known; `127.0.0.1` locally.",
        default="`127.0.0.1`",
        env_only=True,
    ),
    Var(
        "RAILWAY_GIT_COMMIT_SHA",
        "errors",
        "host",
        "The deployed commit, which Railway gives each deploy: Sentry files errors under it "
        "as the release.",
        default="",
        env_only=True,
    ),
]

#: Read only by tests, local runs and the CLI: never on a live host.
LOCAL = [
    Var(
        "MECHFRAME_ALLOW_SEED",
        "local",
        "optional",
        "`1` for one run allows seeding demo rows (`mechframe seed`). Never in `.env`, "
        "`railway.ts` or a live host's variables.",
    ),
    Var(
        "TEST_DATABASE_URL",
        "local",
        "optional",
        "A Postgres role with CREATEDB that the test suites make throwaway databases with.",
    ),
    Var(
        "HARNESS_TEST_SUPPORT",
        "local",
        "optional",
        "`1` mounts the harness's test-only routes (its mail box and clock). Only the test "
        "runs set it.",
    ),
    Var("E2E_PORT", "local", "optional", "The port the end-to-end tests' server uses."),
    Var("E2E_PYTHON", "local", "optional", "The Python the end-to-end tests start it with."),
    Var("CI", "local", "optional", "Set by CI: Playwright refuses a `test.only` there."),
]

#: What a module needs of the kernel's variables, where it has none of its own.
LEANS_ON = {
    "media": "Uploads need storage with its public pair, `STORAGE_PUBLIC_BUCKET` and "
    "`STORAGE_PUBLIC_URL`; until they're set, uploads answer 503 `media.storage_off`.",
    "blog": "Covers come from media, so storage too; Write with AI needs `ANTHROPIC_API_KEY` "
    "or a key saved in Settings → AI.",
    "contact": "Its notices to the Inbox's readers go by mail too, so mail (`MAIL_FROM` with "
    "`SMTP_HOST` or `RESEND_API_KEY`).",
    "campaigns": "Every confirmation and newsletter goes by the kernel's mail (`MAIL_FROM` "
    "with `SMTP_HOST` or `RESEND_API_KEY`). Nothing sends until its postal address is set "
    "in Settings → Newsletter.",
    "pages": "Write with AI needs `ANTHROPIC_API_KEY` or a key saved in Settings → AI.",
}

_SECRET_WORDS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "PRIVATE_KEY")


def _is_secret(name: str) -> bool:
    return any(word in name for word in _SECRET_WORDS)


@dataclass(frozen=True)
class Module:
    """A module's manifest, as the guidebook reads it."""

    id: str
    version: str
    status: str
    summary: str
    planned: bool
    env: list[dict[str, Any]] = field(default_factory=list)
    settings: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def of(cls, manifest: Mapping[str, Any], *, planned: bool) -> Module:
        return cls(
            id=str(manifest["id"]),
            version=str(manifest.get("version", "")),
            status=str(manifest.get("status", "")),
            summary=str(manifest.get("summary", "")),
            planned=planned,
            env=list(manifest.get("env", [])),
            settings=list(manifest.get("settings", [])),
        )


def all_modules() -> list[Module]:
    """Every module in `modules/`, built ones first, then the planned scaffolds."""
    found = []
    for path in sorted(MODULES.glob("*/module.json")):
        folder = path.parent.name
        if folder == "_template":
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        found.append(Module.of(manifest, planned=folder.startswith("_")))
    return sorted(found, key=lambda each: (each.planned, each.id))


def railway_values(path: Path | None = None) -> dict[str, str]:
    """Each variable the site template's `railway.ts` names, with its value as written."""
    text = (path or RAILWAY).read_text(encoding="utf-8")
    start = text.index("env: {")
    end = text.index("\n    },", start)
    return dict(re.findall(r"^\s+([A-Z][A-Z0-9_]*):\s*(.+?),\s*$", text[start:end], re.MULTILINE))


def documented(found: Iterable[Module] | None = None) -> set[str]:
    """Every variable name the guidebook lists."""
    names = {each.name for each in [*KERNEL, *PROCESS, *LOCAL]}
    for module in all_modules() if found is None else found:
        names |= {str(each["name"]) for each in module.env}
    return names


def problems(modules: list[Module] | None = None) -> list[str]:
    """What's wrong with the sources, by name: a name claimed twice, an unknown need
    or group, a module named in `LEANS_ON` that isn't there, a variable it names
    that the guidebook doesn't list."""
    found = all_modules() if modules is None else modules
    wrong = []
    seen: dict[str, str] = {}
    groups = {key for key, _, _ in GROUPS} | {"local"}
    for where, each in [("kernel", v) for v in [*KERNEL, *PROCESS]] + [("local", v) for v in LOCAL]:
        if each.name in seen:
            wrong.append(f"{each.name} is listed twice.")
        seen[each.name] = where
        if each.need not in NEEDS:
            wrong.append(f"{each.name}'s need {each.need!r} isn't one of {', '.join(NEEDS)}.")
        if each.group not in groups:
            wrong.append(f"{each.name}'s group {each.group!r} isn't a group.")
    for module in found:
        for declared in module.env:
            name = str(declared["name"])
            if name in seen:
                wrong.append(f"{name} is claimed by both {seen[name]} and {module.id}.")
            seen[name] = module.id
    ids = {module.id for module in found}
    for module_id, words in LEANS_ON.items():
        if module_id not in ids:
            wrong.append(f"LEANS_ON names {module_id}, which isn't a module.")
        for name in re.findall(r"`([A-Z][A-Z0-9_]+)`", words):
            if name not in seen:
                wrong.append(f"LEANS_ON's {module_id} names {name}, which isn't listed.")
    return wrong


# --- rendering ---------------------------------------------------------------------------------


def _code(value: str) -> str:
    return f"`{value}`" if value else "blank"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _choices(values: list[Any]) -> str:
    shown = [f"`{value}`" for value in values]
    if len(shown) > 8:
        return f"One of {len(shown)} values, such as {', '.join(shown[:4])} or {shown[4]}."
    return f"One of {', '.join(shown[:-1])} or {shown[-1]}." if len(shown) > 1 else ""


def _bounds(metadata: list[Any]) -> str:
    low = high = None
    for each in metadata:
        low = getattr(each, "ge", low)
        high = getattr(each, "le", high)
    if low is not None and high is not None:
        return f"{low} to {high}."
    if low:
        return f"At least {low}."
    if high is not None:
        return f"At most {high}."
    return ""


def _kernel_facts() -> dict[str, tuple[str, str]]:
    """Each kernel variable's default, and what values it allows."""
    from pydantic import SecretStr

    from kernel.config import KernelConfig

    facts = {}
    for name, info in KernelConfig.model_fields.items():
        default = info.default
        if isinstance(default, SecretStr):
            shown = ""
        elif isinstance(default, bool):
            shown = "true" if default else "false"
        else:
            shown = str(default)
        allowed = ""
        if typing.get_origin(info.annotation) is typing.Literal:
            allowed = _choices(list(typing.get_args(info.annotation)))
        else:
            allowed = _bounds(list(info.metadata))
        facts[(info.alias or name).upper()] = (shown, allowed)
    return facts


def _on_railway(var: Var, railway: Mapping[str, str]) -> str:
    if var.railway is not None:
        return var.railway
    value = railway.get(var.name)
    if value is None:
        return "Railway gives it" if var.need == "host" else "Not in `railway.ts`"
    if value == "preserve()":
        return "Only if you change it" if var.need in ("optional", "tuning") else "You type it"
    if value.startswith("db."):
        return "Railway's Postgres"
    literal = value.strip("\"'")
    if literal.startswith("__") and literal.endswith("__"):
        return "Set by `mechframe new`"
    return f"Set: `{literal}`"


def _need(var: Var) -> str:
    marks = [NEEDS[var.need], *(["Secret"] if var.secret else [])]
    marks += ["Environment only"] if var.env_only else []
    return " · ".join(marks)


def _kernel_table(
    names: list[Var], facts: Mapping[str, tuple[str, str]], railway: Mapping[str, str]
) -> list[str]:
    lines = [
        "| Variable | Needed | Default | On Railway | What it's for |",
        "| --- | --- | --- | --- | --- |",
    ]
    for var in names:
        shown, allowed = facts.get(var.name, ("", ""))
        default = _code(shown) if var.default is None else (var.default or "none")
        about = f"{var.about} {allowed}".strip()
        lines.append(
            f"| `{var.name}` | {_need(var)} | {_cell(default)} "
            f"| {_on_railway(var, railway)} | {_cell(about)} |"
        )
    return lines


def _setting_default(value: Any) -> str:
    if isinstance(value, bool):
        return "`true`" if value else "`false`"
    if value in ("", None):
        return "blank"
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False)
        return f"`{text}`" if len(text) <= 40 else "a list (see the module's MODULE.md)"
    return f"`{_cell(str(value))}`"


def _module_section(module: Module) -> list[str]:
    title = f"### `{module.id}` {module.version}"
    title += " (planned, not built yet)" if module.planned else f" ({module.status})"
    lines = [title, "", _cell(module.summary), ""]
    if module.env:
        lines += [
            "| Variable | Needed | On Railway | What it's for |",
            "| --- | --- | --- | --- |",
        ]
        for each in module.env:
            name = str(each["name"])
            need = "Required" if each.get("required") else "Optional"
            need += " · Secret" if _is_secret(name) else ""
            need += " · Environment only"
            lines.append(
                f"| `{name}` | {need} | You type it (`mechframe add` lists it) "
                f"| {_cell(str(each['description']))} |"
            )
        lines.append("")
    else:
        lines += ["No host variables of its own.", ""]
    if module.id in LEANS_ON:
        lines += [f"**From the kernel:** {LEANS_ON[module.id]}", ""]
    if module.settings:
        lines += [
            "Set in the site's admin (Admin → Settings), not on the host:",
            "",
            "| Setting | Type | Default | What it's for |",
            "| --- | --- | --- | --- |",
        ]
        for each in module.settings:
            lines.append(
                f"| `{each['key']}` | {each.get('type', '')} | {_setting_default(each.get('default'))} "
                f"| {_cell(str(each.get('description', '')))} |"
            )
        lines.append("")
    return lines


_INTRO = """\
# Host variables: the guidebook

Every variable a site built with MechFrame reads from its host, and what each module
needs, so a site can go live on Railway or another host without guessing. On Railway
they're the web service's **Variables**; elsewhere, the host's environment variables.
Locally, the site's `.env` holds the kernel's (copy `.env.example`). `.env` feeds only
the kernel's settings: a variable marked **Environment only** (each module's own, and
the server's) is read from the process's environment, so for a local run export it in
the shell before starting the app (`$env:NAME = "value"` in PowerShell). On a host
every variable is in the environment, so there it makes no difference.

> Made by `python -m tools.host_variables` from the kernel's settings
> (`kernel/backend/kernel/config.py`), each module's `module.json` and the site
> template's `.railway/railway.ts`. Don't edit it by hand: change those and run the
> tool. `tests/test_host_variables.py` fails while it's stale, and when the code reads
> a variable this page doesn't list.

**Never commit a value.** Secrets are typed into the host by the site's owner, never
written into `.env.example`, `railway.ts` or chat.

## What "Needed" means

| Needed | Meaning |
| --- | --- |
| Required | The site won't start without it outside `DEBUG`, or can't reach its database. |
| Recommended | It starts without it, but works badly: set it. |
| For mail, For storage, For the AI, For error reports | Needed only for that feature; each group says which go together. |
| Optional | A behaviour with a sensible default. |
| Tuning | A default to change only with a reason. |
| The host gives it | Railway (and most hosts) set it; you don't. |
| Secret | Typed into the host only, never committed or pasted into chat. |
| Environment only | Read from the process's environment, never `.env`: export it for a local run. |

## Putting a site on Railway, step by step

1. **Make the site and add its modules:** `mechframe new <dir> --name "<site name>"`, then
   `mechframe add <id> --site <dir>` for each module. Each `add` lists the module's
   variables in the site's `.env.example` and `.railway/railway.ts`.
2. **Apply Railway as code** from the site's folder: `npm ci`, `railway init --name <project>`
   (or `railway link`), `railway config plan`, then `railway config apply`. This makes the
   `web` service and its `postgres`, and sets every variable marked "Set" or "Railway's
   Postgres" below. A variable on `web` that `railway.ts` doesn't list is deleted by the
   next apply: add new ones to the file first. The site's `README.md` ("Deploying") has
   the rest, Windows included.
3. **Connect `web` to the site's repo** (Settings → Source) and type the three it can't
   start without into its Variables: `SITE_URL`, `SECRET_KEY` and `ENCRYPTION_KEYS`.
4. **Turn on each feature the site uses:** mail, storage, the AI and error reports. Each
   group below says which variables go together; one set in part stops the start and
   names what's missing.
5. **Type each module's own variables** (its section below).
6. **Deploy.** Migrations run before the new deploy takes traffic, and Railway checks
   `/api/kernel/health`. Then make the first owner in the service's shell (`railway ssh`,
   then `python -m app.owner <email>`), and fill each module's admin settings.

## On another host

The same variables, with what Railway did for you done by hand:

- **`DATABASE_URL`:** your Postgres 16+, with a role that owns the site's database.
- **`PORT`:** most hosts give it; otherwise the server listens on 8000.
- **`CLIENT_IP_HEADER` and `FORWARDED_ALLOW_IPS`:** the header your edge writes the
  visitor's address into, and the addresses that edge connects from (`*` only when the
  edge is the only way in).
- **Migrations before traffic:** run `python -m app.migrations upgrade` before each new
  version starts, and stop the deploy if it fails.
- **The health check:** `/api/kernel/health`.

## The kernel's variables
"""


def render(modules: list[Module] | None = None) -> str:
    """The guidebook, from the sources."""
    found = all_modules() if modules is None else modules
    facts = _kernel_facts()
    railway = railway_values()
    lines = [_INTRO]
    for key, heading, about in GROUPS:
        names = [var for var in [*KERNEL, *PROCESS] if var.group == key]
        lines += [f"### {heading}", "", about, ""]
        lines += _kernel_table(names, facts, railway)
        lines.append("")
    lines += [
        "## The modules' variables",
        "",
        "Each module's own host variables, from its `module.json`, and the settings its admin "
        "page holds. A planned module's are as its scaffold has them so far; they grow as it's "
        "built.",
        "",
    ]
    for module in found:
        lines += _module_section(module)
    lines += [
        "## Never on a live host",
        "",
        "Read only by tests, local runs and the CLI. None of these belong in a live host's "
        "variables, `.env.example` or `railway.ts`, and `DEBUG` stays `false` there.",
        "",
        "| Variable | What it's for |",
        "| --- | --- |",
    ]
    lines += [f"| `{var.name}` | {_cell(var.about)} |" for var in LOCAL]
    secrets = sorted(
        {var.name for var in [*KERNEL, *PROCESS] if var.secret}
        | {
            str(each["name"])
            for module in found
            for each in module.env
            if _is_secret(str(each["name"]))
        }
    )
    lines += [
        "",
        "## Every secret, in one list",
        "",
        "Typed into the host by the site's owner, and rotated by typing a new value; for "
        "`ENCRYPTION_KEYS`, the new key goes in front and the old one stays behind it.",
        "",
        ", ".join(f"`{name}`" for name in secrets) + ".",
        "",
    ]
    return "\n".join(lines)


def outputs() -> dict[Path, str]:
    return {DOC: render()}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    wrong = problems()
    if wrong:
        for each in wrong:
            print(each, file=sys.stderr)
        return 1
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        if "--check" in args:
            stale.append(path)
            continue
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}.")
    if stale:
        for path in stale:
            print(f"{path.name} is stale: run python -m tools.host_variables", file=sys.stderr)
        return 1
    if "--check" in args:
        print("docs/HOST-VARIABLES.md is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
