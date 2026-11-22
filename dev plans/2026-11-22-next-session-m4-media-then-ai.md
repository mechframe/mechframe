# Next session, main lane (M4, continued): media's round 2, then blog's AI

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-22-next-session-m4-media-then-ai.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). The repo is public: mechframe/mechframe. The kernel and hooks 1 to 8 are in; `media` (#116), `pages` (#121) and `blog` (#123) have landed. This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **Two lanes** (`CLAUDE.md`, "Two lanes"): you're the main lane.
  - The side lane is **AI DevKit Development 33 WT**, in the worktree `.claude/worktrees/multi-agent-worktree-plan-adc83e`, on M5: contact, then embeds and campaigns.
  - It claims decision 0059, `contact_0001` and `kernel/backend/kernel/notifications.py`. Keep out of `modules/contact/`.
- **Peer sessions** relay the owner's calls: VM Website Dev NN, and Dev 33 WT. Confirm with the owner before acting, and reply with PR numbers as they land. Never edit `C:\DEV\VM Website`.
- **The owner's call:** any Railway project, apply or variable; CI's security gates; any third-party account or key (the Anthropic key included).

## 3. State (verify it)

- **main:** `c821437` (#123), with this handoff, #124, on top once it lands. Check with `git log -1 origin/main` and `gh pr list`.
- **The progress ledger:** `steps` at `/_blob/4cac99854ca40e368540bc714384d490`, the rows from `c821437`. Its `data/users/me` `check` isn't written yet, since the page hasn't drawn. Once one passes, delete the older assets `3e1145cfa09a3512ee565b8d2d55e9e5`, `aebed8eb43ca342bcba2bb7284ae57fe`, `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.
- **Worktrees:** `.claude/worktrees/multi-agent-worktree-plan-adc83e` (Dev 33 WT's, on `feat/contact-module`: leave it), and `.claude/worktrees/strange-cray-b32ad4` (old and detached: remove a junctioned `node_modules` with `cmd /c rmdir` before `git worktree remove`).

## 4. The job, in order

1. **Media's round 2:** its own PR, first, because VM Website is waiting on it.
   - What: the ten items in `dev plans/2026-11-22-media-round-2.md`, with the owner's choice for item 1 (match the boards' line height, keep 1.5 for prose) and where the 1.5 comes from.
   - Check every admin page after, in both themes: `kernel/tests/e2e/parity.spec.ts`, the kit page and axe.
   - Reply to VM Website Dev 09 with the PR (`SendMessage`): it checks parity again when it lands.
2. **Blog's AI PR** (decision 0058):
   - **Ask `blog.md` §8, 6 first: the Anthropic key's home.** Recommended: `ANTHROPIC_API_KEY` in the host's variables only, typed by the owner; nothing AI shows without it.
   - Write its contract first, `dev plans/contracts/kernel-ai.md`. It covers:
     - the kernel's `ai.client()` (SPEC 6);
     - Settings → Writing, lifted from VybeSite's `services/writing_constitution.py` and `writing_styles.py`;
     - the editor's AI buttons through `MarkdownEditor`'s `tools`: draft, titles, summary, search words, rewrite. The AI code comes from VybeSite's `routers/ai.py` and `services/anthropic_service.py`.
3. **Then generated covers** (§8, 3), **then social posting** (ask §8, 7 first).

Close out at a natural break past ~400K tokens. End with two prompts, one for each lane.

## 5. Ask the owner, don't decide

- `blog.md` §8, 6 and 7.
- **How a person's name gets set:** the session answers `name`, but nothing sets `display_name`, so a post's author shows no name on the site. An account field now, or with hook 10?
- The open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite** runs in the background, about 30 minutes alone, longer while the side lane runs. Keep its log in the scratchpad:
  `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov`
- **End-to-end:** `npm run build`, then `npm run e2e` with `TEST_DATABASE_URL`, from the main checkout.
- **Schema names are app-wide.** Give a module's answer models names of their own: two modules' `Full` rename each other in the committed specs.
- **Publishing doesn't bump `version`.** A save after a publish sends the version the publish answered.
- **Shared test data:** compare a list with what the API says, never with "the newest".
- **Line endings:** `git checkout` of a generated `schema.ts` writes CRLF and fails `api:check`. Make it again with `openapi-typescript`.
- **A heredoc with an odd quote fails.** Write a script with the Write tool, and run it with `python -I`.

## 7. Evidence and next IDs

- Evidence: `docs/HANDOFF.md`, `blog.md` §9 and decision 0057.
- Next free: decision 0058 (yours, the AI), 0059 (the side lane's); migration `kernel_0016` (yours, if the AI needs one). PR numbers come from GitHub just before each push.

## 8. Candidates for `knowledge/`

1. OpenAPI component names are app-wide: same-named Pydantic answers in two routers rename both.
2. One regex alias in Vite and Vitest, and one `paths` entry, for an import whose path differs between two layouts.
3. A theme's `font` shorthand sets line height: a later CSS layer, scoped, changes it without touching the tokens.
4. Playwright's role names match substrings; Testing Library's are exact, and it has no `exact` option.
5. A test on a shared database compares with the API, never with "the newest".
