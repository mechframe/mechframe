# Side lane (M12): discography 0.1.3, its row names, then the boards' fixes and #145's items

Start in a new worktree from `main` (`EnterWorktree`), on a branch `feat/discography-0-1-3`. Follow this file from section 3.

## 1. The project and your lane

MechFrame (`CLAUDE.md`, `SPEC.md`). You're the **side lane** ("Two lanes" in `CLAUDE.md`). The main lane's M4l works from `dev plans/2026-11-25-next-session-m4l-step-closes.md`.

- **The worktree** needs a junction to the main checkout's `node_modules`: `cmd /c mklink /J node_modules C:\DEV\AI-DevKit\node_modules`. Its Python is `C:\DEV\AI-DevKit\.venv\Scripts\python.exe`. Remove the junction with `cmd /c rmdir` before `git worktree remove`.
- **Tell the main lane before and after every e2e run.** It's the newest "AI DevKit Development" session that isn't a worktree.
- **Never edit `C:\DEV\VM Website`.** Send the newest VM Website Dev session each PR number as it's pushed and as it lands.

## 2. Yours, and not yours

- **Yours:** `modules/discography/`, plus audio-player and featured if a fix needs them. Decisions 0074 and up; migration `discography_0002`, though none is expected.
- **Not yours:** the kit (`kernel/web/src/ui/`), `kernel/web/src/admin/`, the AI's code (`kernel/web/src/ai/`, `kernel/backend/kernel/ai.py`, `ai_routes.py`), step 1's modules, `docs/HANDOFF.md`, `CLAUDE.md`'s state, and the ledger.

## 3. State (verify it)

Checked on 2026-11-26, about 06:30 Eastern. M12 started that morning, at the owner's word.
- **`main`** is 2e3b155 (#161). The main lane's docs-only handoff, #162, lands next. Merge `main` before you land.
- **Versions:** discography 0.1.2 (#159), audio-player 0.1.1 (#160), featured 0.1.0 (#157).
- **The kit's `Table`** takes `rowHeader` (#158). Deployed: nothing.

## 4. The job, in order

The owner's order (2026-11-25): "Row names, then fixes".

1. **Row names:** set `rowHeader="<column key>"` on Tracks' and Credits' tables, so that column's cell is each row's `<th scope="row">`, at 600 (VM Website's K6). Test it in discography's e2e spec at 1440 and 390, in both themes.
2. **VM Website's board-check fixes** for discography, as its sessions send them.
3. **#145's review items left for later:**
   - unreferenced masters;
   - the row editors' keys and focus;
   - batched reindex reads;
   - a module-only downgrade test;
   - a replacement committed mid-job.

   Find each in #145's threads (`gh api --paginate repos/mechframe/mechframe/pulls/145/comments`, the replies that defer it). Each fix gets a test seen failing first.
4. **discography 0.1.3, as one PR:** `module.json`, CHANGELOG.md, MODULE.md if a surface changes, and the generated files: catalog, `docs/HOST-VARIABLES.md`, the OpenAPI spec and its `web/schema.ts` (`python -m tools.openapi`, then `npm run api:types`), and the event schemas if an event changes (`python -m tools.event_schemas`). Add the PR's number, read from GitHub just before the push, to Step 2's `prs` in `docs/progress.json`, then run `python -m tools.progress`. The row's status and the ledger stay the main lane's.
   - **To land it:** merge `main`, make the generated files again, read the PR number just before your one push, then fast-forward once "CI result" is green and the bots are clear.
5. **Report** in §9 here and in the PR.

## 5. Ask the owner, don't decide

Anything that changes `dev plans/contracts/discography.md`. Already answered on 2026-11-25:
- the three slots are made with Players' New slot;
- only Spotlight shows on the Dashboard;
- discography's settings stay admin-only.

## 6. Environment and traps

- **Before a push,** run `tests/` and `kernel/tests/contract/` (memory `new-module-hidden-tests`), then the module's suites, lint and types.
- **Environment:** `PYTHONUTF8=1`, `MECHFRAME_REQUIRE_DB=1` and the main checkout's `TEST_DATABASE_URL`. Run web tests with `node node_modules/vitest/vitest.mjs run <path>`.
- **The worktree guard** refuses any command with "git" in it, so put multi-step work in a script file.
- **Encoding:** `pathlib.write_text` writes CRLF, so use `open(..., newline="")`. `gh api` output needs `encoding="utf-8"` in `subprocess`.
- **E2E:** memory `worktree-playwright-config`, after `npm.cmd run build`.

## 7. Evidence and next IDs

#145's threads, `dev plans/contracts/discography.md`, and M11's Result in `dev plans/done/`. IDs: decisions 0074 and up, `discography_0002`.

## 8. Candidates for `knowledge/`

1. A table names its rows with `rowHeader`: the table says which column, so a row has one name.

## 9. Result

(The side lane writes it here when the job is done.)
