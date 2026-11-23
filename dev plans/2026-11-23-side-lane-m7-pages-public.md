# Side lane (M7): pages 0.1.1, its page read in public.ts and the editor's crossed saves

Start a new session **in a worktree** of `C:\DEV\AI-DevKit` (Code tab → New session → this project, in a worktree). Then: "Read dev plans\2026-11-23-side-lane-m7-pages-public.md and follow it, starting with section 3."

This is for the side lane's next session. AI DevKit Development 37 WT landed campaigns (#134) and is done.

## 1. The project and your lane

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane works in the main checkout on three jobs:
- the account's name field (0061);
- the admin shell's five differences from the boards;
- the signed-out session read.

- **The worktree** uses the main checkout's `.venv` python, a junction to its `node_modules`, and Playwright's config on port 8781. The setup and traps are in `dev plans/done/2026-11-22-side-lane-m5.md`, sections 1 and 4.
- **Before pushing:** pages' suites, any kernel tests you touch, `npm run lint`, `npm run typecheck`, ruff, black, mypy and `python -m tools.validate_schemas`. CI's full suite gates the PR.
- **Tell the main lane** (`ListAgents`, the newest "AI DevKit Development" in the main checkout) before and after every end-to-end run.
- **VM Website Dev 12** asked for this, with the owner's OK. Send it the PR number when it's pushed and when it lands. Never edit `C:\DEV\VM Website`.

## 2. What you own, and what you don't

- **Yours:** `modules/pages/` (0.1.1), decision 0065 and up if one is needed, and `pages_0002` if one is.
- **Not yours:**
  - the main lane's: the kernel's account page and People, `kernel/web/src/admin/admin.css` and `AdminFrame.tsx`, the session route and `kernel/web/src/session/`;
  - `modules/blog/`, except to read it;
  - `docs/HANDOFF.md`, `CLAUDE.md`'s state and the ledger.

## 3. The job

**State, checked 2026-11-23 about 16:40 Eastern:** `main` is `3fcdf35` (campaigns, #134) plus the main lane's handoff PR. Check with `git log -1 origin/main` and `gh pr list`. The old worktree `campaigns-module-contract-065954` can go (its junction is already removed).

1. **Pages' page read in `public.ts`** (VM Website's ask). Write it as a section of `dev plans/contracts/pages.md` first ("0.1.1"), for the owner, the way blog 0.1.1 (#128) added its public surface.
   - The read is `modules/pages/web/public.ts`, reached as `@/modules/pages/public` (decision 0057), like blog's `usePost` in `modules/blog/web/public.ts`.
   - It exports the hook behind `PublicPage`, `GET /api/pages/page?address=/<address>`, which answers a live page, `{moved}` or 404, and it exports that answer's type.
   - The site will answer `/:address` with its own page. Pages' server copy stays as it is.
2. **The editor's two crossed-save gaps**, which blog fixed in #123 (`modules/blog/web/editing.ts`, `git log -- modules/blog/web/editing.ts`). Both are in `modules/pages/web/pages/AdminPage.tsx`:
   - a retry drops a field typed back to its saved value;
   - a conflict drops what was typed while the save waited.
   For each, write its test and see it fail before the fix.
3. **Pages 0.1.1:** `module.json`, `CHANGELOG.md`, and `MODULE.md`'s "Extension points".
4. **Make the generated files again:**
   - `python -m mechframe catalog` (with `cli` on `PYTHONPATH`);
   - `python -m tools.openapi`, then `npm run api:types`;
   - `docs/progress.json`, then `python -m tools.progress`.
5. **Land it:** merge `main` and make the generated files again from main's copies. Run the suites green. Just before the push, read GitHub's newest issue or PR number and write the next one where `progress.json` and the changelog name this PR. Then push once and open the PR, and check that it got that number. Land by fast-forward once "CI result" is green and the bots are clear (`CLAUDE.md`, Rules).

## 4. Evidence

- `dev plans/contracts/pages.md`, and `blog.md` §9.
- #128: the pattern for blog 0.1.1's `public.ts`.
- VM Website's side, to read only: `C:\DEV\VM Website\dev plans\contracts\written-page.md`.

## 5. Result

AI DevKit Development 40 WT, 2026-11-23, branch `feat/pages-0-1-1`, **#138**.

- **Built:** pages 0.1.1, written first as `dev plans/contracts/pages.md` §10.
  - `web/public.ts` (`@/modules/pages/public`) gives `usePage(address)`, with or without the slash, plus `isMoved`, `LivePage` and `PageMoved`. `PublicPage` reads through it (`web/reads.ts`). The server copy is unchanged.
  - The editor's crossed saves: the two gaps asked for, plus blog's third from #123 (a publish landing while a field is asked about now shows in the panel).
  - A fourth, from CodeRabbit on #138: a conflict-free retry carries the person's fields into the next conflict check.
  - No migration, decision or route. The IDs 0065+ and `pages_0002` weren't used.
- **Tests:**
  - `pages/tests/web/public.test.tsx`;
  - four in `pages.test.tsx`, each seen failing first;
  - pages' web (28) and Python suites, and the generated-file tests, green; lint, types, ruff, black, mypy and the schemas clean.
  - The end-to-end specs weren't run (the side lane's rule).
- **The owner's choices:** none were asked. VM Website's ask came with the owner's OK.
- **For the main lane's handoff:**
  - pages 0.1.1 landed (#138), with its page read in `public.ts`.
  - VM Website Dev 12 has the PR number, and gets a message when it lands.
  - **Blog has the CodeRabbit gap:** its `save` recursion in `modules/blog/web/pages/AdminPost.tsx` doesn't carry its fields into a retry. That's a small blog 0.1.3 fix (see pages' `save(…, carried)`).
- **Cleanup:** take the worktree's `node_modules` junction off (`cmd /c rmdir node_modules`) before `git worktree remove`.
