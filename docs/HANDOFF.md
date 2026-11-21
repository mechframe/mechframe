# Handoff

Overwritten every session. This one: 2026-11-21, afternoon Eastern (Claude Code, the owner's machine), session M2 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`: hooks 6, 7 and 8 (#107, #109, #110), with hooks 1 to 8 of the ten now in. A second MechFrame session ran alongside, at the owner's start (#105, #106, #108 and #111). `main` is `096e51e`.

## State

- **The kernel is done**, K0 to K5. K2's steps 9 to 11 still wait for the site (decision 0029).
- **Hooks 1 to 8 of the ten are in** (decision 0052, its Status "Hooks 1 to 8 applied"; `dev plans/contracts/hooks.md`): content lifecycle (#97), taxonomy (#98), search index (#99), seed data (#102), bot check (#103), consent categories (#107), export and erase (#109), dashboard cards (#110). Entitlements and profile tabs wait (decision 0052, item 11). Vibrant Mindz's step 1 (its modules) can start.
- **#107, hook 6, consent categories**, landed at `69bd37a`. A `CSP` entry's third item is its category: `necessary` by default, or `analytics`, `marketing` or `media`; the start refuses any other. The CSP itself doesn't change. `GET /api/kernel/site` gains `consent: {mode, categories}`, and `CONSENT_MODE` (`ask` or `off`) is in `KernelConfig`, both `.env.example` files and the template's `railway.ts`. The web side is `useConsent(category)` (`{granted, grant, withdraw}`) and `<ConsentGate category fallback>` (`fallback(grant)` for an embed's facade), in `kernel/web/src/consent/`. The choice is kept in `__Host-mf_consent`: the granted categories joined by dots, 180 days, set by script.
- **#109, hook 7, export and erase**, landed at `7ac07f2`.
  - `kernel.privacy`: `privacy.py`'s `export_user_data(db, subject)` and `delete_user_data(db, subject)`, with `Subject` `{user_id, email}`. The start refuses `data_hooks` that disagree. `erase` waits for K2's step 11.
  - `kernel/auth/exports.py` builds 14.7's export. `POST /api/auth/account/export` asks for a copy: step-up, once an hour, storage on.
  - The job `kernel.privacy_export` writes a ZIP of `kernel.json` and one file per module to private storage, at `kernel/exports/<id>.zip`. It mails `kernel.data_export_ready`, or `_failed` on its last try.
  - `GET /api/auth/account/exports/{id}` answers 303 to a 5-minute download, for the account's own owner only. `kernel.prune_exports` removes a copy hourly after its 7 days.
  - The table is `kernel_export` (`kernel_0015`). The account page has a "Your data" card.
  - The contract suite's in-process harness keeps files in a fake S3 (moto) and reads them back with `GET /api/_test/files`.
  - Codex's two findings, fixed with tests: asking needs a confirmed address (403 `auth.email_unverified`), since a module finds data by address; and the prune deletes each copy's own key whether or not its row recorded it.
  - CodeRabbit's seven findings, each answered:
    - `kernel_export.user_id` is `ON DELETE SET NULL`, so a deleted account's copy stays tracked for the prune.
    - The export has its own time limit, 28 of the job's 30 minutes, so running out of time is an ordinary failure, marked on the last try, while a worker's shutdown leaves the job to its lease.
    - The prune locks each row and checks its expiry again, and deletes nothing while storage is off.
    - A copy still queued a day after it was asked for, with no job of its own queued or running (its job lost with a worker), is failed by the prune and its owner told. A try marks a copy ready only while it's still queued, and one that finds it already ready (overlapping tries) leaves its file.
    - The ZIP is made in a thread.
    - The downgrade's notes say what it leaves in storage.
  - The local suite's own finding: the contract suite's fake storage now lives per test, not per session, so it no longer leaks into later tests.
- **#110, hook 8, dashboard cards**, landed at `096e51e`.
  - `dashboard.py`'s `SETUP` (`setup.Step(key, title, why, link, permission, done)`) and `ATTENTION` (items naming their `permission`).
  - "Needs you" adds the modules' items, and `GET /api/kernel/admin/setup` serves the Dashboard's Set up card.
  - The hooks' unit tests now restore the kernel's globals with `monkeypatch`. A mutant showed the old fixtures hid a server that never installed them.
  - Codex's finding, fixed with tests: each setup check and each module's `ATTENTION` runs in a savepoint, so a database error in one doesn't abort the request's transaction.
  - CodeRabbit's findings, fixed with tests: a provider's answer is checked inside its guard; an item must name a declared permission (an owner holds every one); a setup link with a backslash or a control character is refused; the export's try re-checks that the address is confirmed.
- **The other MechFrame session's work**, all landed:
  - #105, `line-4` and the gap ring on admin fields.
  - #106, the site's own header and footer and full-bleed pages (`dev plans/contracts/site-frame.md`, decision 0048 amended).
  - #108, the `mechframe upgrade kernel` contract, approved by the owner, and #111, the command itself (decision 0053), which was M3's first job.
- Mutants caught: 18 for hook 6, 19 for hook 7, 17 for hook 8, and the four "never installed" ones.
- **v1.0:** 78% (48 of 61 steps). The ledger was republished from `096e51e`.

## Next

1. **Session M3** (`dev plans/2026-11-21-next-session-m3-media.md`): `media`, since `mechframe upgrade kernel` is in (#111).
2. M4 and M5 as the plan has them.

## Open questions for the owner

- **Hooks 6 to 8's changes after approval** (the contract's list): override any you'd rather. Hook 6 added `withdraw()`; hook 7's ZIP holds the kernel's own `kernel.json`; hook 8's items are dropped unless they name a permission.
- **The parallel sessions:** the PC ran at 90 to 100% CPU with several sessions at once, so local full suites crawled. #107 was pushed with CI as its gate (the owner, 2026-11-21: "Push now, CI gates"). CodeRabbit's free reviews ran out with two sessions' PRs.
- **A public name and handle for a person**, before hook 10, which waits for wave 2b.
- **The Vibrant Mindz content** (`C:\DEV\VM Website\design\specs\content-intake.md`).
- `mechframe-iac-probe` on Railway; a Railway variable to confirm a destructive migration; seven unused ledger assets; cubic and CodeRabbit's limits; rewording the kernel's screens; the R2 test buckets; renaming the folder and the `devkit-*` skills.

## Notes

- **PR numbers go fast with two sessions:** predict at push time (the highest plus one), and check again just before.
- **The full suite takes about 25 minutes on a quiet machine,** and hours at full load. Run it in the background with its log in the scratchpad, and edit nothing in that checkout meanwhile: CLI tests copy the kernel. A worktree under `.claude/worktrees/` lets work go on beside it. Use this checkout's `.venv` python and a junction to its `node_modules`; Python imports the worktree's kernel.
- **`eslint .` also scans `.claude/worktrees/`:** while another worktree has work in progress, lint by folder (`npx eslint kernel harness modules`).
- **The suite's `jobs/run` doesn't tick the scheduler:** queue a scheduled job by name (`POST /api/_test/jobs {name}`).
- **A 404 `kernel.not_found` reads as "not built"** to the contract client: a test-support route answers its own code (`harness.no_file`).
- **A unit fixture restores a kernel global with `monkeypatch.setattr`**, never by installing the probe's parts again.
- **Git writes CRLF on a stash pop or a merge here,** and the Bash tool decodes `\n` and `\uXXXX`. Patch scripts go through the Write tool, match after `.replace("\r\n", "\n")`, and build a CR with `chr(13)`.

## Warnings

- **An account deleted while its copy is stored** leaves the row, its owner null, until the hourly prune takes it and its file after 7 days. K2's step 11 should delete a person's copies at once, with `privacy.erase`.
- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner.
- Never edit `C:\DEV\VM Website`: a Vibrant Mindz session works there.
