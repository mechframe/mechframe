# CLAUDE.md: MechFrame

The binding directives are in `C:\DEV\CLAUDE.md` and `C:\DEV\DIRECTIVES.md`, which Claude Code loads for every folder under `C:\DEV`. This file is the project map. Where the two differ, this file wins. `AGENTS.md` holds the same text for other agents.

## Identity

- **What:** MechFrame, a library of reusable website modules (auth, blog, chat, payments, community, media and more) that any AI agent copies into a site's repo and wires together from a short brief.
- **Owner:** VybeCode Software (VybeCod.ing / Vibrant Mindz).
- **Not:** a hosted platform, a WordPress-style CMS, or a package registry. Modules are copied in at build time (decision 0002).
- **Path:** `C:\DEV\AI-DevKit`. **Remote:** `https://github.com/mechframe/mechframe` (decision 0034), **public** (decision 0011). Never commit secrets, client material or private notes; private notes go in `docs/private/` (gitignored).
- **The contract:** `SPEC.md`. Every module, the kernel and the CLI follow it. Read the sections you touch before every change.

## Current state (2026-11-27)

- **v1.0 is at 80%** (49 of 61 steps). Nothing is deployed. **The kernel is done**, K0 to K5 (#1 to #96), with K2's steps 9 to 11 waiting until the site needs them (decision 0029); `mechframe upgrade kernel` is in (#111, #114; decision 0053).
- **Hooks:** 1 to 8 (#97 to #110, decision 0052) and 11, item references (`kernel/backend/kernel/refs.py`, #153, decision 0072). Entitlements and profile tabs wait until just before Vibrant Mindz's step 5 and wave 2b.
- **Modules built:** media 0.1.4, pages 0.1.1, blog 0.1.7, contact 0.1.2, embeds 0.1.1, campaigns 0.1.1, discography 0.1.3, audio-player 0.1.2, featured 0.1.0 and social 0.1.0. Each one's `MODULE.md` and `CHANGELOG.md` say what it does, and `catalog.json` indexes them. The Vibrant Mindz scaffolds wait as `modules/_<id>/`.
- **The first real site** is the new Vibrant Mindz site (`docs/plans/vibrant-mindz-module-plan.md`). It's built in its own session (`C:\DEV\VM Website`) from MechFrame's `main`. Its checks against the boards send items here, with the owner's calls relayed.
- **Next, main lane** (`dev plans/2026-11-27-next-session-m4m-board-check.md`): VM Website's board check of #165, then step 1's close; step 2's close (all four tests, after the owner's iPhone Safari check); the flaky axe test diagnosed; and step 3's order and lanes, the owner's call.
- **Side lane:** discography 0.1.4 (`dev plans/2026-11-27-side-lane-m13-discography-0-1-4.md`), in a worktree: K11's `QuietLink`, its long e2e test within 30 seconds, and the site's Admin › Music differences. Two lanes run at once ("Two lanes", below).
- **After v1.0:** the module roadmap and ten contract hooks (decision 0018, `docs/plans/module-roadmap.md`), and VybeSite's page builder for `pages` (the owner, 2026-11-21).
- The state PR by PR is in `docs/archive/` (to 2026-11-21, then to 2026-11-26). Next steps, blockers and warnings live in `docs/HANDOFF.md`.

## Last Completed Task

2026-11-26, about 07:00 Eastern, to 2026-11-27, about 13:40 (Claude Code, the owner's machine, the owner on Remote Control at times): session M4l, the main lane.

- **#164:** `CLAUDE.md` and `AGENTS.md` leaned, 176 lines to 133, word for word into `docs/COMMANDS.md`, `docs/REPO-MAP.md` and `docs/archive/`; the ledger README's check step.
- **#165, VM Website Dev 22's ask:** the kit's last differences from the boards (R1 to R3, R6 to R9, K9 to K12, and the new `QuietLink`); blog 0.1.7's Draw a cover (C1 to C3); audio-player 0.1.2; campaigns 0.1.1, with Set aside named by its words. Decision 0040 amended a third time.
- **The side lane** landed #163 (discography 0.1.3), with the fix for the test #164 broke.

## Read order

1. `KICKOFF.md` (first sessions) or the newest `dev plans\*-next-session-*.md` (later sessions). It is the job.
2. `docs/HANDOFF.md`: state, next steps, blockers.
3. `SPEC.md`: the sections the job touches.
4. `docs/decisions/`: why things are the way they are.
5. `docs/private/inventory.md` (on the owner's machine only, not in git): where each piece can be lifted from in `C:\DEV`.

## Stack (decision 0001)

Python 3.12+, FastAPI, Pydantic v2 (strict), async SQLAlchemy 2 + asyncpg, Postgres 16+, Alembic with one branch per module; auth by argon2-cffi, pyotp and webauthn (passkeys, decision 0028); nh3 for HTML cleaned to an allowlist (decision 0041); python-markdown for what people write in Markdown, made HTML on the server (decision 0055); React 19, Vite, TypeScript strict, React Router 7 (library mode), TanStack Query; design tokens as CSS custom properties with Tailwind v4 mapped to them; openapi-typescript + openapi-fetch for the typed client, with openapi-react-query for its TanStack Query hooks (decision 0042); uqr for the authenticator app's QR code (decision 0043); Anthropic's `anthropic` SDK for the AI's writing help, called from the server only (decision 0058); resvg-py to make a model's SVG, cleaned to an allowlist by `kernel.svg`, a PNG on the server (decision 0065); Postgres-backed job queue; S3-compatible storage (Cloudflare R2) through boto3 (decision 0032); Docker on Railway. Tests: pytest (moto for storage), Vitest + React Testing Library (jsQR reads a drawn QR code back), Playwright.

## Architecture (brief)

- **Copied in, not installed:** a site is the kernel plus the modules it needs, copied into its repo by the `mechframe` CLI (decision 0002). Each module has its own manifest, Alembic branch, routes and web.
- **Seams:** a module's web reaches another's `public.ts` as `@/modules/<id>/public` (decision 0057), and a site's own code a module's `public.py`, which the site's mypy follows (#132). A module shows another's items through `kernel.refs` (hook 11), and shares another's public thing by content type and id through the kernel's `server_copy.preview` and the props slot `content.share` (`ShareParts`).
- **The admin shell** is built to the Vibrant Mindz canvas Admin design, styled by tokens, for every site: only its generic parts are in the kernel, checked in the site's dark theme and in Machined Light (decision 0040, amending 0008). Its forms, lists, notes, dialogs and dashboard are drawn to the boards under `.mf-admin-look` (#155, #156, #158 and #165; decision 0040 amended three times). The kit's `Table` names each row by its `rowHeader` column, and its `QuietLink` is a link that stands alone beside a row's buttons.
- **The AI's writing help** (#135, decision 0058): `await ai.client(db)`. The key is `ANTHROPIC_API_KEY` or one saved in Settings → AI, and a saved key wins; the model is picked there too (decision 0064). No suite calls Anthropic or Buffer: the harness has fakes.
- **The name:** the project is MechFrame (decision 0034, #76); it was AI DevKit until K3. The repo is `mechframe/mechframe`, the CLI `mechframe` (also `mf`), the cookies `__Host-mf_*`, the variables `MECHFRAME_*`; the Python import stays `kernel`. Decision records and other history keep the old name as written.

## Commands

From the repo root, in PowerShell. Python commands use the `python -m` form. Every other command, the generators among them and when to run each, is in `docs/COMMANDS.md`.

| What | Command |
| --- | --- |
| Python environment, first time | `py -3.12 -m venv .venv`, then `.venv\Scripts\Activate.ps1` |
| Install Python dependencies | `python -m pip install --require-hashes -r requirements.txt -r requirements-dev.txt` |
| Test Postgres | `docker compose up -d db`; or any local Postgres 16+ with a role that has CREATEDB and `TEST_DATABASE_URL` pointing at it (compose and CI call it `mechframe`; the owner's machine keeps its `devkit` role on port 55432) |
| Python tests | `python -m pytest` (add `-m "not db"` to run without Postgres) |
| Lint, format, types | `python -m ruff check .`, `python -m black .`, `python -m mypy` |
| Web install | `npm ci` |
| Web tests, lint, types, build | `npm test`, `npm run lint`, `npm run typecheck`, `npm run build` |
| End-to-end tests (Playwright 1.64.1, Chromium build 1248, axe), locally before each push | once on a new machine, `npx playwright install chromium` (`npm ci` doesn't fetch the browser); then `npm run build`, and `npm run e2e` with `TEST_DATABASE_URL` set; it starts its own `python -m harness.e2e` on a `mechframe_e2e` database made fresh each run, never one already running, and reads no `.env`. CI runs them on main's pushes, weekly and by hand (`e2e.yml`), never on a PR |
| Progress document and ledger rows, after editing `docs/progress.json` | `python -m tools.progress` (`--check` only reports) |
| The generated files | OpenAPI: `python -m tools.openapi`, then `npm run api:types`; themes, event schemas, host variables and the template's lockfile: `python -m tools.themes`, `tools.event_schemas`, `tools.host_variables` and `tools.site_template`; the catalog: `mechframe catalog`. Each `--check` (and `npm run api:check`) only reports, and a test or CI fails while one is stale. Which to run after which change: `docs/COMMANDS.md` |
| Brand check, before any PR that lifts code | `python -I "C:\DEV\VybeSite\vybesite\scripts\brand_check.py" "C:\DEV\AI-DevKit"` |

## Rules

- **The spec is the contract.** A change to it is a decision record in `docs/decisions/` plus a line in its change log, in the same PR. Tell the owner which sections changed. There is no doc to sync: the claude.ai Spec doc is retired (decision 0017).
- **Provenance.** Nothing from the client folder named in `docs/private/README.md` or any client-confidential material ever enters this repo. Code lifted from VybeSite passes VybeSite's brand check before it lands: `python -I "C:\DEV\VybeSite\vybesite\scripts\brand_check.py" "C:\DEV\AI-DevKit"`. Never copy anything from VybeSite's `dev plans\` or `snapshots\`.
- **Ask first** before anything outward-facing: creating the GitHub repo or changing its settings, Railway projects, DNS, any third-party account, any message sent for the owner.
- **No secrets, ever.** Not in the repo, not in logs, not in chat. Keys go in a host's variables, typed by the owner.
- **Tests first.** A bug fix has a test seen failing before the fix. Auth work starts from the contract tests in spec 14.13.
- **One logical change per PR,** on its own branch, with conventional commits. Read the staged diff for secrets before every commit.
- **Pushing and merging are the agent's call in this project:** the owner stated it explicitly on 2026-11-17 ("use your best judgement on pushing and merging"), under the rule in `C:\DEV\knowledge\owner.md` (Git, PRs and CI). Push a PR branch once its local suites are green; land the PR once "CI result" is green on its head and the review bots have no open findings. Land by fast-forward (`git merge-base --is-ancestor origin/main <sha>`, then `git push origin <sha>:refs/heads/main`), never `gh pr merge`, then delete the branch here and on GitHub. Everything else outward-facing still asks first.
- **Modules never import each other** except through `public.py` / `web/public.ts` when listed in `requires.modules` (spec section 7).
- **Progress is kept in one file,** `docs/progress.json`: every phase and step to v1.0 and after, with its status and PRs. A PR that starts, finishes or adds a step updates it and runs `python -m tools.progress`, which rewrites `docs/PROGRESS.md` and the ledger's rows; `tests/test_progress.py` fails when they're stale. The owner follows the [visual progress ledger](https://claude.ai/artifact/48auLkb7Ajmyn2SNAni9rm), made from the same rows.
- **Skills:** don't build new skills as you go. Add every idea to `docs/SKILL-BACKLOG.md`; the owner builds them all in one batch later. Build one early only if the work can't continue without it, and say so.

## Gotchas

- Windows: the owner's terminal is PowerShell. Python commands use the `python -m` form (`python -m pip`, `python -m pytest`). PowerShell blocks scripts by default, `Activate.ps1` and `npm.ps1` included: use `.venv\Scripts\python.exe -m ...` and `npm.cmd`, unless the owner has run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- FastAPI 0.16x keeps included routers whole in `app.routes`: walk routes with `fastapi.routing.iter_route_contexts`.
- pytest runs with `--import-mode=importlib`; the root `conftest.py` imports the real `kernel` package before collection so `kernel/tests/*` can't shadow it.
- React Router stays on 7.x (the spec) though 8.x is out; TypeScript stays on 6.0.x for typescript-eslint.
- VybeSite's code is React 18.3; lifted components move to React 19 (ref as a prop, no `forwardRef`).
- VybeSite uses JWT sessions and separate staff and member tables. MechFrame uses opaque cookie sessions and one `auth_user` table (spec 14.1 and 14.5, decision 0003). Port the behavior, not the shape.

## Project map

| Path | What |
| --- | --- |
| `SPEC.md` | The contract (v0.1) |
| `AGENT-GUIDE.md` | Front door for an agent building a site with MechFrame |
| `kernel/` | The always-installed core: `backend/kernel/` (Python), `migrations/`, `tests/`, `web/` (the kit is `web/src/ui/`) |
| `modules/` | One folder per module; `modules/_template/` is the starting point |
| `harness/` | Dev app that mounts the kernel and modules for tests and local runs; `harness/alembic/` is the one Alembic environment |
| `templates/site/`, `cli/` | The empty site `mechframe new` starts every project from, and the `mechframe` CLI |
| `docs/decisions/` | Decision records |
| `docs/HANDOFF.md` | One page, overwritten each session |
| `docs/progress.json` | Progress to v1.0 and after; `docs/PROGRESS.md` and the ledger's rows are made from it |
| `docs/plans/` | Plans: the Vibrant Mindz module and backend plans, the module roadmap |
| `dev plans\`, `dev plans\contracts\` | Session prompts and working plans; each feature's one-page contract, written first and approved by the owner |
| `docs/COMMANDS.md` | Every command, and which generator to run after which change |
| `docs/REPO-MAP.md` | The whole repo, folder by folder, and when to use each project skill (`skills/`, linked into `.claude/skills/` by `python -m tools.link_skills`) |
| `docs/archive/` | Moved out of this file when it was leaned, word for word: the state PR by PR |

## Session end

Every session ends with `docs/HANDOFF.md` overwritten, this file's "Last Completed Task" and "Current state" updated, a starting prompt for the next session (about 4 KB) saved as `dev plans\<date>-next-session-<topic>.md` and offered to the owner, and the progress ledger republished: once `docs/progress.json` is current on `main`, upload `dev plans/progress-ledger/rows.json` to the ledger as an asset and point its `steps` dataset at the new file (`dev plans/progress-ledger/README.md`).

## Two lanes (the owner, 2026-11-22)

MechFrame runs two agents at once, the owner's parallel work under `C:\DEV\CLAUDE.md`'s token economy. This project only; other projects keep one session at a time.

- **The main lane** works in the main checkout, `C:\DEV\AI-DevKit`, on the critical path: the push plan's next step. It alone writes `docs/HANDOFF.md`, this file's "Current state" and "Last Completed Task", and the progress ledger.
- **The side lane** works in a worktree under `.claude/worktrees/`, on its own branch from `main`. It takes one self-contained job that shares no file with the main lane's job: another module, a kit fix, a tool, a board's parity items. It reports in its PR and in its prompt's "Result" section, never in `docs/HANDOFF.md`. The main lane folds that result into its next handoff.
- **Every session end writes two prompts,** each about 4 KB, verified, not remembered:
  - `dev plans\<date>-next-session-<topic>.md` for the main lane;
  - `dev plans\<date>-side-lane-<topic>.md` for the side lane, which says to start it in a worktree.
  - Each names the files its job owns, the files it must not touch, and the IDs it claims: decision numbers and migration numbers, split between the two.
  - Offer both as fenced blocks: the owner starts each as a top-level session.
- **Keeping out of each other's way:**
  - **PR numbers** come from GitHub just before each push, never predicted across lanes.
  - **Generated files** are taken from `main` and made again after merging it, never merged by hand: `docs/progress.json` then `python -m tools.progress`, `catalog.json`, the committed OpenAPI specs and `schema.ts` files, `package.json`'s `api:*` scripts, `docs/HOST-VARIABLES.md` then `python -m tools.host_variables`, and SPEC's change log.
  - **The worktree** uses the main checkout's `.venv` python and a junction to its `node_modules`. Remove the junction (`cmd /c rmdir`) before `git worktree remove`. Playwright finds no tests there: run end-to-end specs from the main checkout.
  - **One full suite at a time on this PC.** The main lane runs the full suite before it pushes. The side lane runs its own module's suites, lint and types, then lets CI's full suite gate its PR (the owner, 2026-11-22).
  - **One end-to-end run at a time:** `harness.e2e` drops and makes again the one database `mechframe_e2e`. Tell the other lane before a run, and after it.
  - **Landing:** merge `main` into the branch, run that lane's suites green, then fast-forward, as above.
  - **The review bots' quota is shared:** push each branch once, then fixes batched.
