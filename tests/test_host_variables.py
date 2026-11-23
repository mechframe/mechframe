"""The host-variables guidebook (`docs/HOST-VARIABLES.md`, `tools/host_variables.py`):
current with its sources, and missing no variable the code, the site template or a
module's manifest names."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools import host_variables

ROOT = Path(__file__).resolve().parent.parent

#: Python whose environment reads count: what runs on a site's host, and the harness.
READERS = [
    "kernel/backend/kernel",
    "modules",
    "templates/site/backend",
    "harness",
    "cli/mechframe",
]
#: On a line that reads the environment (`environ`, `getenv`): a quoted name, or a
#: constant handed to it, as in `environ.get(ALLOW)`.
_QUOTED = re.compile(r"""["']([A-Z][A-Z0-9_]{1,})["']""")
_HANDED = re.compile(r"""[(\[]\s*([A-Z][A-Z0-9_]*)\s*[,)\]]""")
#: A module-level constant holding a name: ALLOW = "MECHFRAME_ALLOW_SEED".
_CONSTANT = re.compile(
    r"""^([A-Z][A-Z0-9_]*)\s*(?::[^=\n]+)?=\s*["']([A-Z][A-Z0-9_]+)["']""", re.MULTILINE
)
#: ${NAME} or ${NAME:-default} in a shell line, and process.env.NAME in a config.
_SHELL = re.compile(r"\$\{([A-Z][A-Z0-9_]+)")
_NODE = re.compile(r"process\.env\.([A-Z][A-Z0-9_]+)")
#: Names the CLI keeps out of a child process's environment, not a site's variables.
NOT_THE_SITE_S = {"PYTHONPATH", "VIRTUAL_ENV"}


def _read_in(text: str) -> set[str]:
    constants = dict(_CONSTANT.findall(text))
    found: set[str] = set()
    for line in text.splitlines():
        if "environ" not in line and "getenv" not in line:
            continue
        found |= set(_QUOTED.findall(line))
        found |= {constants[name] for name in _HANDED.findall(line) if name in constants}
    return found


def _read_by_code() -> set[str]:
    found: set[str] = set()
    for folder in READERS:
        for path in (ROOT / folder).rglob("*.py"):
            if "tests" in path.parts or "node_modules" in path.parts:
                continue
            found |= _read_in(path.read_text(encoding="utf-8"))
    for dockerfile in (ROOT / "templates/site/Dockerfile",):
        found |= set(_SHELL.findall(dockerfile.read_text(encoding="utf-8")))
    for config in (ROOT / "playwright.config.ts", ROOT / "templates/site/web/playwright.config.ts"):
        found |= set(_NODE.findall(config.read_text(encoding="utf-8")))
    return found


def test_the_guidebook_is_current() -> None:
    assert host_variables.problems() == []
    for path, text in host_variables.outputs().items():
        assert (
            path.read_text(encoding="utf-8") == text
        ), f"{path.name} is stale: run python -m tools.host_variables"


def test_every_kernel_setting_is_described_and_nothing_else_is() -> None:
    from kernel.config import KernelConfig

    fields = {(field.alias or name).upper() for name, field in KernelConfig.model_fields.items()}
    described = {each.name for each in host_variables.KERNEL}
    assert fields - described == set(), "a kernel setting the guidebook doesn't describe"
    assert described - fields == set(), "a kernel entry with no setting behind it"


def test_every_variable_the_site_template_names_is_described() -> None:
    railway = host_variables.railway_values()
    assert railway, "railway.ts names no variables: its env block moved?"
    assert set(railway) - host_variables.documented() == set()
    env_example = (ROOT / "templates/site/.env.example").read_text(encoding="utf-8")
    named = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", env_example, re.MULTILINE))
    assert named - host_variables.documented() == set()


def test_every_variable_the_code_reads_is_described() -> None:
    read = _read_by_code() - NOT_THE_SITE_S
    # The scan finds a quoted name, a constant's, the Dockerfile's and a config's.
    assert {
        "RAILWAY_GIT_COMMIT_SHA",
        "MECHFRAME_ALLOW_SEED",
        "CAMPAIGNS_BOUNCE_IMAP_HOST",
        "PORT",
        "E2E_PORT",
    } <= read
    assert read - host_variables.documented() == set()


def test_the_scan_finds_a_name_however_it_s_read() -> None:
    text = (
        'TOKEN = "SHOP_TOKEN"\n'
        'a = os.environ.get("SHOP_URL")\n'
        "b = (os.environ if environ is None else environ).get(TOKEN)\n"
        'c = os.getenv("SHOP_REGION", "auto")\n'
        'd = os.environ["SHOP_KEY"]\n'
        'e = settings.get("NOT_AN_ENV_READ")\n'
    )
    assert _read_in(text) == {"SHOP_URL", "SHOP_TOKEN", "SHOP_REGION", "SHOP_KEY"}


def test_a_module_s_variables_and_settings_come_from_its_manifest() -> None:
    manifest = {
        "id": "shop",
        "version": "0.2.0",
        "status": "stable",
        "summary": "Products and a cart.",
        "env": [
            {"name": "SHOP_STRIPE_SECRET_KEY", "required": True, "description": "Stripe's key"},
        ],
        "settings": [
            {"key": "currency", "type": "string", "default": "usd", "description": "The currency"},
        ],
    }
    text = host_variables.render(modules=[host_variables.Module.of(manifest, planned=False)])
    assert "`SHOP_STRIPE_SECRET_KEY`" in text
    assert "Stripe's key" in text
    assert "`currency`" in text
    row = next(line for line in text.splitlines() if "`SHOP_STRIPE_SECRET_KEY`" in line)
    assert "Required" in row
    assert "Secret" in row


def test_a_variable_two_places_claim_is_a_problem() -> None:
    clash = {
        "id": "clash",
        "version": "0.1.0",
        "status": "experimental",
        "summary": "Claims a kernel variable.",
        "env": [{"name": "SECRET_KEY", "required": False, "description": "Mine now"}],
    }
    found = host_variables.problems(modules=[host_variables.Module.of(clash, planned=False)])
    assert any("SECRET_KEY" in each for each in found)


def test_the_check_fails_on_a_stale_guidebook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = tmp_path / "HOST-VARIABLES.md"
    stale.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(host_variables, "DOC", stale)
    assert host_variables.main(["--check"]) == 1
    assert host_variables.main([]) == 0
    assert host_variables.main(["--check"]) == 0
