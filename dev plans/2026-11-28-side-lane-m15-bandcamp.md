# Side lane (M15): VM Website's ask B, Bandcamp's own player, contract first

Start this in a **worktree** under `.claude/worktrees/`, on its own branch from `main` ("Two lanes" in `CLAUDE.md`). Read this file from the main checkout, `C:\DEV\AI-DevKit\dev plans\`: the worktree's copy may be older. Follow it from section 4.

## 1. The project and your lane

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe. The first site, Vibrant Mindz, is built in VM Website's own session. You're the side lane; the main lane takes comments, then ask C (uploaded video).

## 2. Yours, and not yours

- **Yours:** ask B in `modules/discography/` and `modules/embeds/`, and its contract `dev plans/contracts/bandcamp-player.md`. The owner gave B to this lane on 2026-11-28 ("as recommended").
- **Not yours:** the kernel, the kit and `kernel/web/src/admin/`; `modules/comments/`, `reactions/`, `media/` and `featured/` (ask C touches media and featured); `docs/HANDOFF.md`, `CLAUDE.md`'s state sections and the ledger. Ask the main lane (the newest "AI DevKit Development" session in the main checkout) first.
- **Generated files:** the PR makes its own (`docs/COMMANDS.md`): `python -m tools.openapi`, `npm run api:types`, `mechframe catalog`, `python -m tools.host_variables`, and its `docs/progress.json` line then `python -m tools.progress`. After merging `main`, take main's copies and make them again. SPEC's change log: keep main's and add your line.

## 3. State (verify it)

Checked 2026-11-28, about 10:45 Eastern: `main` was 8e48530 (#171), and the main lane's handoff PR follows it. Discography is 0.1.4 and embeds 0.1.1. M14's worktree, `.claude/worktrees/mechframe-side-lane-portfolio-5d6e12`, is still there, detached at 8e48530; removing it is the owner's call. Ask B is in step 3's note in `docs/progress.json`: your PR adds its number to step 3's `prs`.

## 4. The job, in order

1. **B's contract,** from `C:\DEV\_templates\feature-CONTRACT.md` into `dev plans/contracts/bandcamp-player.md`, with the `mechframe-module-extractor` skill. Sources, read only:
   - VM Website's `dev plans/2026-11-28-ask-b-bandcamp-player.md` (the ask, its boards, what the site does already);
   - its approved `dev plans/contracts/player-sources.md` (2026-11-27);
   - the boards in `C:\DEV\VM Website\design\site\`, canvas 123.
   In short: discography keeps a Bandcamp player per track and per album from pasted embed code (embeds' `fromBandcampCode`); a track with no file or SoundCloud link plays from its own Bandcamp player, else its album's, and counts as Live; the reads (`Card`, release and track reads, `playerItem`) carry it; embeds exports its frame without its own facade (the boards' Listen is the facade); the admin's "Bandcamp player" field. The site's side waits switched off (`NO_BANDCAMP`). It goes to the owner before any code.
2. **Build it** in one PR (discography and embeds each a version up), linted with `module-contract-lint`.
3. **Report** in this file's section 9, Result, and in the PR. Never write in `docs/HANDOFF.md`.

## 5. Ask the owner, don't decide

- The contract, with the ask's two questions: a Bandcamp-only track in an album's queue, and taking turns with a frame nothing can pause.

## 6. Environment and traps

- **The worktree** uses the main checkout's `.venv` python and a junction to its `node_modules`. Remove the junction (`cmd /c rmdir`) before `git worktree remove`.
- **Playwright finds no tests in the worktree:** a throwaway config inside its ignored `test-results/` (memory note "Worktree Playwright config").
- **One e2e run at a time:** tell the main lane before and after.
- **Your suites:** discography's and embeds' own, plus `tests/` and `kernel/tests/contract/`, lint and types. CI's full suite gates the PR.
- **The review bots:** push each round's fixes once, batched.

## 7. Evidence and next IDs

- **IDs:** yours are decisions 0075 to 0079, `discography_0002` and `embeds_0001`. The main lane has 0069 and 0080 to 0089. PR numbers from GitHub just before each push.
- **Evidence:** `docs/HANDOFF.md`, and your last Result in `dev plans/done/2026-11-28-side-lane-m14-portfolio.md` §9.

## 8. Candidates for `knowledge/`

- Add any you find to your Result; the main lane folds them in.

## 9. Result

(Written by the side lane when its PR lands.)
