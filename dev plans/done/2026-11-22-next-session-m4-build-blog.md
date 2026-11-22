# Next session (M4, continued): build `blog`

Run from `C:\DEV\AI-DevKit`: "Read dev plans\2026-11-22-next-session-m4-build-blog.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). The repo is public: mechframe/mechframe. The kernel is done and hooks 1 to 8 are in; `media` (#116) and `pages` (#121) have landed. This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **Each module** gets a one-page contract first. `blog`'s is drafted with the owner's answers (`dev plans/contracts/blog.md`, §8).
  - Lift it with `skills/mechframe-module-extractor/SKILL.md` and lint it with `module-contract-lint`.
  - Run the brand check on anything lifted from VybeSite.
- **`pages` is now the pattern** for a module with content (`modules/pages/`):
  - lifecycle, search, the server copy, moves, menus;
  - the editor's merge on a crossed save (`web/editing.ts`);
  - the backend-only registries fixture (`tests/backend/conftest.py`).
- **Peer sessions** (VM Website Dev NN) relay the owner's calls. Confirm with the owner before acting, then reply with PR numbers as they land. Never edit `C:\DEV\VM Website`.
- **The owner's call:** any Railway project, apply or variable; CI's security gates; any third-party account (Buffer, an AI key).

## 3. State (2026-11-22, 08:30 Eastern; check it, don't trust it)

- **main** should be `2be4d49` (#121), or the handoff, #122, on top of it. Check with `git log -1 origin/main` and `gh pr list`.
  - **If #122 is open,** land it once its "CI result" is green.
- **The progress ledger**'s `steps` points at `/_blob/3e1145cfa09a3512ee565b8d2d55e9e5` (rows from `2be4d49`). Once its `data/users/me` `check` has passed (`dev plans/progress-ledger/README.md`), delete the three older assets `docs/HANDOFF.md` names.
- **The worktree** `.claude/worktrees/strange-cray-b32ad4` may still be there. Remove a junctioned `node_modules` with `cmd /c rmdir` before `git worktree remove`.

## 4. The job, in order

1. **`blog`'s first PR**, the blog itself (`blog.md`, every section but the AI, cover and social parts).
   - Who writes is settled: anyone with `blog.post.write` writes and publishes (§8, 5).
   - Related posts are in.
   - Reuse pages' patterns: slug moves, `MarkdownEditor`, `SearchFields`, lifecycle, the server copy.
2. **Blog's AI PR:** the kernel's `ai.client()`, Settings → Writing, and the editor's AI buttons (decision 0057). Ask §8's 6 first (the Anthropic key's home).
3. **Generated covers**, then **social posting** (ask §8's 7 first). Then M5.

Close out at a natural break past ~400K tokens.

## 5. Ask the owner, don't decide

- `blog.md` §8's 6 and 7.
- How a person's name gets set: the session answers `name`, but nothing sets `display_name`. An account field now, or with hook 10?
- The open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite** runs in the background, its log in the scratchpad, about 20 minutes:
  `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov`
- **End-to-end tests:** `npm run build`, then `npm run e2e` with `TEST_DATABASE_URL`. Run them from the main checkout.
- **One Vitest test with a space in its name:** `node node_modules/vitest/vitest.mjs run <path> -t "..."`. `npx.cmd` can't take a quoted argument with a space.
- **Escapes:** Write and Edit decode `\uXXXX`, and a Bash heredoc decodes `\\n`. Build such characters with `chr()`.
- **Every API answer is a typed object** (`tests/test_openapi.py`): a list is `{items}`.
- **A Playwright name is a substring:** say `exact: true`.
- **Bots:** CodeRabbit re-reviews each push, and its free limit runs out after a big PR. Codex reviews only a PR's first push. Auto-fix relays their comments.

## 7. Evidence and next IDs

- Evidence: `docs/HANDOFF.md`, decision 0056, and `pages.md` §9 (its changes after approval).
- Next free: decision 0057 (the kernel's AI), PR #123, migrations `blog_0001` and `kernel_0016`.

## 8. Candidates for `knowledge/`

1. TanStack Query: `staleTime` never refetches while an observer stays mounted. Judge with `query.isStaleByTime(ms)`.
2. A web test of a save that moves the route must hold the mock until the route has moved.
3. Playwright's role names match substrings; Testing Library's are exact.
4. Vite inlines any font under 4 KB as `data:`, which `font-src 'self'` refuses: test behind the built app's real CSP.
5. A Bash heredoc decodes `\\` before Python sees it, and tool parameters decode `\uXXXX`.
