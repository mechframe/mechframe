# AGENTS.md: MechFrame (same rules as CLAUDE.md)

The binding directives are in `C:\DEV\CLAUDE.md` and `C:\DEV\DIRECTIVES.md`, which Claude Code loads for every folder under `C:\DEV`. This file is the project map. Where the two differ, this file wins. `AGENTS.md` holds the same text for other agents.

## Identity

- **What:** MechFrame, a library of reusable website modules (auth, blog, chat, payments, community, media and more) that any AI agent copies into a site's repo and wires together from a short brief.
- **Owner:** VybeCode Software (VybeCod.ing / Vibrant Mindz).
- **Not:** a hosted platform, a WordPress-style CMS, or a package registry. Modules are copied in at build time (decision 0002).
- **Path:** `C:\DEV\AI-DevKit`. **Remote:** `https://github.com/mechframe/mechframe` (decision 0034), **public** (decision 0011). Never commit secrets, client material or private notes; private notes go in `docs/private/` (gitignored).
- **The contract:** `SPEC.md`. Every module, the kernel and the CLI follow it. Read the sections you touch before every change.

## Current state (2026-11-25; the kernel closed, #96; hooks 1 to 8, #97 to #110; media, #116; the kernel's Markdown, #118; pages, #121 and #138; blog, #123; contact, #125; embeds, #127; a site's mypy, #132; the AI's writing help, #135; campaigns, #134; the account's name, #139; the shell, #140; the signed-out session read, #141; blog 0.1.3, #143; the AI's model, #144; discography, #145 and #151; generated covers, #147; the footer's shift, #148; audio-player, #149; social, #152)

