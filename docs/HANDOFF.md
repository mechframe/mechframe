# Handoff

Overwritten every session. This one: 2026-11-24, about 20:00 Eastern, to 2026-11-25, about 10:00 Eastern (Claude Code, the owner's machine, the owner on Remote Control at times), session M4j of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane. Landed: #150 (M4i's handoff) and #152 (social posting). The side lane landed #149 (audio-player 0.1.0) and #151 (discography 0.1.1). `main` is `bd0ce93`, #152's head; this handoff is its own docs PR.

## State

- **#152, social posting** (decision 0067; `dev plans/contracts/social.md`, approved as recommended, all five answers), landed at `bd0ce93`. It's social 0.1.0 and blog 0.1.5.
  - **What it does:** a Share card after After publishing in blog's post editor, for `social.post.send` (admin, editor). You pick the channels Buffer reaches, edit one text, and send to Buffer's queue, now, at a time, or as a Buffer draft. Refresh and Take it back follow. The token is `BUFFER_ACCESS_TOKEN` or one saved in Settings › Site › Social, sealed; the saved one wins, with Check the token.
  - **The kernel gains:** `server_copy.preview(db, type, id)` and `search.public_document` (a thing's link from its search source and its own module's page), and the props slot `content.share`, drawn with `<ShareParts type id live />` (SPEC 6 and 8). Any module can share; discography's card is one line once its releases are searched.
  - **Never twice:** each channel's share is committed `sending` under an advisory lock before Buffer is asked. One with no answer back, or Buffer's `UNEXPECTED`, is `unknown` and counts as shared.
  - **Reviews:** Codex's two and CodeRabbit's eleven are fixed, each with a test. The contract's "Changes after approval" lists them.
  - **Tests:** full Python suite 3,795 passed, 97.30%; web 1,112; e2e 130 of 130; `mechframe check` passed. No suite calls Buffer: `harness/fake_buffer.py`, and `/api/_test/buffer` in the test app.
- **The side lane** (M9 and M10; Results in `dev plans/done/2026-11-24-side-lane-m9-audio-player.md` and `-m10-discography-0-1-1.md`, §9 each):
  - #149, audio-player 0.1.0 (decision 0071), with `kernel.client_address` on the surface;
  - #151, discography 0.1.1, audio-player's first source.
  - It's now on featured's contract (approved): first the "item references" hook (decision 0072: `kernel/refs.py`, its exports, a build beside `search.build` in the app, SPEC 6 and 7's hooks rows), then featured 0.1.0 (0073, `featured_0001`), then discography 0.1.2.
- **Step 1's close, checked:** schemas validate, tests pass on `main`, and `mechframe check` passed on a fresh site with all six modules. It fails one test, "the admin page matches its board": VM Website Dev 17's asks are open (below). The owner chose to do them first (2026-11-25), so Step 1 stays "next".
- **VM Website:** Dev 17 is offline. Dev 19 was told #152's push and landing, and asked to pass it on.
- **The ledger** shows the rows from this handoff's `main`.

## Next

1. **Dev 17's asks, queued since 2026-11-24 with the owner's OK**, in this order:
   - **A1 to A4, Settings › AI's Model row** (`kernel/web/src/ai/AiSettings.tsx`), record: `C:\DEV\VM Website\dev plans\2026-11-24-admin-ai-parity.md`.
   - **The kit to the boards** (the owner: "Kit to the boards"): B1 to B10 and C1 to C5, the parts every admin form shares; W2 to W4 and S1, Writing's own; T1 and T2, contact's settings; C1's 96 px minimum. Records: `C:\DEV\VM Website\dev plans\2026-11-24-admin-forms-kit-ask.md` (the 22 lines) and `2026-11-24-admin-writing-parity.md`.
2. **Then Step 1's close:** once the site's parity tools say the boards hold, mark Step 1 done in `docs/progress.json`.
3. **Small follow-ups,** each its own PR or folded into a nearby one:
   - embeds' `VideoPlaylist` "Prev" button named "Previous video", which axe refuses;
   - blog's own `/blog` growing under the footer as its list arrives;
   - #145's review items: unreferenced masters, the kit's row editors' keys and focus, batched reindex reads, a module-only downgrade test, a replacement committed mid-job.

## Open questions for the owner

- Where the Share card sits on the AdminPost board: built from the kit's parts after After publishing (§8, 3). VM Website draws it and sends any differences.
- Discography's settings permission: every module's settings save through `kernel.settings.manage`.
- The iPhone Safari check of the audio player (audio-player's contract §7).
- Earlier ones: the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`; hooks 6 to 8's changes after approval; the Vibrant Mindz content; `mechframe-iac-probe` on Railway.

## Notes

- **IDs:** the main lane used 0067, and has 0068 and 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane has 0072 (refs) and 0073 (featured) planned, and 0074 and up, `featured_0001` and `discography_0002`.
- **Traps met:**
  - A Bash heredoc turns `\n` inside a Python string into a real line break: write the file with the Write or Edit tool.
  - Two Playwright tests of one spec ran at once and saved the site's one settings section over each other. A spec on global state is `test.describe.configure({ mode: "serial" })`.
  - Two requests through the contract suite's in-process ASGI app didn't race: the lock's mutant passed. Race in a service test with the check's read slowed.
  - GitHub showed the gitleaks check "in progress" for hours after its job finished green. Read the job: `gh api repos/mechframe/mechframe/actions/jobs/<id>`.
  - CodeRabbit's free reviews run out mid-PR; its review then lands later, as one batch.
- **Still true:**
  - Run the full suite with `$env:PYTHONUTF8 = "1"`; it takes about 55 minutes.
  - Commit with `git commit -F <file>`, and check `git branch --show-current` first.
  - Never `prettier --write` an existing file.
  - On Windows, `npm run api:check` reports some `schema.ts` stale over line endings; CI on Linux is fine.
- **`CLAUDE.md` is about 175 lines.** Lean it when the owner says.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, never create the Buffer account, and never edit `C:\DEV\VM Website`.
