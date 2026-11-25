# Side lane (M10): discography 0.1.1, audio-player's first source

Start in the existing worktree `C:\DEV\AI-DevKit\.claude\worktrees\discography-0-1-0` (`EnterWorktree` with that path). Its branch `feat/discography-0-1-1` is made from `main` at `a9959ee`. It holds this file and M9's Result in one local commit, not pushed. Follow this file from section 3.

## 1. The project and your lane

MechFrame: website modules on a FastAPI and Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane's next session works on social posting (`dev plans/2026-11-24-next-session-m4j-social.md`).

- **Step 2 of the push:** discography (#145) and audio-player (#149) have landed. This is the contract's second PR, then `featured`.
- **The worktree** has the junction to the main checkout's `node_modules`. Its Python is `C:\DEV\AI-DevKit\.venv\Scripts\python.exe`.
- **Tell the main lane** before and after every e2e run (`ListAgents`: the newest "AI DevKit Development" in the main checkout).
- **Never edit `C:\DEV\VM Website`.** Send VM Website Dev 12 the PR number when it's pushed and when it lands.

## 2. Yours, and not yours

- **Yours:** `modules/discography/`, `modules/audio-player/` if a fix is needed, decisions 0072 and up, and migration `discography_0002` (if one is needed; none is expected).
- **Not yours:** `modules/blog/`, the kernel's AI and frame files, `.github/workflows/`, `docs/HANDOFF.md`, `CLAUDE.md`'s state and the ledger.

## 3. State (verified 2026-11-24, 22:50 Eastern)

- **`main`** is `a9959ee`. No PR is open.
- **audio-player 0.1.0** is on main. Its contract is approved, and §2's "discography 0.1.1" block is this job, word for word: `dev plans/contracts/audio-player.md`.

## 4. The job, in order

1. **Build** every bullet of the contract's §2 "discography 0.1.1" block. Not in it, and yours to decide:
   - the Dashboard card's data comes from a small admin read built on `audio_player.public.plays`;
   - an item's `count` in `playerItem` calls the new route.
2. **Test** as the contract's §7 "discography 0.1.1" bullets say, and update discography's e2e spec for the dock.
3. **Docs:** `module.json` 0.1.1, MODULE.md, CHANGELOG.md, a "Changes as built" in discography's contract, and Step 2's row. Then the generated files (`CLAUDE.md` Commands).
4. **Land it:** merge `main` and make the generated files again. Read the PR number just before the one push, and fast-forward on a green "CI result" with the bots clear.

## 5. Ask the owner, don't decide

- Anything that would change audio-player's contract.
- After this lands, the owner's live check (audio-player's contract §7): an upload and a SoundCloud track in Safari on an iPhone.

## 6. Environment and traps (M9's)

- **Before pushing, run `tests/` and `kernel/tests/contract/`, not only the module's suites.** CI failed twice on M9 for tests outside it:
  - `test_hook_consent.py` lists the modules with a media host;
  - `tests/test_openapi.py` refuses `JSONResponse` imported in a module (type a route `-> Response`);
  - `tests/test_migrations.py` needs a `_SEED` row in each new table, and the module's id as the branch label.
- **Tests:** set `PYTHONUTF8=1`, `MECHFRAME_REQUIRE_DB=1` and `TEST_DATABASE_URL=postgresql://devkit:devkit@localhost:55432/postgres`. Log to the scratchpad. Run web tests with `node node_modules/vitest/vitest.mjs run <path>`. An internal web file is imported by a relative path: only `/public` has an alias.
- **The worktree guard** refuses compound git commands and some words in a heredoc. Run git plainly, one command per call, and edit with the Edit tool or a script run with `python -I`.
- **E2e:** memory `worktree-playwright-config`, after `npm.cmd run build`.
- **CodeRabbit reviews in rounds,** each finding a narrower edge. Batch each round's fixes into one push. It rate-limits: a head it skipped still lands under the rule.

## 7. Evidence and next IDs

- **Evidence:** audio-player's contract, decision 0071, #149's PR body, and M9's Result (`dev plans/2026-11-24-side-lane-m9-audio-player.md` §9).
- **IDs:** decisions 0072 and up; PR numbers from GitHub at push time.

## 8. Candidates for `knowledge/`

1. A side lane's "own suites" must include the repo's and kernel's tests that enumerate modules or guard module code: three of M9's CI failures were there.
2. Plays counted without consent: an HMAC of the address and the browser's name under a daily random salt, the salt and listeners deleted the next day (decision 0071).

## 9. Result

(Filled in by the side lane.)
