# Handoff

Overwritten every session. This one: 2026-11-23, about 17:05, to 2026-11-24, about 08:00 Eastern (Claude Code, the owner's machine), session M4g of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane.

- **Landed:** #139 (the account's name), #140 (the admin shell's five differences) and #141 (the signed-out session read). #136, M4f's handoff, had landed before it began.
- **The side lane** landed pages 0.1.1 (#138).
- **`main`** is `c5debc7`, #141's head, landed at 07:41 Eastern (12:41 UTC) on 2026-11-24. This handoff is its own docs PR.

## State

- **#139, the account's name** (decision 0061; contract `dev plans/contracts/account-name.md`, approved as recommended), landed at `3f29622`:
  - a Name field on a new Profile page, and in People for staff;
  - `auth_user.display_name` is cleaned and capped at 120 characters, with no migration;
  - its audit action, and the session's `name`.
- **#140, the shell's five differences** (decision 0044, amended again), landed at `de439e8`:
  - four CSS fixes in `admin.css`;
  - `AdminSection.pages` sets a section's page order, with Content in the boards' order. A page listed twice is drawn once (CodeRabbit).
  - `admin.spec.ts` checks it at 1440 and 390 in both themes.
  - ESLint now ignores `.claude/**`: it ran out of memory walking the worktrees.
- **#141, the signed-out session read** (decision 0063; contract `dev plans/contracts/signed-out-session.md`, approved as recommended), landed at `c5debc7`:
  - **The read:** `GET /api/auth/session` is public. To anyone without a live session it answers 200 `{"user": null}`, and both answers carry `Cache-Control: no-store`. A dead cookie is left alone. The answer model is `SessionRead` (`user: UserView | None`).
  - **The web** reads `user: null` as signed out, and still reads a 401 that way, for a server not yet upgraded.
  - **The template's smoke** allows no console error now.
  - **The tests** read "this session ended" through `Api.who()`.
  - **The test runs:**
    - full Python suite: 3,508 passed, 97.87% coverage;
    - web: 955 passed, 91.1% of lines;
    - e2e: 115 of 115;
    - `tools.site_smoke`: green.
  - **VM Website:** after upgrading the kernel, its copy of the smoke can drop its 401 allowance. Dev 12 has been told.
- **#138, pages 0.1.1** (the side lane, AI DevKit Development 40 WT), landed at `e4f211b`. Its result is §5 of `dev plans/done/2026-11-23-side-lane-m7-pages-public.md`.
  - `@/modules/pages/public` gives `usePage`, `isMoved`, `day`, `LivePage` and `PageMoved`.
  - A live page shows an "Updated" line under its title.
  - Six crossed-save fixes in the editor.
  - VM Website Dev 12 and Dev 13 have the landing message.
- **The progress ledger:** `steps` points at `/_blob/6c0facbe467733921b7f2f3d765230d2`, the rows from `c5debc7`. v1.0 is 80% (49 of 61). Its `data/users/me` `check` isn't written yet: the page writes it only once it draws in a browser.

## Next

1. **Blog 0.1.3:**
   - the post's `summary` in `blog.post.published`, for campaigns;
   - the three crossed-save gaps in `modules/blog/web/pages/AdminPost.tsx` that pages 0.1.1 closed. A retry and a conflict's choice don't carry the person's fields, and neither sets `formNow` before saving again. Copy pages' `save(…, carried)` and its four tests.
2. **Generated covers** (`blog.md` §8, 3). Contract first.
3. **Social posting:** ask `blog.md` §8, 7 first.
- **The side lane, next:** `discography` 0.1.0, contract first (`dev plans/2026-11-23-side-lane-m8-discography.md`).

## Open questions for the owner

- `blog.md` §8, 7: social posting's home and its Buffer key.
- Earlier ones:
  - the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`;
  - hooks 6 to 8's changes after approval;
  - the Vibrant Mindz content;
  - `mechframe-iac-probe` on Railway.

## Notes

- **IDs:**
  - The main lane has 0064 to 0069, `kernel_0017`, `kernel_0018` and `blog_0002`.
  - The side lane has 0070 and up, and `discography_0001`.
  - PR numbers come from GitHub just before each push.
- **Traps met this session:**
  - ESLint runs out of memory when it walks `.claude/worktrees/`. `eslint.config.js` now ignores `.claude/**`.
  - `--cov=<module>` breaks SQLAlchemy's imports (`'InternalTraversal' object is not callable`). Use plain `--cov`.
  - A test that checks layout against a board should measure the page's own brand box: the harness's logo isn't the board's 26px.
  - A merge of `main` across lanes conflicts only in the progress files. Take main's, carry your own Step entry back in, and run `python -m tools.progress`.
- **Still true:**
  - Run the full suite with `$env:PYTHONUTF8 = "1"`.
  - Commit with `git commit -F <file>`, after `git diff --cached --stat` as a step of its own.
  - A module's OpenAPI spec carries its version: run `python -m tools.openapi` after a bump.
  - `npx.cmd` mangles arguments with `|` or spaces.
  - **Worktrees:** `campaigns-module-contract-065954` is removed. These are clean, each on a commit in `main`, and can go once no open session is working in them: `pages-0-1-1-public-5387b6`, `multi-agent-worktree-plan-adc83e`, `strange-cray-b32ad4` and `concurrent-session-standby-fbaf9e`. Remove a junctioned `node_modules` with `cmd /c rmdir` first; the last two still have one. The two `remote-control-standby-*` worktrees are clean on `b30dea3`; whether a session still uses them wasn't checked.
- **The ledger's older assets:** 28 of them, every asset but `6c0facbe467733921b7f2f3d765230d2`, are to be deleted once a page `check` passes. Nothing points at them; `Artifact` `list` with `scope: "assets"` names them.
- **`CLAUDE.md` is 179 lines,** past the ~150 the workspace asks for. Lean it when the owner says.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, and never edit `C:\DEV\VM Website`.
