# Repo map

Moved from CLAUDE.md on 2026-11-26, word for word, when it was leaned. CLAUDE.md keeps a short map; this is the whole repo, folder by folder, and the project skills.

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
