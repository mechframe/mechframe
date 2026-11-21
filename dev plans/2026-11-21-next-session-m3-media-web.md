# Next session (M3b): finish `media`, then M4

Run from `C:\DEV\AI-DevKit`: "Read dev plans\2026-11-21-next-session-m3-media-web.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`), public repo mechframe/mechframe. The kernel is done and hooks 1 to 8 are in. This is M3 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`: `media`, the first real module, which `blog` requires. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **`media` follows its approved contract**, `dev plans/contracts/media.md` (the owner, 2026-11-21, as recommended): images only, files in the public bucket, "Used in" with Delete waiting. A change is a dated line under its "Changes after approval", told to the owner in the PR. Six are there already.
- **Lift with** `skills/mechframe-module-extractor/SKILL.md`; lint with `skills/module-contract-lint/SKILL.md` (imports from `kernel` only, never `kernel.<private>`); brand-check before the PR.
- **Hooks 9 and 10 wait.** Landing: push once local suites are green; land by fast-forward on a green "CI result" with no open thread. Never edit `C:\DEV\VM Website`.
- **The owner's call:** any Railway project, apply or variable, and CI's security gates.

## 3. State (2026-11-21, evening Eastern; check it, don't trust it)

- **main** should be this handoff's PR (#115) on `12b3993` (#114). #113 and #114 landed. `git log -1 origin/main`, `gh pr list`. **If #115 is open,** land it by fast-forward on a green "CI result".
- **`feat/media`** is local only, at `aae5612` on `0d19081` (#113): merge `origin/main` in first, then run the full suite (the session's last run wasn't read). It holds `modules/media/` (backend, migration, `module.json`, `openapi.json`, 53 upload tests), the pins and `catalog.json`.
- `CLAUDE.md` is 159 lines: lean it (`C:\DEV\LEAN-CONTEXT-PROMPT.md`) unless the owner says not now.

## 4. The job, in order

0. Read the Vibrant Mindz handoff's "For MechFrame" list (`C:\DEV\VM Website\docs\HANDOFF.md`, read only).
1. **Backend tests**, in `modules/media/tests/`:
   - a `conftest.py` of its own (the kernel's fixtures in `kernel/tests/conftest.py` aren't visible to `modules/`);
   - service tests against the migrated database: upload, dedupe, replace, change with a stale `version`, delete while in use, `public.use` and `release`, privacy and dashboard;
   - contract tests over HTTP through `harness.testing.build_test_app` with fake S3. `POST /api/_test/users` makes signed-in people with roles. The kernel's contract client only allows routes in `docs/contracts/auth-api.md`, so media's need their own list or a client of their own.
   - Test every route's access (anonymous 401, member 403, editor allowed), and run a mutant script.
2. **Web** (`modules/media/web/`):
   - `module.web.ts` (admin `/admin/media`, `nav.admin` under Content), `api.ts` through `createApiClient`;
   - `pages/AdminMedia.tsx` to the board `C:\DEV\VM Website\design\site\AdminMedia.dc.html`, on the kit (`kernel/web/src/ui/README.md`);
   - `public.ts` exporting `ImagePicker` (from VybeSite `frontend/src/components/ImagePicker.tsx`) and `Picture`;
   - Vitest with RTL, and a Playwright spec in `modules/media/tests/e2e/`: widen `playwright.config.ts` to `modules/*/tests/e2e` too (the owner approved it, 2026-11-21), and check the harness's e2e server has fake storage for uploads.
3. **Docs and the gate:** `MODULE.md`, `CHANGELOG.md`, SPEC's change log, `docs/progress.json` if a step moves, the brand check, the full suite, then the PR.
4. Then M4 (`pages`, `blog`).

Close out at a natural break past ~400K tokens.

## 5. Ask the owner, don't decide

The open questions in `docs/HANDOFF.md`, and anything the contract's §6 non-goals would have to give up.

## 6. Environment and traps

- **Full suite**, in the background with its log in the scratchpad; edit nothing in that checkout meanwhile: `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov`. A worktree under `.claude/worktrees/` lets other work go on.
- **`npx.cmd playwright ... -g "two words"`** breaks in cmd: pass `--grep=oneword`.
- **The Write tool decodes `\uXXXX`** into the character: build such strings with `chr()`.
- `python -m tools.openapi` rewrites `modules/media/openapi.json`; `mechframe catalog` rewrites `catalog.json`.

## 7. Evidence and next IDs

`docs/HANDOFF.md`; the contracts `media.md`, `after-footer.md` and `mechframe-upgrade.md`. Next free: PR #116 (#115 is this handoff), decision 0054, migration `kernel_0016`, `media_0002`.

## 8. Candidates for `knowledge/`

1. A sticky bar portaled outside its column needs a holder with `display: contents`: sticky binds to its parent's box.
2. An upgrade that skips a file while moving its base on never offers it again: stop instead.
3. One counter can't be both an edit token and a file's address.
