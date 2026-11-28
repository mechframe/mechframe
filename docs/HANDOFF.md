# Handoff

Overwritten every session. This one: 2026-11-27, about 14:00 Eastern, to 2026-11-28, about 06:00 (11:00 UTC) (Claude Code, the owner's machine, the owner on Remote Control at times), session M4m, the main lane. Landed: #168. The side lane landed #167 (discography 0.1.4). `main` was de279f9 (#168), and this handoff is its own docs PR.

## State

- **Step 1 is done (#168).** VM Website Dev 25's board check of #165 (`C:\DEV\VM Website\dev plans\2026-11-27-kit-165-parity.md`, canvas 121) held, with two asks, both done tests first:
  - **D1:** a dialog's title in the admin uses the font's own line height (`kit.css`, `.mf-dialog-title`), the card title's other half.
  - **R8:** the AI's problem line (Write with AI's, and a writing style's "has that name") uses the small size in the font's own line (`ai.css`, `.mf-ai-problem`).
  - Decision 0040 is amended a fourth time. K9's "15px words" was dropped: the site didn't ask again.
- **Two e2e flakes fixed in #168:**
  - `settings.spec.ts` failed on #165's head: while Probe was switched off in one worker, a probe.fail job run in another waited instead of failing. Now the file's tests run in order in one worker (`mode: "default"`), the jobs test before the switch.
  - Campaigns' axe test caught Save draft fading to its colour, at 1.7 to 1 in 10 of 41 CI runs. The shared `axe()` (`kernel/tests/e2e/support.ts`) now waits for each running animation that ends. A 3-second transition as the mutant failed before the fix.
  - **The flaky axe test at `sign-in.spec.ts:389`** (the old job 4) is answered: 7f849b8 had fixed it, with 0 failures in 41 CI runs since. The local timeout was the PC's load.
- **Step 2 is done (this PR).** Its four tests, on 2026-11-28:
  - the manifests against the schemas;
  - CI and E2E on `main` (de279f9);
  - `mechframe check` on a fresh site with media, embeds, audio-player, discography and featured;
  - VM Website Dev 27's board check of Admin › Music with discography 0.1.4 (`2026-11-28-kit-168-discography-014-parity.md`): the boards hold, nothing new to ask. Its leftovers are as recorded before, plus its own stage B (Bandcamp's player).
- **The owner moved the iPhone Safari check** of the player to the site's deploy, once its audio uploads are set up. An upload can't be made yet: with storage off, discography answers 503, and the phone needs HTTPS for the consent cookie. It's in audio-player's contract ("Changes after approval"), and VM Website keeps it on its deploy list.
- **The side lane** landed #167, discography 0.1.4 (its Result is in `dev plans/done/2026-11-27-side-lane-m13-discography-0-1-4.md` §9). That covers K11's `QuietLink` for "Open the release" and its e2e spec split into three tests run in order.
- **Progress:** v1.0 is at 83% (51 of 61). Step 3 is next, with the owner's order in its row. **The ledger** shows this PR's rows.

## Next

1. **Main lane, step 3 in the owner's order** (2026-11-28): reactions' contract, then the module, then comments' contract and module. Each contract goes to the owner first. Roster comes last, with the profile-tabs hook.
2. **Side lane, portfolio:** its contract, then the module, in a worktree.
3. **VM Website's asks for its players' sources** stage B (Bandcamp's player) and stage C (uploaded video, Media's Video tab, straight-to-bucket uploads) will come on its owner's OK. Which lane takes them, and when, is the owner's call.

## Open questions for the owner

- Reactions' contract, and later comments' and portfolio's.
- Removing the five old standby worktrees under `.claude/worktrees/` (the side lane's `discography-0-1-0` stays), and the two memory notes marked "can be deleted".
- The Vibrant Mindz content.

## Notes

- **IDs:** the main lane used none. It has decisions 0068, 0069 and 0080 to 0089, `kernel_0017`, `kernel_0018`, `blog_0002`, `reactions_0001` and `comments_0001`. The side lane has decisions 0074 to 0079, `discography_0002` and `portfolio_0001`.
- **Traps met:**
  - **A spec that switches a module off** stops the worker claiming that module's jobs, so another spec's job of it waits. Run such a file in one worker, in order.
  - **axe measures colour mid-transition:** wait for running animations whose end is finite before `analyze()`.
  - **The site's CSP blocks `page.addStyleTag`:** a throwaway diagnostic spec needs `test.use({ bypassCSP: true })`.
  - **A transient `[Errno 10048]`** on port 8765 at an e2e start: nothing was listening afterwards, and a rerun passed.
  - **A cross-session send by name** can match two sessions: use the `[ref]` the listing shows.
- **Still true:**
  - The full Python suite takes about 40 minutes with the PC shared (3,910 tests). The e2e suite has 151 tests; on a shared PC, check `Get-Process` before diagnosing a timeout.
  - Commit with `git commit -F <file>` after `git branch --show-current`. Never `prettier --write` an existing file.
  - On Windows, the generators rewrite some `schema.ts` files with CRLF only: `git checkout` them.
  - **`docs/progress.json`:** `json.dumps` rewrites its whole layout. Edit a step's one line in place.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, never create a third-party account, and never edit `C:\DEV\VM Website`.
