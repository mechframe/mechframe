# Next session, main lane (M4k): Dev 17's queued asks, then step 1's close

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-25-next-session-m4k-kit-to-boards.md and follow it, starting with section 4."

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe; M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** ("Two lanes" in `CLAUDE.md`). The side lane is building the refs hook (decision 0072), then featured. Tell it before and after every e2e run.
- **Yours:** the kit (`kernel/web/src/ui/`, `kit.css`'s `.mf-admin-look`), `kernel/web/src/ai/` and `kernel/web/src/admin/`, and `modules/contact/web/` (`ContactSettings.tsx`, `contact.css`). **Not yours:** `modules/featured/`, `modules/discography/`, `kernel/refs.py`, and SPEC 7's hooks table.
- **The site's session** is VM Website Dev 17 or its successor (Dev 19 was told #152). Send each PR number as it's pushed and as it lands. Never edit `C:\DEV\VM Website`; read its records only.
- **The owner's call:** Railway, CI's security gates, any third-party account or key.

## 3. State (verify it)

- **main:** this handoff's docs PR, on `bd0ce93` (#152, social). Check `git log -1 origin/main` and `gh pr list`.
- **The ledger:** rows from this handoff's `main`.

## 4. The job, in order

0. Land this handoff's PR if it's open: "CI result" green, the bots clear.
1. **A1 to A4, Settings › AI's Model row** (`kernel/web/src/ai/AiSettings.tsx`, `ModelRow`). The record is `C:\DEV\VM Website\dev plans\2026-11-24-admin-ai-parity.md` (A1 to A4, with pictures):
   - a rule above the row, 18 px each side;
   - the source sentence first;
   - one 12 px sentence under the select, in the hint's place;
   - Try again on the label's line.
   One small PR.
2. **The kit to the boards** (the owner: "Kit to the boards"), 22 lines: the ask's 19, then its addendum's 3. They're quoted in `C:\DEV\VM Website\dev plans\2026-11-24-admin-forms-kit-ask.md`, measured in `C:\DEV\VM Website\dev plans\2026-11-24-admin-writing-parity.md`, and drawn on the boards at `C:\DEV\VM Website\design\site\AdminAI.dc.html`, `AdminWriting.dc.html`, `AdminStyle.dc.html` and `AdminSettings.dc.html`.
   - **Lines 1 to 15, B1 to B10 and C1 to C5:** the parts every admin form shares.
   - **Lines 16 to 19, W2 to W4 and S1:** Writing's own.
   - **Line 20, C1 more:** drop the kit's 96 px minimum on a text box, so a box is as tall as its rows (a 3-row box 74 px on the board, 96 built).
   - **Lines 21 and 22, T1 and T2:** contact's settings section.
   - **Scope:** admin only, under `.mf-admin-look`. B4's hint goes under the control there, by CSS order, so member forms keep the kit's order.
   - **No contract:** the owner made the call. Amend decision 0040's line on the kit, and test each line at 1440 and 390 in both themes (`admin.spec.ts`'s way).
3. **Step 1's close:** its other three tests passed on 2026-11-25 (`docs/HANDOFF.md`). Once the site's parity tools say the boards hold, set Step 1 to done in `docs/progress.json` and run `python -m tools.progress`.
4. **Then the small follow-ups** (`docs/HANDOFF.md`, Next 3).

Close out at a natural break past ~400K tokens, with the main lane's prompt; the side lane writes its own.

## 5. Ask the owner, don't decide

`docs/HANDOFF.md`'s open questions: the Share card's board, discography's settings permission, the iPhone Safari check, the flaky axe test, hooks 6 to 8, the Vibrant Mindz content, `mechframe-iac-probe`.

## 6. Environment and traps

- **The full suite** takes about 55 minutes. Merge `main` first, then run it in the background with its log in the scratchpad:
  `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest --cov -q -rfE`
- **E2E:** with `TEST_DATABASE_URL` set (the owner's machine: the `devkit` role on port 55432), `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec>`. A spec that changes the site's one settings section runs serial.
- **More traps:** `docs/HANDOFF.md`, Notes.
- **Commits:** `git commit -F <file>`, after `git branch --show-current`. Resolve review threads by the comment's id.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; the contracts' "Changes after approval" (`social.md`).
- **IDs:** yours are 0068, 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane's are 0072 and up, `featured_0001` and `discography_0002`. Read each PR number from GitHub just before the push.

## 8. Candidates for `knowledge/`

1. Bash heredocs turn `\n` inside a Python string into a real line break: write scripts with the file tools.
2. Playwright workers run a spec's tests at once: a spec on one global setting needs `mode: "serial"`.
3. Two requests through an in-process ASGI app don't race. Slow the check's read in a service test, and prove it with a mutant.
