# MechFrame progress

Generated from `docs/progress.json` by `python -m tools.progress`: edit the JSON, then run the tool. `tests/test_progress.py` fails when this page is stale. The same data feeds the [visual progress ledger](https://claude.ai/artifact/48auLkb7Ajmyn2SNAni9rm).

Updated 2026-11-27, `main` at `89ed7e2`. Progress counts steps, not effort: each row below is one step, whatever its size.

## Overall

| Milestone | Done | In review | Next | To do | Waiting | Later | Progress |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| MechFrame v1.0 | 51 | 0 | 1 | 4 | 3 | 2 | ████████░░ 83% (51 of 61) |
| After v1.0 | 0 | 0 | 0 | 86 | 0 | 3 | ░░░░░░░░░░ 0% (0 of 89) |
| Everything | 51 | 0 | 1 | 90 | 3 | 5 | ███░░░░░░░ 34% (51 of 150) |

## MechFrame v1.0

The kernel, the CLI and the first validation modules, frozen once blog, chat and payments pass the quality gate on the Vibrant Mindz build (SPEC 19).

### Spec v0.1 · 1 of 1 done

The contract every module, the kernel and the CLI follow.

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| Spec v0.1 written, the owner's answers applied | Done |  | [0001](decisions/0001-backend-python-fastapi.md), [0002](decisions/0002-copy-in-modules.md), [0003](decisions/0003-homemade-auth.md) |  |

### K0: repo foundation · 3 of 3 done · gate passed

Python, the harness, Alembic, the web workspace and CI.

Gate: pytest, npm test and the schema checks pass; CI green.

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| Python environment, harness, Alembic, web workspace, CI | Done |  |  |  |
| The audit's fixes and the review bots' follow-ups | Done |  |  | PRs #1 to #24 |
| The owner's follow-ups: history rewrite, ruleset on main, pinned actions | Done |  |  | PRs #25 to #31 |

### K1: kernel core · 3 of 3 done · gate passed

The database, settings, module switches, crypto, errors, rate limits, access marks and the app factory.

Gate: Tests for each piece, secret refusal, CSP headers, a switched-off module answering 404, the migration round trip.

Done: `Database, settings and module switches`, `Crypto, errors, rate limits and access marks`, `The app factory, security headers and CSP`.

### K2: auth · 8 of 11 done · gate not passed yet

The complete auth system of SPEC 14, test-first.

Gate: Every 14.13 contract test passes; each sign-in method works by hand; brand check, gitleaks and pip-audit clean.

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| 1. The contract suite, written first | Done |  |  | 128 pass; 27 wait on steps 9 to 11 |
| 2. Accounts, roles and per-resource overrides | Done | [#36](https://github.com/mechframe/mechframe/pull/36), [#56](https://github.com/mechframe/mechframe/pull/56) | [0031](decisions/0031-moderation-permission.md) |  |
| 3. Passwords | Done | [#7](https://github.com/mechframe/mechframe/pull/7), [#10](https://github.com/mechframe/mechframe/pull/10) |  |  |
| 4. Sessions | Done | [#32](https://github.com/mechframe/mechframe/pull/32), [#33](https://github.com/mechframe/mechframe/pull/33) |  | The device list's three routes were never built, and no contract test calls them (found 2026-11-18): they moved to K4's step "Auth and account screens, with the device routes" |
| 5. Sign-in codes and magic links | Done | [#42](https://github.com/mechframe/mechframe/pull/42) | [0021](decisions/0021-codes-and-links.md) |  |
| 6. Reset, verification and email change | Done | [#39](https://github.com/mechframe/mechframe/pull/39), [#43](https://github.com/mechframe/mechframe/pull/43), [#44](https://github.com/mechframe/mechframe/pull/44), [#45](https://github.com/mechframe/mechframe/pull/45), [#46](https://github.com/mechframe/mechframe/pull/46) | [0020](decisions/0020-sign-up-defaults.md), [0022](decisions/0022-password-resets.md), [0023](decisions/0023-verification-resend.md), [0024](decisions/0024-email-change.md), [0025](decisions/0025-password-change.md) |  |
| 7. Second factors and step-up | Done | [#38](https://github.com/mechframe/mechframe/pull/38), [#47](https://github.com/mechframe/mechframe/pull/47), [#48](https://github.com/mechframe/mechframe/pull/48), [#52](https://github.com/mechframe/mechframe/pull/52) | [0019](decisions/0019-sign-in-limits-as-tiers.md), [0026](decisions/0026-totp-setup-and-confirm.md), [0027](decisions/0027-totp-removal-and-recovery-codes.md) |  |
| 8. Passkeys, and the undo link for an added factor | Done | [#50](https://github.com/mechframe/mechframe/pull/50), [#54](https://github.com/mechframe/mechframe/pull/54) | [0028](decisions/0028-passkeys.md), [0030](decisions/0030-second-factor-undo.md) |  |
| 9. OAuth and OpenID Connect | Waiting |  |  | Before the site's launch at step 5 |
| 10. Invites and API keys | Waiting |  |  | Invites before the site's step 4; API keys after |
| 11. Abuse protection, deletion and data export | Waiting |  |  | Before the site's launch at step 5 |

### K3: kernel services · 10 of 11 done · gate passed

Everything else modules rely on, in the order the site's modules use it.

Gate: Tests for each service; an event delivered once to a handler safe to run twice; a job surviving a worker restart. Checked on the nine services built; retention and the AI client are outside it (the owner, 2026-11-17).

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| Storage | Done | [#58](https://github.com/mechframe/mechframe/pull/58) | [0032](decisions/0032-kernel-storage.md) |  |
| Email: templates, SMTP first, Resend where SMTP is blocked | Done | [#59](https://github.com/mechframe/mechframe/pull/59) | [0033](decisions/0033-kernel-email.md) |  |
| The kernel's own mails as templates a site can reword | Done | [#60](https://github.com/mechframe/mechframe/pull/60) | [0033](decisions/0033-kernel-email.md) |  |
| Jobs: the Postgres queue, the scheduler, mail retries | Done | [#63](https://github.com/mechframe/mechframe/pull/63) | [0035](decisions/0035-kernel-jobs.md) |  |
| Events: emitted in the caller's transaction, delivered as jobs, dead letters | Done | [#65](https://github.com/mechframe/mechframe/pull/65) | [0036](decisions/0036-kernel-events.md) |  |
| Audit: one append-only log for every module, auth's widened | Done | [#67](https://github.com/mechframe/mechframe/pull/67) | [0037](decisions/0037-kernel-audit.md) |  |
| Notifications, with per-person preferences and one-click unsubscribe | Done | [#69](https://github.com/mechframe/mechframe/pull/69) | [0038](decisions/0038-kernel-notifications.md) |  |
| Moderation: reports, the staff queue, filters and actions | Done | [#56](https://github.com/mechframe/mechframe/pull/56), [#71](https://github.com/mechframe/mechframe/pull/71) | [0031](decisions/0031-moderation-permission.md), [0039](decisions/0039-kernel-moderation.md) |  |
| Public rendering: head tags, server copy, sitemap, robots, llms.txt | Done | [#73](https://github.com/mechframe/mechframe/pull/73) | [0041](decisions/0041-public-rendering.md) |  |
| Retention | Later |  |  | Outside K3's gate (the owner, 2026-11-17); its tests come with it |
| The AI client | Done | [#135](https://github.com/mechframe/mechframe/pull/135) | [0058](decisions/0058-ai-writing-help.md) | ai.client(db), the key saved in Settings → AI or the host's, the writing rules and styles, and Write with AI in every editor (#135) |

### Rename to MechFrame · 2 of 2 done

AI DevKit became MechFrame once K3 was done (decision 0034).

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| One PR: prose, packages, cookies, variables, skills and links say MechFrame | Done | [#76](https://github.com/mechframe/mechframe/pull/76) | [0034](decisions/0034-rename-to-mechframe.md) |  |
| The owner moves the repo to github.com/mechframe/mechframe and installs the review bots there | Done |  | [0034](decisions/0034-rename-to-mechframe.md) | 2026-11-18: transferred; Codex, CodeRabbit and cubic review there |

### K4: web kernel · 8 of 9 done · gate passed

The front-end half of the kernel.

Gate: Component tests, axe with no serious violations, Playwright runs of every sign-in method. Checked against the contract's §7 on main after #89 (dev plans/2026-11-20-k4-gate-evidence.md).

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| The typed client: every answer typed, the committed specs, api and its hooks | Done | [#78](https://github.com/mechframe/mechframe/pull/78) | [0042](decisions/0042-web-kernel.md) |  |
| The app shell: router, useSession, guards, slots, the kernel's pages, server copy, Playwright | Done | [#79](https://github.com/mechframe/mechframe/pull/79) | [0042](decisions/0042-web-kernel.md) |  |
| Themes: Machined Light and Vibrant Mindz on the kernel's tokens | Done | [#80](https://github.com/mechframe/mechframe/pull/80) | [0042](decisions/0042-web-kernel.md) |  |
| UI kit, moved to React 19 and tokens | Done | [#82](https://github.com/mechframe/mechframe/pull/82), [#101](https://github.com/mechframe/mechframe/pull/101) | [0042](decisions/0042-web-kernel.md) |  |
| Auth and account screens, with the device routes | Done | [#83](https://github.com/mechframe/mechframe/pull/83) | [0042](decisions/0042-web-kernel.md), [0043](decisions/0043-sign-in-and-account-screens.md) |  |
| Admin shell: sidebar, top bar, Dashboard and Activity | Done | [#84](https://github.com/mechframe/mechframe/pull/84) | [0042](decisions/0042-web-kernel.md), [0044](decisions/0044-admin-shell.md) |  |
| Admin people and roles, with role editing | Done | [#85](https://github.com/mechframe/mechframe/pull/85), [#88](https://github.com/mechframe/mechframe/pull/88), [#89](https://github.com/mechframe/mechframe/pull/89) | [0042](decisions/0042-web-kernel.md), [0045](decisions/0045-people-and-roles.md) |  |
| Admin settings: Site, Features and System | Done | [#87](https://github.com/mechframe/mechframe/pull/87) | [0042](decisions/0042-web-kernel.md), [0046](decisions/0046-settings-features-system.md) |  |
| Depth theme | Later |  |  | The owner, 2026-11-18: when a site wants it |

### K5: CLI and site template · 5 of 5 done · gate passed

mechframe works end to end.

Gate: mechframe new test-site builds, migrates and passes its tests; mechframe check passes on it. Checked against the contract's §7 on main at b543642, alone and with the fixture modules added (dev plans/2026-11-20-k5-gate-evidence.md).

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| The mechframe commands and lock files | Done | [#91](https://github.com/mechframe/mechframe/pull/91), [#92](https://github.com/mechframe/mechframe/pull/92), [#94](https://github.com/mechframe/mechframe/pull/94), [#95](https://github.com/mechframe/mechframe/pull/95) | [0047](decisions/0047-cli-and-site-template.md), [0048](decisions/0048-site-pages-and-template.md), [0050](decisions/0050-add-and-remove.md), [0051](decisions/0051-create-owner.md) | check and the lock in #91; new (kernel only) in #92; add, remove and new --recipe in #94; create-owner in #95; diff and upgrade wait for a module's second version (the owner, 2026-11-20) |
| templates/site, made from the harness | Done | [#92](https://github.com/mechframe/mechframe/pull/92) | [0047](decisions/0047-cli-and-site-template.md), [0048](decisions/0048-site-pages-and-template.md) | the site's own pages (create_app(site=), defineSite), kernel.load_module, the site's tests and CI, tools/site_smoke.py |
| The start command and .env.example for a host's edge | Done | [#92](https://github.com/mechframe/mechframe/pull/92) | [0048](decisions/0048-site-pages-and-template.md) | the Dockerfile's start command reads the proxy's headers; .railway/railway.ts (Railway as code) in place of railway.toml, checked live on a throwaway project |
| mechframe catalog | Done | [#91](https://github.com/mechframe/mechframe/pull/91) | [0047](decisions/0047-cli-and-site-template.md) |  |
| SPEC 10's confirmation before a destructive migration | Done | [#93](https://github.com/mechframe/mechframe/pull/93) | [0049](decisions/0049-destructive-migrations-wait.md) | kernel.migrate: once its branch holds data, an upgrade stops before a revision marked destructive = True until --confirm-destructive names it; the owner, 2026-11-20: before any module with migrations |

### Contract hooks · 8 of 10 done

The ten hooks the Must modules need (decision 0018), in the shapes and order of decision 0052 (dev plans/contracts/hooks.md): 1 to 8 before Vibrant Mindz's step 1 and its blog, entitlements before step 5, and profile tabs before wave 2b, which may be after v1.0 freezes (the owner, 2026-11-21).

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| Content lifecycle | Done | [#97](https://github.com/mechframe/mechframe/pull/97) | [0052](decisions/0052-the-contract-hooks.md) | kernel.lifecycle: the Publishable mixin, publish, schedule and unpublish, visible, and the kernel's kernel.publish_due job |
| Taxonomy | Done | [#98](https://github.com/mechframe/mechframe/pull/98) | [0052](decisions/0052-the-contract-hooks.md) | kernel.taxonomy: vocabularies in module.json, the kernel's term tables (kernel_0013), tag, terms_for, tagged and untag_all, the public terms list and the admin's term routes |
| Search index | Done | [#99](https://github.com/mechframe/mechframe/pull/99) | [0052](decisions/0052-the-contract-hooks.md) | kernel.search: search.py's SEARCH and content_types[].search, the kernel table kernel_search_document (kernel_0014), the kernel hearing kernel.content.*, the kernel.search_reindex job, and GET /api/kernel/search |
| Seed data | Done | [#102](https://github.com/mechframe/mechframe/pull/102) | [0052](decisions/0052-the-contract-hooks.md) |  |
| Bot check | Done | [#103](https://github.com/mechframe/mechframe/pull/103) | [0052](decisions/0052-the-contract-hooks.md) |  |
| Consent categories | Done | [#107](https://github.com/mechframe/mechframe/pull/107) | [0052](decisions/0052-the-contract-hooks.md) |  |
| Export and erase | Done | [#109](https://github.com/mechframe/mechframe/pull/109) | [0052](decisions/0052-the-contract-hooks.md) |  |
| Dashboard cards | Done | [#110](https://github.com/mechframe/mechframe/pull/110) | [0052](decisions/0052-the-contract-hooks.md) |  |
| Entitlements | To do |  |  | Waits until just before Vibrant Mindz step 5, its downloads (the owner, 2026-11-21) |
| Profile tabs | To do |  |  | Waits until just before wave 2b, its profiles module (the owner, 2026-11-21) |

### Vibrant Mindz site, to launch · 3 of 6 done · gate not passed yet

The first real site, built from the modules; it doubles as the spec's validation (docs/plans/vibrant-mindz-backend/KICKOFF.md).

Gate: v1.0 is frozen when blog, chat (community) and payments pass the quality gate.

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| Step 0: scaffold, moderation permission, custom roles | Done | [#55](https://github.com/mechframe/mechframe/pull/55), [#56](https://github.com/mechframe/mechframe/pull/56) | [0029](decisions/0029-vibrant-mindz-order.md), [0031](decisions/0031-moderation-permission.md) |  |
| Step 1: media, pages, blog, embeds, contact, campaigns | Done | [#116](https://github.com/mechframe/mechframe/pull/116), [#118](https://github.com/mechframe/mechframe/pull/118), [#119](https://github.com/mechframe/mechframe/pull/119), [#121](https://github.com/mechframe/mechframe/pull/121), [#123](https://github.com/mechframe/mechframe/pull/123), [#125](https://github.com/mechframe/mechframe/pull/125), [#126](https://github.com/mechframe/mechframe/pull/126), [#127](https://github.com/mechframe/mechframe/pull/127), [#128](https://github.com/mechframe/mechframe/pull/128), [#129](https://github.com/mechframe/mechframe/pull/129), [#131](https://github.com/mechframe/mechframe/pull/131), [#132](https://github.com/mechframe/mechframe/pull/132), [#134](https://github.com/mechframe/mechframe/pull/134), [#135](https://github.com/mechframe/mechframe/pull/135), [#138](https://github.com/mechframe/mechframe/pull/138), [#139](https://github.com/mechframe/mechframe/pull/139), [#140](https://github.com/mechframe/mechframe/pull/140), [#141](https://github.com/mechframe/mechframe/pull/141), [#143](https://github.com/mechframe/mechframe/pull/143), [#144](https://github.com/mechframe/mechframe/pull/144), [#147](https://github.com/mechframe/mechframe/pull/147), [#148](https://github.com/mechframe/mechframe/pull/148), [#152](https://github.com/mechframe/mechframe/pull/152), [#155](https://github.com/mechframe/mechframe/pull/155), [#156](https://github.com/mechframe/mechframe/pull/156), [#158](https://github.com/mechframe/mechframe/pull/158), [#160](https://github.com/mechframe/mechframe/pull/160), [#161](https://github.com/mechframe/mechframe/pull/161), [#165](https://github.com/mechframe/mechframe/pull/165), [#168](https://github.com/mechframe/mechframe/pull/168) | [0040](decisions/0040-admin-shell-design.md), [0054](decisions/0054-route-body-limits.md), [0055](decisions/0055-markdown-editor.md), [0056](decisions/0056-loaded-links-and-the-footer-menu.md), [0057](decisions/0057-module-public-imports.md), [0058](decisions/0058-ai-writing-help.md), [0059](decisions/0059-notify-holders.md), [0060](decisions/0060-text-slots.md), [0061](decisions/0061-the-accounts-name.md), [0062](decisions/0062-queue-message-public.md), [0063](decisions/0063-the-signed-out-session-read.md), [0064](decisions/0064-the-ais-model-from-anthropics-list.md), [0065](decisions/0065-generated-covers.md), [0066](decisions/0066-the-footer-waits-for-the-page.md), [0067](decisions/0067-social-posting.md) | media landed (#116); the kernel's Markdown and its editor for pages and blog (#118); media and the admin kit drawn to the boards (#119), and again in round 2, the admin's labels in the boards' normal line height (#126), and in round 3, the kit's alert with its what at the boards' 16px and the alt box with no resize handle (#131), and in round 4, the admin shell's sidebar links, bell, View site and Menu where the boards draw them, with Content's pages in the boards' order (#140); pages, its menus loaded into nav.public and the new nav.footer (#121), and its page read in public.ts for a site's own page at /:address, an Updated line under each page's title, and the editor's crossed saves closed as blog's were (pages 0.1.1, #138); blog, with its categories, covers, related posts and board, and a module's web reaching another's public.ts as @/modules/<id>/public (#123, decision 0057), and its public surface for a site's own Blog and Post pages (#128), which a site's mypy now follows from its own code (#132); contact, its form, its Inbox and the kernel's notify_holders telling the Inbox's readers (#125, decision 0059), and its reads and send in public.ts for a site's own form (#129); embeds, its players behind a consent facade in every Prose, the Embed button in every editor and the YouTube playlist player, through the kit's two new text slots (#127, decision 0060); blog's AI writing help, the kernel's Write with AI in every editor with Settings → AI and Writing, and blog 0.1.2 handing it its fields (#135, decision 0058); blog 0.1.3, the post's summary in blog.post.published (v2) for campaigns' email, and the editor's crossed saves closed as pages' were (#143); campaigns, the newsletter: sign-ups confirmed by email from a site's own sections, contact's news box and blog's Email it to subscribers, sends at a pace with one-click unsubscribe through the kernel's email.queue_message, and bounces set aside from the mailbox over IMAP or Resend's webhook (#134, decision 0062); the account's name, set on a new Profile page or by staff in People, and found by People's search (#139, decision 0061); the session read answering a signed-out visitor 200 with no user, so a public page logs no 401 (#141, decision 0063); the AI's model picked in Settings → AI from Anthropic's newest Opus, Sonnet and Haiku, read each time the page opens and saved only through its own route (#144, decision 0064); generated covers, drawn by the AI from the post editor in one of four styles, cleaned to an allowlist by the kernel's new kernel.svg and kept in the media library as a PNG (blog 0.1.4, media 0.1.4, #147, decision 0065); the site frame's footer waiting for the page, so a first load never moves it (#148, decision 0066); social posting, a published post shared to the site's channels through Buffer from its editor's Share card, any module's public thing named by its content type and id through the kernel's server_copy.preview and the new content.share slot (social 0.1.0, blog 0.1.5, #152, decision 0067); Settings → AI's Model row drawn to its board, a form of its own under a rule, where the model comes from said first, the state's sentence in the hint's place and Try again on the label's line (#155); the admin's form parts drawn to the boards, VM Website's 22 lines: a field's hint under its control, the boards' select chevron, small buttons in settings forms and dialogs, ruled switch rows, a form card at 760px and the rest, in the admin only (contact 0.1.2, #156, decision 0040 amended); then the admin's lists and dashboard: 12px pills and column heads, a table's rowHeader column naming each row at 600, and a dashboard card's link and figure in the font's own line (#158, decision 0040 amended again); embeds 0.1.1, the playlist's Previous button showing the words of its name (#160); blog 0.1.6, /blog holding back on a first load until its posts and categories answer, so its footer stays put (#161); the kit's last differences from the boards, VM Website Dev 22's R and K items: card and page titles and a field's error in the font's own line, a card's text at 16px, a dialog 16px from the window's edges, every note radius 12 on the ground the boards give it, a long accordion description beside its title, Writing's styles at 390, the kit's new QuietLink, the Newsletter section's parts 18px apart and its Set aside buttons named by their words (campaigns 0.1.1), and blog's Draw a cover drawn to the AdminPost board: its switch rows, its failure line and Change it (blog 0.1.7) (#165, decision 0040 amended a third time); and VM Website's board check of #165, the last of step 1's four tests (Dev 25, against canvas 121): the boards hold, with its two asks done here, a dialog's title and the AI's problem line in the font's own line (#168, decision 0040 amended a fourth time) |
| Step 2: discography, audio player, featured | Done | [#145](https://github.com/mechframe/mechframe/pull/145), [#149](https://github.com/mechframe/mechframe/pull/149), [#151](https://github.com/mechframe/mechframe/pull/151), [#153](https://github.com/mechframe/mechframe/pull/153), [#157](https://github.com/mechframe/mechframe/pull/157), [#159](https://github.com/mechframe/mechframe/pull/159), [#160](https://github.com/mechframe/mechframe/pull/160), [#163](https://github.com/mechframe/mechframe/pull/163), [#165](https://github.com/mechframe/mechframe/pull/165), [#167](https://github.com/mechframe/mechframe/pull/167) | [0070](decisions/0070-audio-through-soundfile.md), [0071](decisions/0071-a-player-modules-hand-items-to.md), [0072](decisions/0072-item-references.md), [0073](decisions/0073-featured.md) | discography, the music library: releases, tracks, credits and streaming links with covers from media, a track playing from an upload made into an MP3 stream by a job (soundfile) or from a SoundCloud link, its four admin boards and three pages, and its public.py and public.ts for audio-player, featured and a site's own pages (#145, decision 0070); audio-player, the player modules hand items to: inline and docked bars, a queue and waveforms, one thing playing at a time with YouTube's player, SoundCloud behind its controls, and plays counted once per listener a day with nothing kept that identifies anyone (#149, decision 0071); discography 0.1.1, audio-player's first source: the Release page's Play album, each row's play and the docked Player, the Track page's bar, plays counted through discography's own route, and the Dashboard's Plays this week (#151); featured's contract approved and its first PR, hook 11, item references, so featured needs no module's code (#153, decision 0072); featured 0.1.0, the homepage's players: slots an admin makes on Players, filled with other modules' items or YouTube links in order with optional dates, live worked out at each read, the Dashboard's card and its two-day warning (#157, decision 0073); discography 0.1.2, its tracks and albums for featured's players through refs.py, the reads by id a homepage draws them from, and its admin drawn nearer its boards (VM Website's D1 to D4, K2, K3, K6 and K8) (#159); audio-player 0.1.1, the Player section on Settings › Site spanning its card, and its e2e axe covering the playlist again (#160); discography 0.1.3, its tables' rows named by their track or person, VM Website's P1 to P6 and #145's last review items (#163); audio-player 0.1.2, its lines at the theme's small size, which an invalid font-size had dropped, and the Player section's parts 18px apart (#165); discography 0.1.4, Tracks' panel's Open the release as the kit's QuietLink (VM Website's K11) and its e2e spec in three tests run in order, each within its 30 seconds at the end of a full run (#167); and step 2's four tests on 2026-11-28: the manifests against the schemas, CI and E2E on main (de279f9), `mechframe check` on a fresh site with media, embeds, audio-player, discography and featured, and VM Website's board check of Admin › Music with discography 0.1.4 (Dev 27: the boards hold). The owner's iPhone Safari check of the player moves to the site's deploy, once its audio uploads are set up (audio-player's contract, Changes after approval) |
| Step 3: roster, portfolio, reactions, comments | Next |  |  | The owner's order (2026-11-28): reactions then comments in the main lane, portfolio in the side lane, roster last; each contract first, for the owner |
| Step 4: community | To do |  |  |  |
| Step 5: payments, shop, downloads; the v1.0 gate and the site's launch | To do |  |  |  |

## After v1.0

The rest of the Vibrant Mindz site, the module waves, the framework tools and the TypeScript port study (decision 0018, SPEC 19).

### Vibrant Mindz site, after launch · 0 of 3 done

The beat store and the apparel designer.

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| Step 6: licensing, the beat store | To do |  |  |  |
| Step 7: print on demand, the apparel designer | To do |  |  |  |
| pages: VybeSite's builder, its sections, designs and layout | To do |  |  | the owner, 2026-11-21: ported after the Markdown pages (dev plans/contracts/pages.md) |

### Wave 1: foundations every site uses · 0 of 16 done

docs/plans/module-roadmap.md

To do: `forms`, `bot-shield`, `consent`, `analytics-adapters`, `privacy-center`, `legal`, `security-center`, `account-center`, `site-search`, `redirects`, `data-grid`, `import-export`, `command-palette`, `setup-wizard`, `image-pipeline`, `ai-gateway`.

### Wave 2a: sell more · 0 of 8 done

docs/plans/module-roadmap.md

To do: `memberships`, `credits`, `discounts`, `drops`, `tips`, `shipping`, `pricing-table`, `waitlist`.

### Wave 2b: fans and community · 0 of 11 done

docs/plans/module-roadmap.md

To do: `profiles`, `follows`, `feed`, `groups`, `polls`, `bookmarks`, `reviews`, `submissions`, `contests`, `live`, `rooms`.

### Wave 2c: music and media · 0 of 8 done

docs/plans/module-roadmap.md

To do: `video`, `radio`, `podcast`, `music-import`, `press-kit`, `short-links`, `social-feeds`, `transfer`.

### Wave 3a: agency handoff · 0 of 11 done

docs/plans/module-roadmap.md

To do: `migrate`, `invoices`, `client-portal`, `white-label`, `onboarding-tours`, `crm`, `reports`, `email-builder`, `announcements`, `editorial-calendar`, `zapier`.

### Wave 3b: service businesses · 0 of 7 done

docs/plans/module-roadmap.md

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| maps | To do |  |  |  |
| booking | To do |  |  |  |
| events | To do |  |  |  |
| directory | To do |  |  |  |
| recipes | To do |  |  |  |
| google-business | To do |  |  |  |
| sms | To do |  |  | Provider chosen at this wave |

### Wave 4: software products · 0 of 13 done

docs/plans/module-roadmap.md

To do: `license-keys`, `release-channels`, `beta-program`, `crash-reports`, `preset-exchange`, `docs`, `faq`, `changelog`, `wiki`, `helpdesk`, `public-api`, `orgs`, `enterprise-sso`.

### Wave 5: AI layer · 0 of 5 done

docs/plans/module-roadmap.md

To do: `semantic-search`, `concierge`, `agent-ready`, `prompts`, `ai-studio`.

### Framework tools · 0 of 4 done

When each lands is in docs/plans/module-roadmap.md.

| Step | Status | PRs | Decisions | Note |
| --- | --- | --- | --- | --- |
| provenance-scan and quality-gate | To do |  |  | During v1 extraction |
| visual-regression and catalog-site | To do |  |  | After wave 1 |
| theme-generator and fleet | To do |  |  | Wave 3a |
| platform-bridge | To do |  |  | After wave 5 |

### TypeScript port study · 0 of 3 done

After the first real site ships (SPEC 19).

Later: `Port one small module to a TypeScript backend, judged by the same contract tests`, `Measure the effort and what the contract tests caught`, `Record the call in a decision`.
