# Next session, main lane (M4m): the site's board check of #165, then steps 1 and 2's closes

Run from `C:\DEV\AI-DevKit`, the main checkout, on `main`. Follow this file from section 4.

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe. Vibrant Mindz's steps are the "site" phase of `docs/progress.json`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** ("Two lanes" in `CLAUDE.md`). Tell the side lane, on discography 0.1.4, before and after every e2e run.
- **Yours:**
  - the kit (`kernel/web/src/ui/`) and `kernel/web/src/admin/`;
  - the AI's code and tests (`kernel/web/src/ai/`, `kernel/backend/kernel/ai.py`, `kernel/backend/kernel/ai_routes.py`, `kernel/tests/e2e/ai.spec.ts`);
  - `kernel/tests/e2e/support.ts`;
  - step 1's modules, and audio-player.
- **Not yours:** `modules/discography/`, `modules/featured/` and `kernel/backend/kernel/refs.py`. Ask the side lane first.
- **The site's session** is the newest VM Website Dev session (Dev 24 had #165's landing). Send it each PR number when it's pushed and when it lands. Never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key, a new module's contract, and removing worktrees.

## 3. State (verify it)

Checked 2026-11-27, about 13:40 Eastern (18:40 UTC):
- **`main`:** 89ed7e2 (#165). This handoff is a docs PR on `docs/handoff-m4l`. Once it lands, `main` is its head and the checkout should be on `main`. Check `git log -1 origin/main` and `gh pr list`.
- **Open PRs:** only the handoff's. The e2e workflow on 89ed7e2 was running at the handoff; read its result (`gh run list --workflow e2e.yml`).
- **Versions:** blog 0.1.7, campaigns 0.1.1, audio-player 0.1.2, discography 0.1.3, featured 0.1.0, contact 0.1.2, embeds 0.1.1.
- **Progress:** v1.0 at 80% (49 of 61). Steps 1 and 2 are "next". The ledger shows this handoff's rows.

## 4. The job, in order

0. Land the handoff's PR if it's still open: "CI result" green, the bots clear.
1. **VM Website's board check of #165.** Dev 22's ask: `C:\DEV\VM Website\dev plans\2026-11-26-kit-r-items-ask.md`. Take any differences it sends as asks. Open item: K9's "15 px words". Here a note's what is 16px and its why 14px, and Dev 24 was asked which part it measured.
2. **Step 1's close,** once the site says the boards hold. Its other three tests passed on 2026-11-25. Set the row to done, then run `python -m tools.progress`.
3. **Step 2's close** (the owner: "All four, like Step 1"):
   - schemas;
   - tests on `main`;
   - `mechframe check` on a fresh site with step 2's modules;
   - VM Website's board check of Admin › Music, after discography 0.1.4.
   The owner's iPhone Safari check of the player comes first.
4. **Diagnose the flaky axe test** at `kernel/tests/e2e/sign-in.spec.ts:389`, the `DEBUG_PROTOCOL.md` way.
5. **Step 3** (roster, portfolio, reactions, comments): ask the owner its order and lanes first. The recommendation is reactions first (`docs/plans/vibrant-mindz-backend/extraction/reactions.md`). Each contract goes first.

Close out at a natural break past ~400K tokens. Both lanes' prompts are yours.

## 5. Ask the owner, don't decide

- Step 3's order and lanes.
- Removing the five old standby worktrees under `.claude/worktrees/` (the side lane's `discography-0-1-0` stays), and the two memory notes marked "can be deleted".
- The Vibrant Mindz content.

## 6. Environment and traps

- **This PC is shared.** Before diagnosing an e2e timeout, check what's busy: `Get-Process`, CPU over 5 seconds. Synkopate's Remotion renders took about 7 of 16 threads and timed out every spec at 30s. `--workers=1` held.
- **Full Python suite:** about 40 minutes with the PC shared. Merge `main` first, then run it in the background with its log in the scratchpad: `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest -q`.
- **E2E:** with `TEST_DATABASE_URL` set, run `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec>` (147 tests).
- **More traps:** `docs/HANDOFF.md`, Notes. Grep tests for a doc's name before moving text out of it.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`, decision 0040's third amendment, and #164's and #165's bodies.
- **IDs:** yours are 0068, 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane has 0074 and up and `discography_0002`. Read each PR number from GitHub just before the push.

## 8. Candidates for `knowledge/`

1. A docs-only PR's CI runs no tests, but tests read docs: grep for a file's name before moving text out of it.
2. A CSS type token that's a whole `font` can't be a `font-size`. Use `font:`, then set `line-height`.
3. A modal `<dialog>` is capped by the browser at 100% less 6px and 2em: set `max-width` to keep the margin.
4. Parallel e2e specs that save one versioned setting cross: save again after a refused save.
5. Before an e2e timeout hunt on a shared PC, measure CPU by process.
