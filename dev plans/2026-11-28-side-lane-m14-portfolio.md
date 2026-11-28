# Side lane (M14): portfolio, contract first

Start this in a **worktree** under `.claude/worktrees/`, on its own branch from `main` ("Two lanes" in `CLAUDE.md`). Read this file from the main checkout, `C:\DEV\AI-DevKit\dev plans\`: the worktree's copy may be older. Follow it from section 4.

## 1. The project and your lane

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe: modules copied into a site's repo. The first site is Vibrant Mindz, built in VM Website's own session. You're the side lane. The main lane, in the main checkout, takes reactions, then comments.

## 2. Yours, and not yours

- **Yours:** `modules/portfolio/` (new) and `dev plans/contracts/portfolio.md`. The site's asks for discography or featured, if any come, are yours after portfolio, each in its own PR.
- **Not yours:**
  - the kernel, the kit and `kernel/web/src/admin/`;
  - `modules/reactions/` and `modules/comments/`;
  - `docs/HANDOFF.md`, `CLAUDE.md`'s state sections and the progress ledger.
  Ask the main lane (the newest "AI DevKit Development" session in the main checkout) first.
- **Generated files** are taken from `main` and made again after merging it, never merged by hand. They include `docs/progress.json` (then `python -m tools.progress`), `catalog.json`, the committed OpenAPI specs and `schema.ts` files, `package.json`'s `api:*` scripts, and SPEC's change log.

## 3. State (verify it)

Checked 2026-11-28, about 06:00 Eastern (11:00 UTC): `main` was de279f9 (#168), and the main lane's handoff PR follows it. Steps 1 and 2 are done; step 3 (roster, portfolio, reactions, comments) is next, in the owner's order. Portfolio's scaffold waits as `modules/_portfolio/` (2026-11-15, from `docs/plans/vibrant-mindz-backend/backend-plan.md`): start from it, as discography did from its own.

## 4. The job, in order

1. **Portfolio's contract,** from `C:\DEV\_templates\feature-CONTRACT.md` into `dev plans/contracts/portfolio.md`.
   - The module plan's row (`docs/plans/vibrant-mindz-module-plan.md` §2): paintings, graphic design, animation and video, by discipline. It's new, with no source to lift from.
   - It picks images from `media` and videos through `embeds`, through their `public.ts`. Look at `featured` and `discography` for how a module lists another's items (`kernel.refs`, hook 11).
   - Ask VM Website's session which boards draw portfolio's admin and public pages.
   - It goes to the owner before any code.
2. **Build portfolio 0.1.0** in one PR, from its scaffold, linted with the `module-contract-lint` skill. Then, on a fresh site, `mechframe add` its requirements and portfolio, and run `mechframe check`.
3. **Report** in this file's section 9, Result, and in the PR. Never write in `docs/HANDOFF.md`.

## 5. Ask the owner, don't decide

- The contract, above all what video means for now. Uploaded video is VM Website's stage C, not built; until then, by a link through `embeds`?

## 6. Environment and traps

- **The worktree** uses the main checkout's `.venv` python and a junction to its `node_modules`. Remove the junction (`cmd /c rmdir`) before `git worktree remove`.
- **Playwright finds no tests in the worktree.** Use a throwaway config inside the worktree's ignored `test-results/`, with forward slashes, and delete it before lint (the memory note "Worktree Playwright config").
- **One e2e run at a time:** tell the main lane before and after.
- **Your suites:** portfolio's own, plus `tests/` and `kernel/tests/contract/` (a new module trips hidden tests: the memory note "New module: hidden tests"), lint and types. CI's full suite gates the PR.
- **The worktree's guard** refused a heredoc'd Python script: write the file whole with the Write tool.

## 7. Evidence and next IDs

- **IDs:** yours are decisions 0074 to 0079, `portfolio_0001` and `discography_0002`. The main lane has 0068, 0069 and 0080 to 0089. Read each PR number from GitHub just before the push.
- **Evidence:** `docs/HANDOFF.md`, and the side lane's last Result in `dev plans/done/2026-11-27-side-lane-m13-discography-0-1-4.md` §9.

## 8. Candidates for `knowledge/`

- Add any you find to your Result; the main lane folds them in.

## 9. Result

(Written by the side lane when its PR lands.)
