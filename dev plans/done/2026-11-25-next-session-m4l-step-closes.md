# Next session, main lane (M4l): lean CLAUDE.md, steps 1 and 2's closes, then step 3's order

Run from `C:\DEV\AI-DevKit`, the main checkout. Follow this file from section 4.

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe. Vibrant Mindz's steps are the "site" phase of `docs/progress.json`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** ("Two lanes" in `CLAUDE.md`). Tell the side lane, on discography 0.1.3, before and after every e2e run.
- **Yours:** the kit (`kernel/web/src/ui/`), `kernel/web/src/admin/`, the AI's code and its tests (`kernel/web/src/ai/`, `kernel/backend/kernel/ai.py`, `kernel/backend/kernel/ai_routes.py`, `kernel/tests/test_ai.py`, `kernel/tests/contract/test_ai_contract.py`, `kernel/tests/e2e/ai.spec.ts`), and step 1's modules. **Not yours:** `modules/discography/`, `featured/`, `audio-player/` (ask the side lane first) and `kernel/backend/kernel/refs.py`.
- **The site's session** is the newest VM Website Dev session. Send it each PR number as it's pushed and as it lands. Never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key, and a new module's contract.

## 3. State (verify it)

Checked on 2026-11-26, about 06:30 Eastern:
- **`main`** is 2e3b155 (#161). This session's handoff, #162 on `docs/handoff-m4k`, is docs only. Once it lands, `main` is its head, and the checkout should be on `main`.
- **Open PRs:** only #162. The side lane's discography 0.1.3 runs on `feat/discography-0-1-3`, with no PR yet.
- **Versions:** blog 0.1.6, embeds 0.1.1, contact 0.1.2, audio-player 0.1.1, discography 0.1.2, featured 0.1.0.
- **Progress:** v1.0 is at 80% (49 of 61). Steps 1 and 2 are "next". Deployed: nothing.
- **Half-done:** nothing in this lane. VM Website's owner is reviewing the site's short list and the `.mf-player-hint` question.

## 4. The job, in order

0. Land #162 if it's still open: "CI result" green, the bots clear.
1. **Lean `CLAUDE.md`** (the owner: "Lean it soon") with `C:\DEV\LEAN-CONTEXT-PROMPT.md`, as its own docs PR. Change `AGENTS.md` too: it's the same text under its own first line.
2. **VM Website's asks as they come:** the short list (card titles' line height, a few cases at 390), and `.mf-player-hint`, whose `font-size` is a whole font shorthand.
3. **Step 1's close,** once the site says the boards hold. Its other three tests passed on 2026-11-25. Set the row to done, then run `python -m tools.progress`.
4. **Step 2's close** (the owner: "All four, like Step 1"): schemas, tests on `main`, `mechframe check` on a fresh site with step 2's modules, and VM Website's board check. The owner's iPhone Safari check of the player comes first.
5. **Diagnose the flaky axe test** at `kernel/tests/e2e/sign-in.spec.ts:389`, the `DEBUG_PROTOCOL.md` way.
6. **Step 3** (roster, portfolio, reactions, comments): ask the owner its order and lanes first. The recommendation is reactions first, since comments use it (`docs/plans/vibrant-mindz-backend/extraction/reactions.md`). Each contract comes first, for the owner's approval.

Close out at a natural break past ~400K tokens. Both lanes' prompts are yours.

## 5. Ask the owner, don't decide

Step 3's order and lanes, and the Player section's 16px gap. The rest are answered in `docs/HANDOFF.md`, under "Owner's answers".

## 6. Environment and traps

- **The full suite** takes about 21 minutes. Merge `main` first, then run it in the background with its log in the scratchpad: `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest -q`.
- **E2E:** with `TEST_DATABASE_URL` set, run `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec>` (141 tests, about 3 minutes).
- **Before `git switch -c`,** switch to `main`. Run `gh api --jq` through the Bash tool, and commit with `git commit -F <file>`.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; decision 0040's two amendments; the bodies of #156, #158, #160 and #161.
- **IDs:** yours are 0068, 0069, `kernel_0017`, `kernel_0018` and `blog_0002`. The side lane has 0074 and up and `discography_0002`. Read each PR number from GitHub just before you push.

## 8. Candidates for `knowledge/`

1. A branch is cut from the one you're on: `git switch main` first.
2. Test a two-condition gate with a mutant for each condition.
3. axe's `label-content-name-mismatch`: a button's visible words must appear in its name.
4. A first-load shift test: hold the reads back with `page.route`, answering GET only, and add up the shifts after `<main>`.
