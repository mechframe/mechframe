# Handoff

Overwritten every session. This one: 2026-11-25, about 10:00 Eastern, to 2026-11-26, about 07:00 (Claude Code, the owner's machine, the owner on Remote Control at times), session M4k, the main lane. Landed: #155, #156, #158, #160 and #161. The side lane landed #157 (featured 0.1.0) and #159 (discography 0.1.2). `main` is 2e3b155 (#161), and this handoff is its own docs PR, #162.

## State

- **VM Website Dev 17's queued asks are done:**
  - **#155:** Settings › AI's Model row drawn to its board (A1 to A4).
  - **#156:** the admin kit to the boards, the ask's 22 lines (B1 to B10, C1 to C5, W2 to W4, S1, C1 more, T1, T2). They apply in the admin only, under `.mf-admin-look`. Contact is 0.1.2. Decision 0040 is amended.
  - **#158:** VM Website's next asks: K3's 12px pills, K6's 12px column heads, and the StatCard's link and figure (P2, P3). The kit's `Table` gains `rowHeader="<column key>"`, which draws that column's cell as each row's `<th scope="row">` at 600. Decision 0040 is amended again.
  - **The site's parity tools** (Dev 21): the forms' 22 lines and the Dashboard card's P1 to P3 match. A short list still differs (card titles' line height, a few cases at 390) and is with its owner first, so Step 1's board test hasn't passed.
- **Small follow-ups landed:**
  - **#160:** embeds 0.1.1, the playlist's "Prev" reads "Previous" (WCAG 2.5.3), and audio-player's e2e axe covers the playlist again. audio-player 0.1.1 lets the Player section on Settings › Site span its card (VM Website's ask, on its owner's word).
  - **#161:** blog 0.1.6, `/blog` holds back on a first load until its posts and categories answer, so the footer doesn't move (decision 0066's consequence). Before, it shifted 0.04 on a phone and 0.06 at 1440.
- **The side lane** (M11; Result in `dev plans/done/2026-11-25-side-lane-m11-featured.md` §9):
  - #157, featured 0.1.0 (decision 0073, `featured_0001`): Players at `/admin/featured`, the Dashboard's card. The kit's `SaveBar` gains `what`.
  - #159, discography 0.1.2: `refs.py`'s two sources, reads by id, and VM Website's D1 to D4, K2, K3's words, K6's card and K8.
- **Step 1** stays "next": its board test waits on the site's short list. **Step 2's** modules are all built; its close checks haven't run.
- **The ledger** shows the rows from this handoff's `main`.

## Next

1. **`CLAUDE.md` and `AGENTS.md`, leaned** (session M4l's docs PR): 133 lines from 176. The whole commands table is in `docs/COMMANDS.md`, the whole map and the project skills in `docs/REPO-MAP.md`, and the state PR by PR in `docs/archive/claude-state-to-2026-11-26.md`, each word for word.
2. **VM Website's asks as they come:** the short list, once its owner has decided, and whether to fix `.mf-player-hint`. Its owner decided on 2026-11-26 ("Send all of them"): Dev 22 sent both as `C:\DEV\VM Website\dev plans\2026-11-26-kit-r-items-ask.md` (R1 to R3, R6 to R9, K9 to K12). That rule sets `font-size` to a whole font shorthand, so the size is invalid and the Loading line inherits.
3. **Step 1's close,** once the site says the boards hold: set the row to done.
4. **Step 2's close** (the owner: "All four, like Step 1"): schemas, tests on `main`, `mechframe check` on a fresh site with step 2's modules, and the boards by VM Website's parity check. The owner does the iPhone Safari check before it closes.
5. **Diagnose the flaky axe test** at `kernel/tests/e2e/sign-in.spec.ts:389` (the owner: "Diagnose it").
6. **Step 3:** its order and lanes are the owner's call. The recommendation is reactions first, since comments use it. Each module's contract goes first.
7. **The side lane:** discography 0.1.3, under way since 2026-11-26 on `feat/discography-0-1-3` (`dev plans/2026-11-25-side-lane-m12-discography-0-1-3.md`). The owner's order: row names (`rowHeader`), then VM Website's board-check fixes, then #145's review items.

## Open questions for the owner

- **Step 3's order and lanes:** reactions, comments, portfolio and roster.
- **The Player section's gap:** 16px, where the board's form cards space their parts 18px apart. Campaigns' Newsletter section does the same three times. VM Website raised it, and its owner hasn't decided.
- **Still open from before:** the Vibrant Mindz content.

## Owner's answers (2026-11-25, relayed by the side lane)

- Step 2 closes on all four tests, like Step 1; the owner does the iPhone Safari check first.
- Discography's settings stay admin-only (`kernel.settings.manage`).
- The Share card stays as built until VM Website's board check sends differences.
- Hooks 6 to 8's changes after approval are accepted as built.
- The flaky axe test is to be diagnosed.
- The owner types the newsletter's postal address and IMAP login when the site goes live.
- The owner deletes `mechframe-iac-probe` in Railway.
- `CLAUDE.md` is leaned soon, as its own docs PR.
- Vibrant Mindz's three slots are made with Players' New slot (`spotlight`: tracks, `releases`: albums, `videos`: YouTube links), on the site's dev copy now and at launch. Only Spotlight shows on the Dashboard.

## Notes

- **IDs:** the main lane used none this session. It still has 0068, 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane has 0074 and up and `discography_0002`.
- **Traps met:**
  - `git switch -c` cuts the new branch from the one you're on: switch to `main` first.
  - In PowerShell, `gh api --jq` breaks on its quotes, and piping a here-string to `git commit -F -` fails. Use the Bash tool, or a message file.
  - A unit test that waits a fixed time after a request left proves nothing: wait on the query cache's answer, and test each half of a two-read gate with its own mutant.
  - A Playwright route that fakes a read should answer GET only.
- **Still true:**
  - The full Python suite takes about 21 minutes now (3,897 tests); the e2e suite, about 3 minutes (141).
  - Commit with `git commit -F <file>`, and check `git branch --show-current` first.
  - Never `prettier --write` an existing file.
  - On Windows, `npm run api:check` reports some `schema.ts` files stale over line endings. CI on Linux is fine.
- **A new command** goes in `docs/COMMANDS.md`; commands used every session go in `CLAUDE.md`'s Commands too.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, never create a third-party account, and never edit `C:\DEV\VM Website`.
