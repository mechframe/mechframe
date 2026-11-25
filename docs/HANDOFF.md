# Handoff

Overwritten every session. This one: 2026-11-24, about 13:00 to 19:45 Eastern (Claude Code, the owner's machine, the owner on Remote Control), session M4i of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane. Landed: #147 (generated covers) and #148 (the footer's shift). The side lane landed #145 (discography 0.1.0) and has #149 (audio-player 0.1.0) open. `main` is `1a1b4b8`, #148's head; this handoff is its own docs PR.

## State

- **#147, generated covers** (decision 0065; `dev plans/contracts/blog-covers.md`), landed at `0a217b1`. It's blog 0.1.4 and media 0.1.4.
  - **What it does:** Draw a cover in the post editor, for `kernel.ai.write` and `media.image.upload`, while a key works and media's storage is on. Claude draws an SVG in Editorial, Signal, Minimal or Custom, in the site's colours, with its name in the corner. `kernel.svg` cleans it, the dialog shows the kernel's own PNG of it, and Use this cover keeps a 2400 × 1260 PNG with its alt text.
  - **The kernel gains:** `svg` and `ai.budget` on its surface, `sayAi` on the web, and the toast's `returnTo`. A render runs in a process of its own, stopped at 10 seconds.
  - **The reviews:** Codex's four findings and CodeRabbit's twelve are fixed, each code fix with a test seen failing first. The contract's "Changes after approval" lists them.
  - **The tests:** full Python suite 3,709 passed, 97.43%; web 1,032. The e2e cover test passes alone and beside `ai.spec.ts`; storage is off in `harness.e2e`, so the kept file is stood in at the browser.
- **#148, the footer's shift** (decision 0066; `dev plans/contracts/footer-shift.md`), landed at `1a1b4b8`.
  - **What it does:** one rule in `frames.css`. Nothing after `<main>` is drawn while it's empty, or while it holds only the session guard's empty busy mark (CodeRabbit on #148). `!important`, to win over a site's own unlayered footer styles.
  - **Measured:** 0.13 to 0.14 at 412 before, 0 after, on the kernel's home and its 404 page. `frame.spec.ts` checks the rule's states directly and fails without either line.
  - **Also in it:** CI's Python job may now run 30 minutes, not 20 (the owner's OK). Green runs take 14 to 18.
- **The side lane** (AI DevKit Development 44 and 46 WT):
  - **#145, discography 0.1.0,** landed at `5c12f8e`. Its result is §9 of `dev plans/2026-11-24-side-lane-m8b-discography-web.md`.
  - **#149, audio-player 0.1.0,** is open, from `.claude/worktrees/discography-0-1-0` on `feat/audio-player`. It puts `kernel.client_address` on the surface (decision 0071). Discography 0.1.1 follows it.
- **The owner's answers (2026-11-24):** the footer went right after covers. Social posting is a `social` module, its Buffer token on the host or saved in Settings like the AI's key, not as recommended (`blog.md` §8, 7).
- **VM Website Dev 17** is the site's session now (Dev 15 stood down). It has both landings.
- **The ledger** shows the rows from `1a1b4b8`. v1.0 stays 80% (49 of 61): step 1 is still "next".

## Next

1. **Social posting:** its contract first, `dev plans/contracts/social.md`, for the owner. It's a `social` module any module shares through, blog first, VybeSite's Buffer integration (`backend/app/services/buffer_service.py`) the source. The token is `BUFFER_ACCESS_TOKEN` or one saved in Settings, sealed, the saved one winning, with a Check, as `kernel.ai`'s key is.
2. **Then step 1's close:** with social in, check step 1's six modules against the push plan's "done when" and mark it.
3. **Small follow-ups,** each a PR of its own or folded into a nearby one:
   - blog's own `/blog` grows under the footer as its list arrives (0.03 at 412): hold the page until its first read;
   - embeds' `VideoPlaylist` "Prev" button is named "Previous video", which axe refuses (the side lane);
   - the review items #145 left: a sweep of unreferenced masters, the kit's row editors' keys and focus, batched reindex reads, a module-only downgrade test, a replacement committed mid-job.

## Open questions for the owner

- Social's contract, when it's written.
- Discography's settings: the Music panel saves through the kernel's settings routes, which ask for `kernel.settings.manage`; no route checks `discography.settings.manage`. It's a question for every module's settings.
- Earlier ones: the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`; hooks 6 to 8's changes after approval; the Vibrant Mindz content; `mechframe-iac-probe` on Railway.

## Notes

- **IDs:** the main lane used 0065 and 0066, and has 0067 to 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane has 0070, 0071 (written) and up.
- **Traps met:**
  - A loop that resolves "every unresolved thread" closes the bots' newest ones too. Resolve by the comment's id.
  - Bash heredocs mangle `\n` and `\x89` inside Python strings: write the script with the Write tool, and check its bytes with `od -c`.
  - Playwright empties `test-results/` each run, so a throwaway spec goes in `kernel/tests/e2e/zz-*.spec.ts` for one run, then is deleted.
  - A test page's inline `<style>` needs `bypassCSP: true`: the site's policy refuses it.
  - GitHub refuses a fast-forward to `main` until "CI result" passes: the rule is the gate.
  - On Windows, `npm run api:check` reports campaigns' and media's `schema.ts` stale. It's line endings only; CI on Linux is fine.
- **Still true:**
  - Run the full suite with `$env:PYTHONUTF8 = "1"`. It takes about 55 minutes here now.
  - Commit with `git commit -F <file>`, and check `git branch --show-current` first.
  - The root lint and black sweep `.claude/worktrees/`, and `npx.cmd` mangles arguments.
  - Never `prettier --write` an existing file: the repo isn't prettier-formatted. A new file can take `--print-width 160`.
- **`CLAUDE.md` is about 175 lines.** Lean it when the owner says.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code: social lifts its Buffer service.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, never create the Buffer account, and never edit `C:\DEV\VM Website`.