- **The kernel is done**, K0 to K5 (#1 to #96), with K2's steps 9 to 11 waiting until the site needs them (decision 0029). **Hooks 1 to 8** of the ten are in (#97 to #110, decision 0052); entitlements and profile tabs wait until just before Vibrant Mindz's step 5 and wave 2b. `mechframe upgrade kernel` is in (#111, #114; decision 0053).
- **Modules:** `media` (#116; drawn to its board, #119, #126 and #131; 0.1.4, #147, `public.store` for another module's image), `pages` (#121: Markdown pages, moves that never chain, the header's and footer's menus through link slots and `nav.footer`, decision 0056; 0.1.1, #138, its page read in `public.ts` and an Updated line), `blog` (#123: posts with categories, covers from media, related posts; 0.1.1, #128, its public surface; 0.1.2, #135, its fields handed to Write with AI; 0.1.3, #143, the summary in `blog.post.published` v2 and the editor's crossed saves; 0.1.4, #147, generated covers), `contact` (#125: the form, the Inbox, decision 0059's `notify_holders`; 0.1.1, #129, its reads and send in `public.ts`) and `embeds` (#127: players behind a consent facade, the kit's text slots `editor.tools` and `prose.embed`, decision 0060) and `campaigns` (#134: the newsletter, double opt-in sign-ups, sends at a pace and bounces read back, decision 0062), `discography` (#145, the side lane: releases, tracks, credits and links, an upload or a SoundCloud link as each track's audio, decision 0070; 0.1.1, #151, audio-player's first source), `audio-player` (#149: the player modules hand items to, one thing at a time, plays counted under a daily salt, decision 0071) and `social` (#152: a published post shared to the site's channels through Buffer from its editor's Share card, decision 0067; blog 0.1.5 draws it). A module shares another's public thing by content type and id through the kernel's `server_copy.preview` and the props slot `content.share` (`ShareParts`). A module's web reaches another's `public.ts` as `@/modules/<id>/public` (decision 0057), and a site's own code a module's `public.py`, which the site's mypy follows (#132).
- **The AI's writing help** (#135, decision 0058): `await ai.client(db)`. The key is `ANTHROPIC_API_KEY` or one saved in Settings → AI, and a saved key wins. Settings → Writing holds the site's rules and its styles (`kernel_0016`). Every editor has Write with AI through `editor.tools`. The model is picked in Settings → AI from Anthropic's newest Opus, Sonnet and Haiku, read each time, and saved only through its own route (#144, decision 0064, settings' `own_route`). No suite calls Anthropic: the harness has a fake. **Generated covers** (#147, decision 0065): Draw a cover in blog's editor; `kernel.svg` cleans Claude's SVG to an allowlist and renders it with the bundled Inter, and media keeps only the PNG.
- **The account and the session:**
  - a Name on Profile, and in People for staff (#139, decision 0061);
  - `GET /api/auth/session` answers a signed-out visitor 200 `{"user": null}`, never cached (#141, decision 0063);
  - the admin sidebar takes a section's page order from `AdminSection.pages` (#140, decision 0044 amended);
  - the site frame draws nothing after an empty `<main>`, so a first load never moves the footer (#148, decision 0066).
- **Next, main lane** (`dev plans/2026-11-25-next-session-m4k-kit-to-boards.md`): VM Website Dev 17's queued asks, the owner's call to do them before step 1's close: Settings › AI's Model row (A1 to A4), then the admin kit to the boards (B1 to B10, C1 to C5, W2 to W4, S1, T1, T2). Then step 1's close: its other three tests passed on 2026-11-25.
- **Side lane:** `featured`, its contract approved: first the "item references" hook (decision 0072, `kernel/refs.py`), then featured 0.1.0 (0073), then discography 0.1.2, in its worktree with its own prompt. Two lanes run at once ("Two lanes", below).
- **The kernel's Markdown** (#118, decision 0055): `kernel.markdown` (`render`, `plain`, `excerpt`) and the kit's `MarkdownEditor`, `Prose` and `SearchFields`. #119 added the kit's `SearchBox`, an action's icon before its words, the required token `opacity.55`, the session's `name` on the person card and the boards' admin sections by default (decisions 0042 and 0044, amended).
- **Progress** is one record, `docs/progress.json`, made into `docs/PROGRESS.md` and the owner's visual ledger (#61). v1.0: 80% (49 of 61 steps).
- **The first real site** is the new Vibrant Mindz site (`docs/plans/vibrant-mindz-module-plan.md`). It's built in its own session (`C:\DEV\VM Website`) from MechFrame's `main`. Its checks against the boards send items here, with the owner's calls relayed.
- **The project is MechFrame** (decision 0034, #76); it was AI DevKit until K3. The repo is `mechframe/mechframe`, the CLI `mechframe` (also `mf`), the cookies `__Host-mf_*`, the variables `MECHFRAME_*`; the Python import stays `kernel`. Decision records and other history keep the old name as written.
- **The admin shell** is built to the Vibrant Mindz canvas Admin design, styled by tokens, for every site: only its generic parts are in the kernel, checked in the site's dark theme and in Machined Light (decision 0040, amending 0008).
- **After v1.0:** the module roadmap and ten contract hooks (decision 0018, `docs/plans/module-roadmap.md`), and VybeSite's page builder for `pages` (the owner, 2026-11-21).
- The state as it stood to 2026-11-21, phase by phase, is in `docs/archive/claude-state-to-2026-11-21.md`. Next steps, blockers and warnings live in `docs/HANDOFF.md`.

## Last Completed Task

2026-11-24, about 20:00 Eastern, to 2026-11-25, about 10:00 (Claude Code, the owner's machine, the owner on Remote Control at times): session M4j, the main lane.

- **#152, social posting** (decision 0067), landed, its contract approved as recommended: social 0.1.0, blog 0.1.5, the kernel's `server_copy.preview` and `content.share`, with Codex's two findings and CodeRabbit's eleven fixed.
- **Step 1's close, checked:** three of its four tests pass; the boards' test waits on Dev 17's asks, which go first (the owner, 2026-11-25).
- **The side lane** landed #149 (audio-player) and #151 (discography 0.1.1).

## Read order

1. `KICKOFF.md` (first sessions) or the newest `dev plans\*-next-session-*.md` (later sessions). It is the job.
2. `docs/HANDOFF.md`: state, next steps, blockers.
3. `SPEC.md`: the sections the job touches.
4. `docs/decisions/`: why things are the way they are.
5. `docs/private/inventory.md` (on the owner's machine only, not in git): where each piece can be lifted from in `C:\DEV`.

## Stack (decision 0001)

Python 3.12+, FastAPI, Pydantic v2 (strict), async SQLAlchemy 2 + asyncpg, Postgres 16+, Alembic with one branch per module; auth by argon2-cffi, pyotp and webauthn (passkeys, decision 0028); nh3 for HTML cleaned to an allowlist (decision 0041); python-markdown for what people write in Markdown, made HTML on the server (decision 0055); React 19, Vite, TypeScript strict, React Router 7 (library mode), TanStack Query; design tokens as CSS custom properties with Tailwind v4 mapped to them; openapi-typescript + openapi-fetch for the typed client, with openapi-react-query for its TanStack Query hooks (decision 0042); uqr for the authenticator app's QR code (decision 0043); Anthropic's `anthropic` SDK for the AI's writing help, called from the server only (decision 0058); resvg-py to make a model's SVG, cleaned to an allowlist by `kernel.svg`, a PNG on the server (decision 0065); Postgres-backed job queue; S3-compatible storage (Cloudflare R2) through boto3 (decision 0032); Docker on Railway. Tests: pytest (moto for storage), Vitest + React Testing Library (jsQR reads a drawn QR code back), Playwright.

## Commands

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

## Project skills (`skills/`, linked into `.claude/skills/` by `python -m tools.link_skills`)

| Skill | Use it when |
| --- | --- |
| `mechframe-module-extractor` | Lifting a feature from another project into `modules/` |
| `mechframe-site-picker` | Turning a site brief into a module list and build commands |
| `beat-license-generator` | Building the `licensing` module |
| `printful-v2-adapter` | Building the `print-on-demand` module |
| `alembic-multi-module-migrations` | Adding a module's migrations, merging heads, the round-trip tests |
| `module-contract-lint` | Reviewing a module (or the kernel) against the contract before it merges |
| `mechframe-hook-designer` | Adding a cross-module hook to the contract (search index, consent, entitlements and the rest of the 2026-11-13 roadmap hooks) |

## Project map

| Path | What |
| --- | --- |
| `SPEC.md` | The contract (v0.1) |
| `KICKOFF.md` | The first build sessions' prompt: phases K0 to K5 |
| `AGENT-GUIDE.md` | Front door for an agent building a site with MechFrame |
| `schema/` | JSON Schemas: module manifest, recipe, lock file; event payload schemas land in `schema/events/` |
| `kernel/` | The always-installed core: `backend/kernel/` (Python), `migrations/`, `tests/`, `web/`, and `openapi.json` (generated) |
| `modules/` | One folder per module; `modules/_template/` is the starting point, and the Vibrant Mindz scaffolds wait as `modules/_<id>/` until built |
| `recipes/` | Preset module bundles per kind of site |
| `themes/` | Token sets, one folder each: `machined-light` (the default) and `vibrant-mindz`; `README.md` lists the kernel's required tokens |
| `templates/site/` | The empty site `mechframe new` starts every project from (#92; `templates/README.md`): the harness made into a site, its own pages in `backend/app/site/` and `web/src/site/`, Railway as code in `.railway/railway.ts` |
| `cli/` | The `mechframe` CLI: `cli/mechframe/` and its tests in `cli/tests/` (`cli/README.md`; built in K5) |
| `harness/` | Dev app that mounts the kernel and modules for tests and local runs; `harness/alembic/` is the one Alembic environment, `harness/migrations.py` drives it |
| `tools/` | Repo tooling: `validate_schemas.py`, `link_skills.py`, `build_common_passwords.py` (rebuilds the bundled list; steps in NOTICE) |
| `tests/` | Repo-level tests: schemas, migrations round trip, tools |
| `conftest.py` | The test run's made-up secrets and the throwaway Postgres fixtures |
| `catalog.json` | Generated index of every module (empty until the first module) |
| `docs/decisions/` | Decision records |
| `docs/HANDOFF.md` | One page, overwritten each session |
| `docs/progress.json`, `docs/PROGRESS.md` | Progress to v1.0 and after: the data, and the document `tools/progress.py` makes from it |
| `docs/private/` | Not in git (the repo is public): the inventory of `C:\DEV` and the name of the client folder |
| `docs/archive/` | Moved out of this file when it was leaned, word for word: the state to 2026-11-21, phase by phase |
| `docs/plans/` | Plans, such as the Vibrant Mindz module plan |
| `docs/plans/module-roadmap.md` | The module roadmap after v1.0: five waves of Musts, after ten contract hooks (decision 0018) |
| `docs/plans/vibrant-mindz-backend/` | The Vibrant Mindz backend plan: its kickoff (steps 0 to 7), specs, admin map, kernel additions and extraction briefs |
| `docs/contracts/` | HTTP contracts the contract suites check, starting with `auth-api.md` |
| `docs/SKILL-BACKLOG.md` | Skill ideas waiting to be built |
| `skills/` | Project skills, the source copies; K0 links them into `.claude/skills/` |
| `dev plans\` | Session prompts and working plans (the owner's convention) |
| `dev plans\contracts\` | Each feature's and module's one-page contract, written first and approved by the owner (`pages.md`, `blog.md`, `media.md`, the hooks' and the kernel's) |

## Gotchas

- Windows: the owner's terminal is PowerShell. Python commands use the `python -m` form (`python -m pip`, `python -m pytest`). PowerShell blocks scripts by default, `Activate.ps1` and `npm.ps1` included: use `.venv\Scripts\python.exe -m ...` and `npm.cmd`, unless the owner has run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- FastAPI 0.16x keeps included routers whole in `app.routes`: walk routes with `fastapi.routing.iter_route_contexts`.
- pytest runs with `--import-mode=importlib`; the root `conftest.py` imports the real `kernel` package before collection so `kernel/tests/*` can't shadow it.
- React Router stays on 7.x (the spec) though 8.x is out; TypeScript stays on 6.0.x for typescript-eslint.
- VybeSite's code is React 18.3; lifted components move to React 19 (ref as a prop, no `forwardRef`).
- VybeSite uses JWT sessions and separate staff and member tables. MechFrame uses opaque cookie sessions and one `auth_user` table (spec 14.1 and 14.5, decision 0003). Port the behavior, not the shape.

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
