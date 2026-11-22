# dev plans

Session prompts and working plans, the owner's convention across `C:\DEV`. Each session ends with two starting prompts saved here (`CLAUDE.md`, "Two lanes", since 2026-11-22): `<date>-next-session-<topic>.md` for the main lane and `<date>-side-lane-<topic>.md` for the side lane, in a worktree. When a prompt's session is done, it moves to `done/`, so the ones left here are the jobs. Durable decisions go in `docs/decisions/`, not here.

`2026-11-22-media-round-3.md` is the two ways Admin › Media still differs from its board after round 2 (#126; round 2's queue and result are in `done/`), sent by VM Website Dev 10 with the owner's OK: the main lane's job after landing #129. The jobs now are `2026-11-22-next-session-m4-contact-round3-ai.md` (the main lane) and `2026-11-22-side-lane-m5-embeds-campaigns.md` (the side lane).

`progress-ledger/` is the source of the visual progress ledger, https://claude.ai/artifact/48auLkb7Ajmyn2SNAni9rm: its page (`index.html`) and the rows `python -m tools.progress` makes from `docs/progress.json` (`rows.json`); its README says how to republish it.

`2026-11-17-k3-gate-evidence.md` is the evidence K3's gate was checked on: each service's tests and coverage, the two named tests, and the kernel's contract lint (#75).

`2026-11-19-k45-screens/` holds the sign-in and account screens beside their boards, at 1440 and 390 px in both themes, with what differs and why (#83).

`2026-11-19-k46-admin/` holds the admin's Dashboard and Activity beside their boards (and the boards as drawn), at 1440 and 390 px in both themes, with what differs and why (#84).

`2026-11-19-k47-people-roles/` holds the admin's People and Roles beside their boards (and the boards as drawn), at 1440 and 390 px in both themes, with both dialogs, and what differs and why (#85).

`2026-11-19-k48-settings-system/` holds the admin's Settings tabs (Site, Features, System) at 1440 and 390 px in both themes, with failed jobs on System, and `README.md` saying what differs from `AdminSettings.dc.html` and why (#87).

`2026-11-20-k4-gate-evidence.md` is the evidence K4's gate was checked on (contract §7): the runs, each bullet's tests, the one finding (a stale People list after a save under load, fixed by #89), and the kernel's contract lint (#90).

`2026-11-21-vibrant-mindz-push-plan.md` is the road from hook 4 to Vibrant Mindz's step 1, with the site's front end built alongside in its own session (the owner's decisions of 2026-11-21).

`2026-11-20-k5-gate-evidence.md` is the evidence K5's gate was checked on (contract §7): the smoke's runs, alone and with the fixture modules, each bullet's tests, and the kernel's close (KICKOFF): SPEC 16's rows in CI, the scans, one gap for the first module, and the spec sections changed since K0 (#96).

`contracts/` holds the one-page contract each feature that touches a seam gets before its code (`C:\DEV\knowledge\decisions\0008-feature-contracts.md`):

| File | What |
| --- | --- |
| `contracts/k3-storage.md` | K3's storage service, `kernel.storage` (PR #58) |
| `contracts/k3-email.md` | K3's email service: `email.send`, templates, SMTP and Resend (PR #59) |
| `contracts/kernel-auth-templates.md` | K2's auth mails on `kernel.*` templates (PR #60) |
| `contracts/k3-jobs.md` | K3's jobs: the queue, the worker and the scheduler, `kernel.jobs` (PR #63) |
| `contracts/k3-events.md` | K3's events: `events.emit`, listeners delivered as jobs, dead letters, `kernel.events` (PR #65) |
| `contracts/k3-audit.md` | K3's audit log: `audit.record` for every module, the staff and own-activity reads, pruning, `kernel.audit` (PR #67) |
| `contracts/k3-notifications.md` | K3's notifications: `notifications.notify`, per-person preferences per key, one-click unsubscribe, `kernel.notifications` (PR #69 predicted) |
| `contracts/k3-moderation.md` | K3's moderation: reports, the staff queue, word and link filters, actions and suspension, `kernel.moderation` (PR #71) |
| `contracts/k3-public-rendering.md` | K3's public rendering: each page's head, words and JSON-LD in the shell, real 404s, `sitemap.xml`, `robots.txt`, `llms.txt`, `kernel.server_copy` (PR #73) |
| `contracts/k4-web-kernel.md` | K4's web kernel: the typed client, the app shell, session, guards, slots, themes, the UI kit, the auth and account screens and the admin shell (with role editing and System), in eight PRs from #78 |
| `contracts/k5-cli-and-site-template.md` | K5's CLI and site template: `mechframe new`, `add`, `remove`, `check`, `catalog` and `create-owner`, the lock file, `templates/site/` from the harness, the start command; approved 2026-11-20, five PRs from #91 |
| `contracts/site-frame.md` | The site's own header and footer (`defineSite({ header, footer })`, `SiteAccountLinks`) and pages that run full bleed (`bleed: true`), VM Website's item 5; approved 2026-11-21 as recommended (PR #106) |
| `contracts/media.md` | The media module: the library every module picks images from (images only, the public bucket, "Used in" with Delete waiting); approved 2026-11-21 as recommended |
| `contracts/after-footer.md` | A page's part after the site frame's footer (`<AfterFooter>`), VM Website's item 6: the owner's goal, the agent's interfaces (PR #113) |
| `contracts/pages.md` | The pages module: Markdown pages, their addresses and moves, the header's and footer's menus through link slots a module loads (decision 0056); approved 2026-11-21 with the owner's four answers (the kernel's editor in #118, the module in #121) |
| `contracts/blog.md` | The blog module: posts, the kernel's AI writing help, generated covers and social posting, in four PRs; approved 2026-11-22 for the first (#123, with decision 0057), §8 saying what's still to ask and §9 what changed as it was built |
| `contracts/contact.md` | The contact module: the `/contact` form and the admin's Inbox, held messages set apart as spam, a notice to the Inbox's readers (decision 0059's `notify_holders`) and a newsletter sign-up for `campaigns`; approved 2026-11-22 as recommended |
| `contracts/mechframe-upgrade.md` | M3's `mechframe upgrade kernel`: a site takes the kernel's changes from a Git ref, three ways against its lock, whole or not at all, with diffs for an agent where both sides changed; approved 2026-11-21 as recommended, built in #111 (decision 0053) |
| `contracts/hooks.md` | Decision 0018's ten contract hooks (decision 0052): content lifecycle, taxonomy, search index, seed data, bot check, consent, export and erase, dashboard cards, entitlements and profile tabs; one PR each from #97; draft, waiting for the owner |

`npm-audit-allowlist/`: the proposal for `npm audit` with an expiring allowlist, adopted 2026-11-17 (#75, decision 0015). The tool, its list and its tests now live in `tools/` and `tests/`; the README stays as the record of why.
