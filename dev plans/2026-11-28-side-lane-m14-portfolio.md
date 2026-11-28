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
- **Generated files:** the PR makes and commits portfolio's own: `python -m tools.openapi` (its `openapi.json`), its entries in `package.json`'s `api:*` scripts then `npm run api:types`, `mechframe catalog`, and its `docs/progress.json` line then `python -m tools.progress` (`docs/COMMANDS.md`). After merging `main`, take main's copies and make them again, never merged by hand. SPEC's change log is hand-written: keep main's and add your line.

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

Side lane M14, 2026-11-28, about 06:15 to 07:50 Eastern (11:15 to 12:50 UTC).

- **The contract** (`dev plans/contracts/portfolio.md`) went to the owner first, and was approved as recommended, its eight answers in §8. Its "Changes as built" lists what the build says more exactly; none changes what was approved.
- **#171, portfolio 0.1.0,** from `main` at 7e59b9b (#169), pushed once. Decision 0074 and migration `portfolio_0001` were used; 0075 to 0079 and `discography_0002` are still free. Step 3's `prs` gains 171, and `python -m tools.progress` remade `docs/PROGRESS.md` and the ledger's rows. Republishing the ledger is the main lane's.
  - **Built:** pieces with one picture from media, one discipline (the kernel's `portfolio_discipline`), the account they're credited to, a year, words and an optional YouTube link, drafted, scheduled and published through the lifecycle. Search, `refs.py` (`portfolio.piece`), server copy (`VisualArtwork`, `CollectionPage`, the sitemap), export and erase, and the seed. Collective › Portfolio and the Art page are drawn to VM Website's AdminPortfolio and Art boards, with a Settings section "Art page".
  - **The two permissions** (decision 0074): `portfolio.piece.add` for an artist's own pieces, held only while they hold it, and `portfolio.piece.manage` for every piece. `require_owner_or` passes anyone holding the permission it names, so VM Website's planned seed, which gives its artist role `portfolio.piece.manage`, `roster.profile.manage` and `licensing.work.manage`, would have opened every artist's work to every artist. The main lane was told, for roster's contract. VM Website's seed change (`portfolio.piece.add` and `media.image.upload` for the artist role) goes to its session once this PR lands.
  - **The boards:** VM Website Dev 27 was asked which boards draw portfolio, and didn't answer during the session. The build follows AdminPortfolio and Art, the two the design folder has (`design/site/README.md`, the Admin's seventh row).
- **Local before the push:**
  - portfolio's Python suites (backend and HTTP contract): 55 passed, 95.4% of its backend's lines and branches;
  - `tests/`, `kernel/tests/contract/` and `kernel/tests/test_app.py`: 743 passed, 1 skipped, 19 xfailed (10 minutes);
  - web: portfolio's 15 Vitest tests, ESLint and tsc clean; mypy clean across the project;
  - e2e: `portfolio.spec.ts`, 2 passed (both themes, axe at 1440 and 390), from a throwaway config in the worktree, the main lane told before and after;
  - on a fresh site, `mechframe add` media, embeds and portfolio, then `mechframe check`: passed. The brand check is clean.
- **Traps hit:**
  - a seed may never ask for the owner (`ctx.user("owner")` raises): use the seeded editor;
  - a manifest's `summary` is 120 characters at most (`tools.validate_schemas`);
  - the e2e server's storage is off, so media can't give any picture an address: a module whose every item needs a picture stands in its reads at the browser, as blog's covers are;
  - axe's `label-content-name-mismatch`: a button named by `aria-label` must contain its visible words, so "Edit" is a visually hidden prefix instead;
  - jsdom joins inline spans' words without spaces in a computed name, and Chromium doesn't: match a tile's name with `/^Edit ?Title/`.
- **Candidates for `knowledge/`:**
  - `require_owner_or(p)` passes staff holding `p` on anything: a role meant for "own only" needs a permission of its own (decision 0074);
  - a module that needs pictures can't be e2e-tested for real while the e2e server's storage is off; a fake public bucket in `harness.e2e` would let it.
