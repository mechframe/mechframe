# Next session, main lane (M4o): reactions 0.1.1, then comments' contract

Run from `C:\DEV\AI-DevKit`, the main checkout, on `main`. Follow this file from section 4.

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe. Vibrant Mindz's steps are the "site" phase of `docs/progress.json`; VM Website runs its staging.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** ("Two lanes" in `CLAUDE.md`). Tell the side lane before and after every e2e run.
- **Yours:** reactions, `modules/comments/` (from `modules/_comments/`), ask C (media and featured), the kernel and the kit. **Not yours:** discography and embeds (the side lane's ask B).
- **The site's session** is the newest VM Website Dev session: send it each PR number when pushed and when landed. Never edit `C:\DEV\VM Website`.
- **The owner's call:** each contract, Railway, CI's security gates, any third-party account or key, removing worktrees.

## 3. State (verify it)

Checked 2026-11-28, about 10:45 Eastern (15:45 UTC):
- **`main`:** 8e48530 (#171), then this handoff's docs PR (`docs/handoff-m4n`). Check `git log -1 origin/main` and `gh pr list`.
- **Versions:** blog 0.1.8, reactions 0.1.0, portfolio 0.1.0; the rest in `catalog.json`.
- **Progress:** v1.0 at 83% (51 of 61). Step 3: reactions and portfolio built; comments, then roster.

## 4. The job, in order

1. **Reactions 0.1.1** (VM Website Dev 28's X1 and X2; the owner: the board wins): in `modules/reactions/web/reactions.css`, drop `.mf-reaction-count`'s `tabular-nums`, and give `.mf-reaction` `line-height: normal` after its `font`. VM Website's page: `dev plans/2026-11-28-reactions-row-ask.md`. One small PR; done when the site's six Post states are exact at 1440 and 390.
2. **Comments' contract** (`_templates\feature-CONTRACT.md` into `dev plans/contracts/comments.md`, skill `mechframe-module-extractor`). Sources: the module plan's §9, `modules/_comments/`, the `k3-moderation` and `k3-notifications` contracts, hook 5, decision 0068. To the owner before any code. The boards (`C:\DEV\VM Website\design\site\`, read 2026-11-28):
   - **`Post.dc.html`:** Top or Newest; the form (Name, Email "(never shown)", "Email me replies", guests' and first comments wait for approval); each comment's name, role badge, time, heart and count, Reply, Report; "This comment was removed." keeps its replies; replies one level in.
   - **`AdminComments.dc.html`:** Waiting, Approved, Spam; Approve, Don't publish, Spam; "The oldest has waited [n] days"; "Spam teaches the filter."
   - **`AdminSettings.dc.html`:** the Comments switch.
3. **Build comments** in one PR (`module-contract-lint`); before the push, run `tests/` and `kernel/tests/contract/` too (memory note "New module: hidden tests").
4. **Ask C's contract:** VM Website's `dev plans/2026-11-28-ask-c-uploaded-video.md`, under its `contracts/player-sources.md`. It changes decision 0054 and discography's non-goal.
5. **Roster last.** Close out at a natural break past ~400K tokens; both lanes' prompts are yours.

## 5. Ask the owner, don't decide

- **Comments:** does each comment take reactions' heart; replies one level (the board) or two (the plan); "Spam teaches the filter" with no learning filter; confirming a guest's address before mailing replies; how approved comments join the post's server copy.
- **Roster:** the profile-tabs hook, and an own-profile permission apart from staff's (decision 0074).
- Removing the standby worktrees, and the two memory notes marked "can be deleted".

## 6. Environment and traps

- **Full Python suite:** about 30 minutes; merge `main` first, run it in the background: `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest -q`.
- **E2E:** `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec> --workers=1`.
- More in `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; `dev plans/contracts/reactions.md`.
- **IDs:** decisions 0069 and 0080 to 0089, `kernel_0017`, `kernel_0018`, `blog_0002`, `comments_0001`, `media_0002`, `featured_0002`. The side lane has 0075 to 0079, `discography_0002`, `embeds_0001`. PR numbers from GitHub just before each push.

## 8. Candidates for `knowledge/`

`docs/HANDOFF.md`'s "Traps met": read TanStack's cache when a part acts; two modules' answer models of one name rename the kernel's; `require_owner_or(p)` passes staff holding `p` on anything.
