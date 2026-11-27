# Side lane (M13): discography 0.1.4

Start in the existing worktree `C:\DEV\AI-DevKit\.claude\worktrees\discography-0-1-0` (`EnterWorktree` with that path). It's detached at an old commit, so make your branch from the newest `main`: `git fetch origin`, then `git switch -c feat/discography-0-1-4 origin/main`. Follow this file from section 3.

## 1. The project and your lane

MechFrame: website modules on a FastAPI and Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** ("Two lanes" in `CLAUDE.md`). The main lane's session M4m works on VM Website's board check of #165 and steps 1 and 2's closes (`dev plans/2026-11-27-next-session-m4m-board-check.md`).

- **The worktree** has the junction to the main checkout's `node_modules`. Its Python is `C:\DEV\AI-DevKit\.venv\Scripts\python.exe`.
- **Tell the main lane before and after every e2e run.** It's the newest "AI DevKit Development" session in `ListAgents` that isn't a WT. Run e2e from the main checkout, or with memory `worktree-playwright-config`.
- **Never edit `C:\DEV\VM Website`.** Send the newest VM Website Dev session each PR number as it's pushed and again when it lands.

## 2. Yours, and not yours

- **Yours:** `modules/discography/`, decisions 0074 and up, migration `discography_0002` (none expected).
- **Not yours:** the kit (`kernel/web/src/ui/`), `kernel/web/src/admin/`, the AI's code, `kernel/tests/e2e/support.ts`, audio-player, step 1's modules, `docs/HANDOFF.md`, `CLAUDE.md`'s state and the published ledger. Adding your PR to Step 2's `prs` in `docs/progress.json` is yours, as #163 did. The main lane republishes the ledger.

## 3. State (verified 2026-11-27, about 13:40 Eastern, 18:40 UTC)

- **`main`** is 89ed7e2 (#165), or the main lane's handoff PR after it. #163 (discography 0.1.3) landed; its Result is in `dev plans/done/2026-11-25-side-lane-m12-discography-0-1-3.md` §9.
- **#165 added the kit's `QuietLink`** (`@/kernel`): a link that stands alone beside a row's buttons, in the info colour at the small size, underlined only when hovered, at least 24px each way. It also made every admin note radius 12, so Credits' amber note now has a card's colour, as its board draws it, with no change of yours.

## 4. The job, in order: discography 0.1.4, one PR

1. **K11** (VM Website Dev 22, `C:\DEV\VM Website\dev plans\2026-11-26-discography-012-parity.md`, "The kit's"): Tracks' panel's "Open the release" becomes a `QuietLink`. It's `modules/discography/web/pages/AdminTracks.tsx:700`: `<Link to={...}>Open the release</Link>` becomes `<QuietLink to={...}>Open the release</QuietLink>`. Add a check to discography's spec or its unit test.
2. **`discography.spec.ts:81`,** "an editor publishes a release, and a visitor plays it", within its 30 seconds at the end of a full local e2e run.
   - **The numbers:** 34.2s and 34.9s with one worker, though 18 to 19s alone. Before #163 it took 25 to 29s in full runs. #163's extra axe passes at each width (`cleanAtEachWidth`) push it over once the database holds the whole suite's data. CI's e2e on `main` passed it.
   - **The fix:** split the test, or cut what it repeats (fewer axe passes per width, say), so each test ends within 30 seconds at the end of a full run. Don't raise the timeout: `test.slow()` hides the length instead of fixing it (CodeRabbit on #166). Show it inside its time at the end of a full run: ask the main lane for a quiet window, since that run is the PC's one e2e run.
3. **VM Website's differences for Admin › Music,** if its board check of #165 sends any for discography.

Docs: MODULE.md if behaviour changes, CHANGELOG.md, `module.json` 0.1.4, then the generated files (`docs/COMMANDS.md`, "The generated files"). Step 2's `prs` gains the PR, then run `python -m tools.progress`. **Landing:** merge `main`, make the generated files again, read the PR number just before the one push, and fast-forward on a green "CI result" with the bots clear.

## 5. Ask the owner, don't decide

Anything that would change discography's contract.

## 6. Environment and traps

- **Before a push,** run discography's suites, `tests/` and `kernel/tests/contract/` (memory `new-module-hidden-tests`).
- **The test environment:** `PYTHONUTF8=1`, `MECHFRAME_REQUIRE_DB=1` and `TEST_DATABASE_URL=postgresql://devkit:devkit@localhost:55432/postgres`. Logs go to the scratchpad.
- **The worktree guard** refuses compound git: run git one command per call. Do multi-step work in a script piped to `python -I -`.
- **This PC is shared:** another project's renders can take about 7 of 16 threads. Check CPU by process before diagnosing a timeout.
- **On Windows,** `openapi-typescript` and the generators rewrite `schema.ts` with CRLF only: `git checkout` those files.

## 7. Evidence and next IDs

- **Evidence:** #165's body, decision 0040's third amendment, and `dev plans/contracts/discography.md`.
- **IDs:** decisions 0074 and up; `discography_0002`; PR numbers from GitHub at push time.

## 8. Candidates for `knowledge/`

1. A long e2e test with axe at each width grows with the suite's data: budget for the end of a full run, not a run alone.
2. A COMMIT that raised may still have landed: keep what it wrote (#163).

## 9. Result

(Filled in by the side lane.)
