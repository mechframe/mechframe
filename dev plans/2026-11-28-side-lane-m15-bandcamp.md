# Side lane (M15): VM Website's ask B, Bandcamp's own player, contract first

Start this in a **worktree** under `.claude/worktrees/`, on its own branch from `main` ("Two lanes" in `CLAUDE.md`). Read this file from the main checkout, `C:\DEV\AI-DevKit\dev plans\`: the worktree's copy may be older. Follow it from section 4.

## 1. The project and your lane

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe. The first site, Vibrant Mindz, is built in VM Website's own session. You're the side lane; the main lane takes comments, then ask C (uploaded video).

## 2. Yours, and not yours

- **Yours:** ask B in `modules/discography/` and `modules/embeds/`, and its contract `dev plans/contracts/bandcamp-player.md`. The owner gave B to this lane on 2026-11-28 ("as recommended").
- **Not yours:** the kernel, the kit and `kernel/web/src/admin/`; `modules/comments/`, `reactions/`, `media/` and `featured/` (ask C touches media and featured); `docs/HANDOFF.md`, `CLAUDE.md`'s state sections and the ledger. Ask the main lane (the newest "AI DevKit Development" session in the main checkout) first.
- **Generated files:** the PR makes its own (which to run after which change: `docs/COMMANDS.md`): `python -m tools.openapi`, `npm run api:types`, `mechframe catalog`, `python -m tools.host_variables`, and its `docs/progress.json` line then `python -m tools.progress`. After merging `main`, take main's copies and make them again. SPEC's change log: keep main's and add your line.

## 3. State (verify it)

Checked 2026-11-28, about 10:45 Eastern: `main` was 8e48530 (#171), and the main lane's handoff PR follows it. Discography is 0.1.4 and embeds 0.1.1. M14's worktree, `.claude/worktrees/mechframe-side-lane-portfolio-5d6e12`, is still there, detached at 8e48530; removing it is the owner's call. Ask B is in step 3's note in `docs/progress.json`: your PR adds its number to step 3's `prs`.

## 4. The job, in order

1. **B's contract,** from `C:\DEV\_templates\feature-CONTRACT.md` into `dev plans/contracts/bandcamp-player.md`, with the `mechframe-module-extractor` skill. Sources, read only:
   - VM Website's `dev plans/2026-11-28-ask-b-bandcamp-player.md` (the ask, its boards, what the site does already);
   - its approved `dev plans/contracts/player-sources.md` (2026-11-27);
   - the boards in `C:\DEV\VM Website\design\site\`, canvas 123.
   In short: discography keeps a Bandcamp player per track and per album from pasted embed code (embeds' `fromBandcampCode`); a track with no file or SoundCloud link plays from its own Bandcamp player, else its album's, and counts as Live; the reads (`Card`, release and track reads, `playerItem`) carry it; embeds exports its frame without its own facade (the boards' Listen is the facade); the admin's "Bandcamp player" field. The site's side waits switched off (`NO_BANDCAMP`). It goes to the owner before any code.
2. **Build it** in one PR (discography and embeds each a version up), linted with `module-contract-lint`; before the push, `python -m tools.validate_schemas`, the brand check on lifted code, and `mechframe add` then `mechframe check` on a fresh site.
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

Side lane M15, 2026-11-28, about 11:00 to 12:10 Eastern (16:00 to 17:10 UTC).

- **The contract** (`dev plans/contracts/bandcamp-player.md`) went to the owner first. They approved it as recommended, with its three answers in §8:
  - the queue skips a Bandcamp-only track;
  - the site's Listen takes turns through `useExclusive`;
  - a track falls back to its album's player.
  - Its "Changes as built" adds `SOURCE` and five smaller things; none changes what was approved.
- **#174, discography 0.1.5 and embeds 0.1.2,** from `main` at ad1702f (#172). It uses decision 0075 and migration `discography_0002`; 0076 to 0079 and `embeds_0001` are still free. Step 3's `prs` gains 174, and `python -m tools.progress` remade `docs/PROGRESS.md` and the ledger's rows. Republishing the ledger is the main lane's.
  - **Built:**
    - a "Bandcamp player" field on a track and an album takes the embed code;
    - the server reads it (embeds' new `from_bandcamp_code`, the web's twin, both held to 17 shared cases) and keeps only the link;
    - the source order: upload, SoundCloud, the track's own player, then its album's;
    - `bandcamp_url` beside `soundcloud_url` in every read, and Live everywhere;
    - `playerItem` null for a Bandcamp track, `playerQueue` without it, and `bandcampPlayer(track)`;
    - embeds' `EmbedFrame`, the iframe alone, drawn only once `media` is granted;
    - discography's own Release and Track pages draw a Listen, then the frame, taking turns with audio-player.
  - **For VM Website:** `playerItem` now returns `PlayerItem | null`, so the site's typecheck flags its Spotlight and deck builders until they leave Bandcamp tracks out and draw `bandcampPlayer(track)` through `EmbedFrame`. That's the wiring `NO_BANDCAMP` waits for. Then the boards' Bandcamp states at 1440 and 390 are VM Website's check.
- **Local before the push:**
  - discography's Python suites (backend and HTTP contract): 169 passed, 23 of them new (the two tests the new shape broke were updated);
  - `tests/`, `kernel/tests/contract/` and embeds' backend: 843 passed, 1 skipped, 19 xfailed. Three failures were stale generated files (`progress.json`'s PR number not yet set, discography's `openapi.json` version line), remade and passing (49 passed);
  - web: discography's and embeds' Vitest tests passed (263); ESLint and tsc are clean, and mypy is clean across the project;
  - a mutant (the Listen without `claim()`) fails the turn-taking test;
  - e2e: `discography.spec.ts` and `embeds.spec.ts` passed, 8 of 8, both themes, from a throwaway config in the worktree, with the main lane told before and after;
  - on a fresh site, `mechframe add` media, embeds, audio-player and discography, then `mechframe check`: passed. `tools.validate_schemas` is clean. The brand check doesn't apply: nothing was lifted.
- **Traps hit:**
  - a manifest's `summary` is 120 characters at most (again);
  - `docs/HOST-VARIABLES.md` lists each module's version and summary: run `python -m tools.host_variables` after a version bump;
  - `npm run api:types` rewrites every module's `schema.ts` with LF endings in a CRLF checkout, so restore the unchanged ones. `api:check` fails here on line endings alone: check one module with `openapi-typescript … --check`;
  - a `bash` heredoc with many apostrophes broke twice: write a long edit script with the Write tool and run it.
- **Candidates for `knowledge/`:**
  - a player that can't be paused from outside takes turns by being unmounted: claim the turn on Listen, and let the other player's start put it back (decision 0075);
  - when a public helper's return type widens to `| null`, a site's type checker is the cheapest way to say "this case needs handling now".
