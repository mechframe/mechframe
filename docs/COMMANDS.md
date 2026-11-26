# Commands

Moved from CLAUDE.md on 2026-11-26, word for word, when it was leaned. CLAUDE.md keeps the commands used every session; this is every command, the generators among them, and when to run each.

From the repo root, in PowerShell. Python commands use the `python -m` form.

| What | Command |
| --- | --- |
| Python environment, first time | `py -3.12 -m venv .venv`, then `.venv\Scripts\Activate.ps1` |
| Install Python dependencies | `python -m pip install --require-hashes -r requirements.txt -r requirements-dev.txt` |
| Re-pin after editing a `.in` file | `python -m uv pip compile requirements.in --generate-hashes --universal --python-version 3.12 -o requirements.txt`, and the same for `requirements-dev.in` into `requirements-dev.txt` |
| Test Postgres | `docker compose up -d db`; or any local Postgres 16+ with a role that has CREATEDB and `TEST_DATABASE_URL` pointing at it (compose and CI call it `mechframe`; the owner's machine keeps its `devkit` role on port 55432) |
| Python tests | `python -m pytest` (add `-m "not db"` to run without Postgres) |
| Lint, format, types | `python -m ruff check .`, `python -m black .`, `python -m mypy` |
| Manifests against the schemas | `python -m tools.validate_schemas` |
| Migrations | `python -m harness.migrations upgrade` (also `downgrade`, `heads`, `history`, `current`), with `DATABASE_URL` set |
| Jobs worker, a process of its own | `python -m harness.worker`, with `JOBS_IN_WEB=false` on the web app (by default the web app runs one; decision 0035) |
| Audit Python dependencies | `python -m pip_audit --strict --require-hashes --disable-pip -r requirements.txt -r requirements-dev.txt` |
| Audit web dependencies, with the expiring allowlist (`tools/npm_audit_allow.json`, decision 0015) | `python -m tools.npm_audit` |
| Web install | `npm ci` |
| Web tests, lint, types, build | `npm test`, `npm run lint`, `npm run typecheck`, `npm run build` |
| Web coverage (85 % of lines, the contract's floor; CI's Web job runs it) | `npm run test:coverage` |
| End-to-end tests (Playwright 1.64.1, Chromium build 1248, axe), locally before each push | once on a new machine, `npx playwright install chromium` (`npm ci` doesn't fetch the browser); then `npm run build`, and `npm run e2e` with `TEST_DATABASE_URL` set; it starts its own `python -m harness.e2e` on a `mechframe_e2e` database made fresh each run, never one already running, and reads no `.env`. CI runs them on main's pushes, weekly and by hand (`e2e.yml`), never on a PR |
| Link the project skills for Claude Code | `python -m tools.link_skills` |
| Progress document and ledger rows, after editing `docs/progress.json` | `python -m tools.progress` (`--check` only reports) |
| Each theme's `tokens.css` and `tailwind.css`, after editing a `tokens.json` | `python -m tools.themes` (`--check` only reports) |
| Event payloads as JSON Schema, after declaring or changing one | `python -m tools.event_schemas` (`--check` only reports) |
| Every variable a site's host may set, `docs/HOST-VARIABLES.md`, after changing a kernel setting in `config.py`, a `module.json`'s env, settings or version, or `railway.ts` | `python -m tools.host_variables` (`--check` only reports; `tests/test_host_variables.py` fails while it's stale) |
| The committed OpenAPI specs and the web's API types, after changing a route or its answer | `python -m tools.openapi`, then `npm run api:types` (`--check` and `npm run api:check` only report; decision 0042) |
| The CLI: a new site, its modules, its edits, versions and advisories; the catalog (decisions 0047 and 0050) | After the pinned requirements, `python -m pip install --no-deps --no-build-isolation -e .` once, then `mechframe new <dir> [--recipe <id>]`, `mechframe add <id> --site <dir>`, `mechframe remove <id> --site <dir>`, `mechframe check --site <dir>` and `mechframe catalog` (`--check` only reports); or `python -m mechframe` with `$env:PYTHONPATH = "cli"` |
| A new site, kernel only (decision 0048) | `python -m mechframe new <dir> --name "<site name>" [--theme <name>]` with `cli` on the path; the folder must be empty or not there yet |
| The site's first owner, from its server (decision 0051) | `mechframe create-owner <email> --site <dir>`: runs the site's `python -m app.owner <email>` with its `.venv` and prints a one-time link to set the password; with an owner already, only an owner's own address gets one |
| The template's web package and lockfile, after a bump in the root's `package.json` | `python -m tools.site_template` (needs npm and the registry; `--check` only reports) |
| A new site made and run from nothing: venv, pins, lint, migrations, tests, `npm ci`, the build, `railway.ts`'s types, Playwright, `mechframe check` (CI's E2E workflow runs it; never on a PR) | `python -m tools.site_smoke` with `TEST_DATABASE_URL` set and npm on the path (`--keep` keeps the folder); about 5 minutes once pip's cache is warm |
| Brand check, before any PR that lifts code | `python -I "C:\DEV\VybeSite\vybesite\scripts\brand_check.py" "C:\DEV\AI-DevKit"` |
