# Next session, main lane (M4g): the account's name, then VM Website's shell and session asks

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-23-next-session-m4g-name-shell-session.md and follow it, starting with section 4."

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe; M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). 37 WT is landing campaigns (#134); the side lane's next session takes pages 0.1.1 (`dev plans/2026-11-23-side-lane-m7-pages-public.md`). Tell it before and after every end-to-end run; fold its result into your handoff.
- **Yours:** `kernel/web/src/account/`, People, the shell (`admin.css`, `AdminFrame.tsx`), the session route and `kernel/web/src/session/`, the template's `web/e2e/smoke.spec.ts`. **Not yours:** `modules/pages/`, `modules/campaigns/`.
- **VM Website Dev 12** relays the owner's calls: send it each PR number as pushed and landed; never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key. A contract waits for the owner's approval.

## 3. State (verify it)

- **main:** this handoff's docs PR on `f18f764` (#135). #134 (campaigns) may have landed since. Check `git log -1 origin/main` and `gh pr list`.
- **The ledger** shows the rows from `f18f764` (`docs/HANDOFF.md`, State).

## 4. The job, in order

0. Land this handoff's PR if it's open, on a green "CI result" with the bots clear.
1. **The account's name field** (decision 0061; the owner: now). Write its contract first, `dev plans/contracts/account-name.md` from `_templates/feature-CONTRACT.md`, for the owner. It covers:
   - a Name on the account page, and in People for admins;
   - `auth_user.display_name` (120 characters, `auth/models.py:88`) is already read in four places, so it may need no migration;
   - who may change whose name, its trimming and length, its audit action, and where it shows: the session's `name` (#119) and blog's author.
2. **The admin shell's five differences** (`docs/HANDOFF.md` lists them, with the CSS that drew the boards).
   - Four are CSS in `admin.css`.
   - The order of a section's pages needs a way for a site or a `nav.admin` entry to set it: decision 0063 if the manifest changes (tell the owner which SPEC sections).
   - Check it in `admin.spec.ts` at 1440 and 390, in both themes.
3. **The signed-out session read** (the owner's ask, through VM Website): `GET /api/auth/session` answers 200 with no user, so a public page logs no 401. Contract first (decision 0064): `docs/contracts/auth-api.md`'s row and its contract tests (spec 14.13), `session.tsx`, the template smoke's allowance for that 401.
4. Then generated covers (`blog.md` §8, 3, through `ai.client(db)`), then social posting (ask §8, 7 first).

Close out at a natural break past ~400K tokens, with two prompts, one for each lane.

## 5. Ask the owner, don't decide

Each contract's open questions; the section order's shape if it changes the manifest; `blog.md` §8, 7; `docs/HANDOFF.md`'s open questions.

## 6. Environment and traps

- **The full suite** (over an hour with both lanes at work): merge `main` first; run it in the background, its log in the scratchpad:
  `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest --cov -q -rfE`
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test`. Under load, rerun a timed-out test alone before calling it a failure.
- **Commits:** `git commit -F <file>`, after `git diff --cached --stat` as a step of its own.
- **More:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; `dev plans/contracts/kernel-ai.md`, "Changes after approval"; `dev plans/done/`.
- **IDs:** yours are 0061, 0063, 0064, `kernel_0017`, `kernel_0018`; the side lane's 0062, 0065 and up, `pages_0002`. PR numbers come from GitHub just before each push.

## 8. Candidates for `knowledge/`

1. A controlled textarea loses undo when `execCommand` types into it in an effect or under a modal `<dialog>`: type after the dialog closes.
2. Pydantic v2 words a validator's ValueError "Value error, …": show `ctx["error"]`.
3. An Alembic expression index compares as Postgres reads it back (`lower(name::text)`).
4. StrictMode runs setup, cleanup, setup: set an effect's refs in its setup.
5. On a busy PC, rerun a timed-out end-to-end test alone before calling it a failure.
