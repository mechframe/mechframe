# Side lane (M9): audio-player 0.1.0, contract first

Start in the existing worktree `C:\DEV\AI-DevKit\.claude\worktrees\discography-0-1-0` (`EnterWorktree` with that path). It's detached at `main`: make `feat/audio-player` from `origin/main`, then follow this file from section 3. Commit this file with your first commit.

## 1. The project and your lane

MechFrame: website modules on a FastAPI and Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane is on blog covers (#147), then social posting.

- **Step 2 of the push:** `discography` (landed), then `audio-player`, then `featured` (`docs/plans/vibrant-mindz-backend/KICKOFF.md`, `backend-plan.md`, `players-admin.md`).
- **The worktree** has the junction to the main checkout's `node_modules`. Its Python is `C:\DEV\AI-DevKit\.venv\Scripts\python.exe`.
- **Tell the main lane** before and after every e2e run (`ListAgents`: the newest "AI DevKit Development" in the main checkout; 42 on 2026-11-24).
- **Never edit `C:\DEV\VM Website`;** read its player boards. Send VM Website Dev 12 the PR number when it's pushed and when it lands.

## 2. Yours, and not yours

- **Yours:** `modules/_audio-player/` (renamed `modules/audio-player/` once built), `dev plans/contracts/audio-player.md`, decisions 0071 and up, migration `audio_player_0001`.
- **Not yours:** `modules/blog/`, the kernel's AI files, `.github/workflows/ci.yml` (the main lane is raising the Python timeout to 30 min), `docs/HANDOFF.md`, `CLAUDE.md`'s state and the ledger.

## 3. State (verified 2026-11-24, about 17:10 Eastern)

- **`main` is `5c12f8e`:** #145, discography 0.1.0, landed; `feat/discography` is deleted.
- **Open PRs:** #147 (`feat/blog-covers`, head `0a217b1`, CI running), the main lane's.
- **The scaffold** `modules/_audio-player/` is stubs. It plans tables `audio_player_play` and `audio_player_play_daily`, settings `autoplay_next` and `count_after_seconds`, and permission `audio-player.stats.read`.
- **It reads** discography's `public.py` (`track_cards`, `release_cards`) and `web/public.ts`.

## 4. The job, in order

1. **Write the contract** `dev plans/contracts/audio-player.md` from `_templates/feature-CONTRACT.md`, as `discography.md` did.
   - Cover the docked and inline players, the queue, one thing playing at a time (embeds' YouTube player hands off through it), play counting, and the SoundCloud widget's CSP (`kernel-additions.md` 6).
   - **Stop for the owner's approval.**
2. **Build it** as discography went:
   - the backend and its migration;
   - contract tests over HTTP;
   - the web, to VM Website's boards, with web tests and an e2e spec;
   - MODULE.md, CHANGELOG.md and the generated files (`CLAUDE.md` Commands).
3. **Check it:** the `module-contract-lint` skill, then on a fresh site `mechframe add` media, embeds, discography and audio-player, and `check`.
4. **Land it:**
   - merge `main` and make the generated files again;
   - read the PR number just before the one push;
   - fast-forward on a green "CI result" with the bots clear.

## 5. Ask the owner, don't decide

In the contract's §8:
- what counts as a play;
- whether stats are kept daily;
- whether the queue survives a page move;
- whether a SoundCloud track plays in the widget or opens SoundCloud.

## 6. Environment and traps

- **Tests:** set `PYTHONUTF8=1`, `MECHFRAME_REQUIRE_DB=1` and `TEST_DATABASE_URL=postgresql://devkit:devkit@localhost:55432/postgres`. Run `python -m pytest -q -p no:cacheprovider modules/audio-player/tests` with the log in the scratchpad, and the web tests with `node node_modules/vitest/vitest.mjs run`.
- **The worktree guard** refuses compound git commands: run git plainly.
- **E2e:** memory `worktree-playwright-config`, after `npm run build`.
- **A CI job that timed out** gets `gh run rerun <id> --failed`, not a push.
- **Memories to read:** `react-render-time-sync-traps` and `rollback-expires-orm-rows`.

## 7. Evidence and next IDs

- **The model:** discography's contract, #145's PR body, and `modules/discography/`.
- **IDs:** decisions 0071 and up; migration `audio_player_0001`; PR numbers from GitHub at push time.

## 8. Candidates for `knowledge/`

1. A worker's timeout cancels the handler, which `except Exception` never hears. Give the job its own `asyncio.timeout` just under the worker's, so the last try records why.
2. Lock-order tests: wait until `pg_blocking_pids(actor)` holds the holder's PID, then probe with NOWAIT, and check against a mutant.

## 9. Result

(Filled in by the side lane.)
