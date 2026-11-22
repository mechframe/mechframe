# Next session (M4, continued): build `pages`, then `blog`

Run from `C:\DEV\AI-DevKit`: "Read dev plans\2026-11-22-next-session-m4-build-pages.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`), public repo mechframe/mechframe. The kernel is done, hooks 1 to 8 are in, `media` landed (#116). This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **Each module** gets a one-page contract first; `pages`' is approved (`dev plans/contracts/pages.md`), `blog`'s is drafted with the owner's answers (`dev plans/contracts/blog.md`, §8 says what's still to ask). Lift with `skills/mechframe-module-extractor/SKILL.md`, lint with `module-contract-lint`, brand-check.
- **`media` is the pattern** for a module (`modules/media/`): its tests' `conftest.py` files, web tests, `tests/e2e`, grants in its first migration, seed rows in `tests/test_migrations.py`'s `_SEED`.
- **Peer sessions** (VM Website Dev NN) relay the owner's calls: confirm with the owner before acting, then reply with PR numbers as they land. Never edit `C:\DEV\VM Website`.
- **The owner's call:** any Railway project, apply or variable; CI's security gates; any third-party account (Buffer, an AI key).

## 3. State (2026-11-22, early morning Eastern; check it, don't trust it)

- **main** should be `f3fc712` (#119) or the handoff, #120, on it. `git log -1 origin/main`, `gh pr list`. **If #120 is open,** land it on a green "CI result".
- **The progress ledger**'s `steps` points at `/_blob/aebed8eb43ca342bcba2bb7284ae57fe` (rows from `f3fc712`). No `data/users/me` `check` exists yet: once one has passed (`dev plans/progress-ledger/README.md`), delete the older assets `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.
- **Worktrees:** `.claude/worktrees/media-fixes` and `strange-cray-b32ad4` may be left; remove a junctioned `node_modules` with `cmd /c rmdir` before `git worktree remove`.

## 4. The job, in order

1. **`pages`, one PR** (contract §2 to §7): `modules/pages/`, decision 0056 (link slots a module loads, and `nav.footer`) in the same PR, `kernel/web/src/slots/`. Header and footer menus (the owner chose both). Uses the kernel's `MarkdownEditor`, `Prose`, `SearchFields` (#118) and `SearchBox` (#119).
2. **`blog`'s first PR** (the blog itself; contract `blog.md`): ask §8's 7 first (who writes). Related posts are in.
3. Then blog's AI PR (the kernel's `ai.client()`, Settings → Writing, the editor's AI buttons; ask §8's 5 first), covers, social posting (ask 6 first). Then M5.

Close out at a natural break past ~400K tokens.

## 5. Ask the owner, don't decide

`blog.md` §8, 5 to 7; how a person's name gets set (the session answers `name` since #119, the card shows it, nothing sets `display_name`: an account field now, or with hook 10's name and handle); the open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite**, in the background with its log in the scratchpad: `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov` (25 minutes when nothing else runs; much longer beside other runs).
- **A worktree** under `.claude/worktrees/` lets work go on beside it (main's `.venv` python, a junction to `node_modules`), but Playwright finds no tests there: run end-to-end specs from the main checkout.
- **Escapes:** a Python heredoc in Bash turns `\\n` into a real line break; write such scripts to the scratchpad with Write. `npx.cmd` can't take a quoted argument with a space.
- **CodeRabbit** re-reviews each push; Codex only a PR's first.

## 7. Evidence and next IDs

`docs/HANDOFF.md`; decisions 0055 (Markdown), 0042 and 0044 amended (#119). Next free: decision 0056 (pages' link slots), 0057 (the kernel's AI), PR #121, migrations `pages_0001`, `blog_0001`, `kernel_0016`.

## 8. Candidates for `knowledge/`

1. A Bash heredoc decodes `\\` before Python sees it; tool parameters decode `\uXXXX`.
2. Playwright finds no tests in a worktree under a dot-folder.
3. `document.execCommand("insertText")` is still the only way a script's change keeps the browser's undo; jsdom has none, so test that path in Playwright.
