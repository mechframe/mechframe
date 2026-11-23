# Next session, main lane (M4, continued): blog's AI, then the account's name

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-22-next-session-m4f-blog-ai.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). The repo is public: mechframe/mechframe. This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). The side lane, AI DevKit Development 37 WT, builds campaigns (decision 0062, `campaigns_0001`) on `feat/campaigns-module` in `.claude/worktrees/campaigns-module-contract-065954`. Tell it before and after every end-to-end run, and fold its result into your handoff.
- **VM Website Dev 11** relays the owner's calls for the site: confirm a new ask with the owner, send it PR numbers as pushed and landed, never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key (the Anthropic key included). A contract waits for the owner's approval before its code.

## 3. State (verify it)

- **main:** this handoff's PR (#133), on `86f18c1`; before it #131 (media's round 3) and #132 (a site's mypy) landed, and VM Website Dev 11 knows. Check with `git log -1 origin/main` and `gh pr list`.
- **The ledger** shows the rows from `86f18c1` (`docs/HANDOFF.md`, State).
- `modules/contact/web/schema.ts` shows as modified from line endings only: leave it, don't stage it.

## 4. The job, in order

1. **Blog's AI PR** (decision 0058). Write its contract first, `dev plans/contracts/kernel-ai.md` from `_templates/feature-CONTRACT.md`, for the owner to approve:
   - `ai.client()` (SPEC 6);
   - the key in `ANTHROPIC_API_KEY` or saved encrypted in Settings → AI (the owner: "Host variable or Settings"), saying which wins when both are set;
   - Settings → Writing, from VybeSite's `writing_constitution.py` and `writing_styles.py`;
   - the editor's buttons (draft, titles, summary, search words, rewrite) as a kernel entry in `KERNEL_EDITOR_TOOLS` (`kernel/web/src/app/editorTools.ts`), from VybeSite's `routers/ai.py` and `services/anthropic_service.py`;
   - blog's next version, which also says in `MODULE.md` ("Extension points") that `blog.public`'s dates are ISO text (`kernel.answers.When`).
   Read `dev plans/contracts/blog.md` §8 and §9 first. Lift nothing from VybeSite's `dev plans\` or `snapshots\`, and run its brand check.
2. **The account's name field** (the owner: now): a Name on the account page, and in People for admins (decision 0061, `kernel_0016` and `kernel_0017` if it needs them).
3. Then pages' crossed-save gaps (`docs/HANDOFF.md`), generated covers (`blog.md` §8, 3), social posting (ask §8, 7 first).

Close out at a natural break past ~400K tokens, with two prompts, one for each lane.

## 5. Ask the owner, don't decide

The contract's open questions; `blog.md` §8, 7; the open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite** (1 h 17 min with both lanes at work): merge `main` first, then run it in the background with `$env:PYTHONUTF8 = "1"`, its log in the scratchpad.
  `TEST_DATABASE_URL` is the owner's user variable (the `devkit` role on port 55432); `MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov -q -rfE`
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test` with `TEST_DATABASE_URL`. Call node directly: `npx.cmd` mangles `|` and spaces.
- **Commits:** `git commit -F <file>`, and `git diff --cached --stat` as its own step first.
- **More:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- Evidence: `docs/HANDOFF.md`; the "Result" sections in `dev plans/done/`; `blog.md` §9.
- Yours: decisions 0058 (the AI) and 0061 (the name field), migrations `kernel_0016` and `kernel_0017`. The side lane's: 0062 and up. PR numbers come from GitHub just before each push.

## 8. Candidates for `knowledge/`

1. A text-mode `subprocess.run` under an inherited `PYTHONIOENCODING=utf-8` reads cp1252 on Windows: pass `encoding="utf-8"`.
2. PowerShell 5.1 splits a here-string at its quotes for a native program: use a message file.
3. A copied package's folder belongs on `mypy_path` as it is on `sys.path`: follow it, don't silence it.
4. Check the staged set as its own step before a commit, so a stray change can't ride along.
5. A board's text measures differently while its web font is still loading: wait for `document.fonts.ready`.
