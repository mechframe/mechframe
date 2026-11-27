# Handoff

Overwritten every session. This one: 2026-11-26, about 07:00 Eastern, to 2026-11-27, about 13:40 (Claude Code, the owner's machine, the owner on Remote Control at times), session M4l, the main lane. Landed: #164 and #165. The side lane landed #163 (discography 0.1.3). `main` is 89ed7e2 (#165), and this handoff is its own docs PR.

## State

- **#164, `CLAUDE.md` and `AGENTS.md` leaned:** 133 lines from 176, word for word into `docs/COMMANDS.md`, `docs/REPO-MAP.md` and `docs/archive/claude-state-to-2026-11-26.md`. The ledger README's step 4 says the ledger writes its `check` only after a page file changes, or on a fault.
  - It broke `cli/tests/test_review_91.py`, whose `INSTALL_DOCS` still named `CLAUDE.md`. Its docs-only CI skipped Python. The side lane fixed the test in #163.
- **#165, VM Website Dev 22's ask** (`C:\DEV\VM Website\dev plans\2026-11-26-kit-r-items-ask.md`, against canvas 115 and 116). Decision 0040 is amended a third time.
  - **Kit, admin only:** R1, R2, R6 to R9, K9 (every note radius 12; a note with nothing to click on the canvas only inside a card) and K10 (a long description beside its title; the summary still wraps).
  - **New in the kit:** `QuietLink` (K11), at least 24px each way.
  - **Modules:**
    - audio-player 0.1.2: K12's invalid `font-size: var(--mf-type-small)` and R3's 18px.
    - campaigns 0.1.1: R3, and Set aside named "Set aside <address>" for WCAG 2.5.3, which made `campaigns.spec` fail at random.
    - blog 0.1.7: Draw a cover's C1 to C3.
  - **Tests:** `saveAiKey` in `kernel/tests/e2e/support.ts` saves the site's one AI key again when parallel specs' saves cross.
  - **K9's 15px words** didn't reproduce: a note's what is 16px and its why 14px. VM Website Dev 24 was asked which part it measured.
- **The side lane** landed #163, discography 0.1.3 (Result in `dev plans/done/2026-11-25-side-lane-m12-discography-0-1-3.md` §9): row names, VM Website's P1 to P6 and #145's last items. A master whose COMMIT raised is kept, and a clean commit starts no background work.
- **Local results for #165:**
  - Full Python suite 3,896 passed; its one failure was #164's break.
  - Full e2e 147 of 147 before merging #163. After it, 145 of 147 with one worker: discography's long test times out locally (Next 2).
  - CI's e2e on `main` after #163 passed.
- **Steps 1 and 2** are "next". **The ledger** shows the rows from this handoff's `main`.

## Next

1. **VM Website's board check of #165** (Dev 24 was told it landed): send any differences back as asks. Step 1 closes once the boards hold: set its row to done.
2. **The side lane, discography 0.1.4:**
   - K11, "Open the release" as a `QuietLink` (`AdminTracks.tsx:700`);
   - `discography.spec.ts:81` within its 30 seconds at the end of a full local run (34s now);
   - VM Website's Admin › Music differences, if any.
3. **Step 2's close** (all four tests, like Step 1): schemas, tests on `main`, `mechframe check` on a fresh site with step 2's modules, VM Website's board check. The owner's iPhone Safari check of the player comes first.
4. **Diagnose the flaky axe test** at `kernel/tests/e2e/sign-in.spec.ts:389`, the `DEBUG_PROTOCOL.md` way. Under load it also timed out this session.
5. **Step 3:** its order and lanes are the owner's call. The recommendation is reactions first, since comments use it. Each contract goes first.

## Open questions for the owner

- Step 3's order and lanes: reactions, comments, portfolio and roster.
- The Vibrant Mindz content.
- Removing the five old standby worktrees under `.claude/worktrees/` (the side lane's `discography-0-1-0` stays), and the two memory notes marked "can be deleted".

## Notes

- **IDs:** the main lane used none this session. It still has 0068, 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane has 0074 and up and `discography_0002`.
- **Traps met:**
  - **This PC is shared:** Synkopate's Remotion renders took about 7 of its 16 threads at times, and every e2e spec then timed out at 30s. Check `Get-Process` before diagnosing a timeout. `--workers=1` held, with 145 of 147.
  - **A docs-only PR's CI runs no Python,** but tests read docs: grep tests for a file's name before moving text out of it.
  - **Kit class names:** the kit already had `.mf-text-link` (the auth screens'). Grep the built CSS for a class name before choosing one.
  - **`docs/progress.json`:** `json.dumps` rewrites its whole layout. Edit a step's one line in place.
  - **A type token is a whole `font`:** `font-size: var(--mf-type-*)` is invalid. Use `font:`, then set `line-height` after it.
  - **Modal dialogs:** the browser caps a modal `<dialog>` at 100% less 6px and 2em, so set `max-width` to keep 16px.
- **Still true:**
  - The full Python suite takes about 40 minutes with the PC shared (3,896 tests). The e2e suite takes about 3 minutes (147) on a quiet PC, and 22 minutes with one worker.
  - Commit with `git commit -F <file>` after `git branch --show-current`. Never `prettier --write` an existing file.
  - On Windows, the generators rewrite some `schema.ts` files with CRLF only: `git checkout` them.
  - A new command goes in `docs/COMMANDS.md`, and one used every session in `CLAUDE.md` too.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, never create a third-party account, and never edit `C:\DEV\VM Website`.
