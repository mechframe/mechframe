# Next session (M4): `pages`, then `blog`

Run from `C:\DEV\AI-DevKit`: "Read dev plans\2026-11-21-next-session-m4-pages-blog.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`), public repo mechframe/mechframe. The kernel is done, hooks 1 to 8 are in, and the first module, `media`, landed (#116). This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **Each module** gets a one-page contract first (`dev plans/contracts/<id>.md`), with the owner's goal and non-goals put as questions with a recommendation, as `media.md` was. Lift with `skills/mechframe-module-extractor/SKILL.md`, lint with `module-contract-lint`, and brand-check.
- **`media` is the pattern** for a module: `modules/media/`, its tests' own `conftest.py` files (backend and contract), web tests, `tests/e2e`, `BODY_LIMITS` for uploads, grants in its first migration, and seed rows in `tests/test_migrations.py`'s `_SEED`.
- **`blog` requires `media`:** its covers through `media.public` (`picture`, `use`, `release`) and `public.ts`'s `ImagePicker`.
- **Hooks 9 and 10 wait.** Landing: push once the local suites are green; land by fast-forward on a green "CI result" with no open thread. Never edit `C:\DEV\VM Website`.
- **The owner's call:** any Railway project, apply or variable, and CI's security gates.

## 3. State (2026-11-21, evening Eastern; check it, don't trust it)

- **main** should be this handoff's PR (#117) on `fde6a90` (#116). `git log -1 origin/main`, `gh pr list`. **If #117 is open,** land it on a green "CI result".
- **The progress ledger:** read `data/users/me` `check` on it (`dev plans/progress-ledger/README.md`). Once it has passed, delete the old asset `fe086f5b0b23e9e6621a99d0fe0cd7bb`.
- `CLAUDE.md` is about 160 lines: lean it (`C:\DEV\LEAN-CONTEXT-PROMPT.md`) unless the owner says not now.

## 4. The job, in order

0. Read the Vibrant Mindz handoff's "For MechFrame" list (`C:\DEV\VM Website\docs\HANDOFF.md`, read only).
1. **`pages`** (brief `docs/plans/vibrant-mindz-backend/extraction/pages.md`): contract, owner's answers, then one PR.
2. **`blog`** (brief `extraction/blog.md`; board `C:\DEV\VM Website\design\site\AdminBlog.dc.html` and `AdminPost.dc.html`): contract, then one PR. It fills lifecycle, taxonomy, search, seed and export.
3. Then M5, as the plan has it.

Close out at a natural break past ~400K tokens.

## 5. Ask the owner, don't decide

Each module's goal and non-goals; the open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite**, in the background with its log in the scratchpad: `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov`. CI's coverage leaves `modules/` out: measure a module's own with `--cov=modules/<id>/backend/<pkg>`.
- **End to end:** `npm run build`, then `npm run e2e` with `TEST_DATABASE_URL`. The e2e server runs with storage off.
- **Traps:** `npx.cmd` with a quoted argument holding a space fails in cmd. The Write tool decodes `\uXXXX`. A rollback expires ORM rows, so read ids first. Before a push, run `python -m black --check .` (the tests too).
- **CodeRabbit** re-reviews each push and can hit its hourly chat limit; Codex reviews a PR's first push only.

## 7. Evidence and next IDs

`docs/HANDOFF.md`, `dev plans/contracts/media.md`, decision 0054. Next free: PR #118 (#117 is this handoff), decision 0055, migration `kernel_0016`, `media_0002`.

## 8. Candidates for `knowledge/`

1. A savepoint's release fires SQLAlchemy's `after_commit`, and a session closed with no rollback fires only `after_transaction_end`: decide cleanup at the root transaction's end.
2. A key that a rolled-back try may reuse needs a number no rollback undoes (a sequence).
3. A sticky bar portaled outside its column needs a `display: contents` holder.
4. A test that holds a background delete behind a gate is the one that shows a cleanup race.
