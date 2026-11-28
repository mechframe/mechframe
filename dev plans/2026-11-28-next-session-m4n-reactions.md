# Next session, main lane (M4n): step 3, reactions first, contract first

Run from `C:\DEV\AI-DevKit`, the main checkout, on `main`. Follow this file from section 4.

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe. Vibrant Mindz's steps are the "site" phase of `docs/progress.json`. Nothing of MechFrame's is deployed; VM Website runs the site's staging, https://vybesite.com, from its own session.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** ("Two lanes" in `CLAUDE.md`). Tell the side lane, on portfolio, before and after every e2e run.
- **Yours:** `modules/reactions/` and later `modules/comments/` (both new), with their contracts; the kernel, the kit and `kernel/web/src/admin/`; step 1's modules and audio-player.
- **Not yours:** `modules/portfolio/` and its contract (the side lane's), `modules/discography/` and `modules/featured/`. Ask the side lane first.
- **The site's session** is the newest VM Website Dev session (Dev 27 last). Send it each PR number when it's pushed and when it lands. Never edit `C:\DEV\VM Website`.
- **The owner's call:** each new module's contract, Railway, CI's security gates, any third-party account or key, and removing worktrees.

## 3. State (verify it)

Checked 2026-11-28, about 06:00 Eastern (11:00 UTC):
- **`main`:** de279f9 (#168). This handoff is a docs PR on `docs/handoff-m4m`. Once it lands, `main` is its head. Check `git log -1 origin/main` and `gh pr list`.
- **CI and E2E** were green on de279f9.
- **Versions:** media 0.1.4, pages 0.1.1, blog 0.1.7, contact 0.1.2, embeds 0.1.1, campaigns 0.1.1, discography 0.1.4, audio-player 0.1.2, featured 0.1.0, social 0.1.0.
- **Progress:** v1.0 at 83% (51 of 61). Steps 1 and 2 are done; step 3 is next, with the owner's order in its row. The ledger shows this handoff's rows.

## 4. The job, in order

0. Land the handoff's PR if it's still open: "CI result" green, the bots clear.
1. **Reactions' contract,** from `C:\DEV\_templates\feature-CONTRACT.md` into `dev plans/contracts/reactions.md`.
   - Sources: `docs/plans/vibrant-mindz-backend/extraction/reactions.md` (VybeMindz's reactions and custom emojis), the module plan's §8 and §9 (shared by comments and community), and `docs/private/inventory.md` for where to lift from.
   - Ask the site's session which boards draw reactions, if any.
   - It goes to the owner before any code. Use the `mechframe-module-extractor` skill.
2. **Build reactions** in one PR, linted with `module-contract-lint`. Before the push, run `tests/` and `kernel/tests/contract/` too (the memory note "New module: hidden tests").
3. **Comments' contract, then the module,** from its scaffold `modules/_comments/`: threads on any module's item (module plan §9). The kernel's notifications and moderation are done.
4. **Roster comes last,** after portfolio, with the profile-tabs hook (`dev plans/contracts/hooks.md`).

Close out at a natural break past ~400K tokens. Both lanes' prompts are yours.

## 5. Ask the owner, don't decide

- Each contract.
- VM Website's asks for its players' sources: stage B (Bandcamp's player) and stage C (uploaded video, Media's Video tab, straight-to-bucket uploads), on its owner's OK. Which lane takes them, and when.
- Removing the five old standby worktrees under `.claude/worktrees/` (the side lane's `discography-0-1-0` stays), and the two memory notes marked "can be deleted".
- The Vibrant Mindz content.

## 6. Environment and traps

- **This PC is shared.** Before diagnosing an e2e timeout, check what's busy: `Get-Process`, CPU over 5 seconds. `--workers=1` held.
- **Full Python suite:** about 40 minutes (3,910 tests). Merge `main` first, then run it in the background, its log in the scratchpad: `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest -q`.
- **E2E:** with `TEST_DATABASE_URL` set, `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec>` (151 tests).
- **More traps:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`, #168's body, and VM Website's `dev plans/2026-11-28-kit-168-discography-014-parity.md`.
- **IDs:** yours are decisions 0068, 0069 and 0080 to 0089, `kernel_0017`, `kernel_0018`, `blog_0002`, `reactions_0001` and `comments_0001`. The side lane has 0074 to 0079, `discography_0002` and `portfolio_0001`. Read each PR number from GitHub just before the push.

## 8. Candidates for `knowledge/`

1. A spec that switches a module off races other specs' jobs of it: run it serially.
2. axe measures colour mid-transition: wait for running, finite animations first.
3. A site's CSP blocks `page.addStyleTag`: a diagnostic spec needs `bypassCSP`.
4. Tests read docs, and a docs-only PR runs none: grep before moving text.
5. Before an e2e timeout hunt on a shared PC, measure CPU by process.
