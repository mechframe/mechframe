# Handoff

Overwritten every session. This one: 2026-11-22, about 16:40 Eastern, to 2026-11-23, about 08:20 (Claude Code, the owner's machine, the owner on Remote Control), session M4e of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane. Landed: #131 (media's round 3) and #132 (a site's mypy finding its modules). `main` is `86f18c1`, #132's head; this handoff is its own docs PR.

## State

- **#131, media's round 3**, landed at `3f61134`. The board's alert measured 3px taller because the kit drew its "what" at the theme's type.body (15px in Vibrant Mindz). `.mf-attention-what` is now 1rem in every theme (decision 0042, amended), and media 0.1.3's alt box has no resize handle. `kit.spec.ts` checks the alert in both themes and `media.spec.ts` both items. The result: `dev plans/done/2026-11-22-media-round-3.md`.
  - Geist's normal line height is 1.3 in fontsource 5.3.0 and Google's alike. If VM Website still measures about 72 against 75, Geist hadn't loaded on the site when it measured.
- **#132, a site's mypy**, landed at `86f18c1`. The template's `mypy_path` is `backend,backend/modules`, and mypy follows a module as it follows the kernel. All five modules' 45 files pass a site's strict mypy. `tests/test_site_template.py` now runs a site's mypy on every PR, with media, blog and a page importing `blog.public` (about 2 minutes). The result: `dev plans/done/2026-11-22-site-mypy-modules.md`.
  - For VM Website, `mechframe upgrade kernel` stops on its edited `pyproject.toml` as a conflict: take the template's line, drop its `follow_imports = "silent"` override, then `--merged pyproject.toml`.
  - Blog's `MODULE.md` note, that `blog.public`'s dates are ISO text, goes in with blog's next version (the AI PR).
- **VM Website Dev 11** is the site's session now (the owner's word, through Dev 10). It holds the Contact page's wiring to contact 0.1.1 and takes #131 and #132 next; Dev 10 forwarded it both PR numbers and both landings.
- **The side lane:** AI DevKit Development 35 WT landed embeds (#127, decision 0060). Campaigns' contract is approved (decision 0062, `campaigns_0001`). AI DevKit Development 37 WT started building it on 2026-11-23 at about 08:05 Eastern, from `dev plans/2026-11-22-side-lane-m6-campaigns.md`: `feat/campaigns-module` is at `b5b8a0d` (main merged in) in the worktree `.claude/worktrees/campaigns-module-contract-065954`. Main keeps the old M5 prompt until campaigns lands.
- **The progress ledger:** `steps` points at `/_blob/f973d1010fe6ff42eb7464c80ed06be9`, the rows from `86f18c1`. Step 1 lists #116, #118, #119, #121, #123, #125 to #129, #131 and #132; v1.0 is 78% (48 of 61). Its `data/users/me` `check` isn't written yet, since the page hasn't drawn. Once one passes, delete the older assets `d04f4fb64eb82a5cf3c6b5cc8ab5d1b4`, `7cba5e8f7e5bb99d774882ce79d9aaad`, `4cac99854ca40e368540bc714384d490`, `3e1145cfa09a3512ee565b8d2d55e9e5`, `aebed8eb43ca342bcba2bb7284ae57fe`, `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.

## Next

1. **Blog's AI PR** (decision 0058): its contract `dev plans/contracts/kernel-ai.md` first, for the owner. It covers `ai.client()` (SPEC 6), the key in `ANTHROPIC_API_KEY` or saved encrypted in Settings → AI (saying which wins), and Settings → Writing. The buttons go through `editor.tools` as a kernel entry in `KERNEL_EDITOR_TOOLS`. Blog's next version carries the ISO-dates note.
2. **The account's name field** (the owner: now; decision 0061, `kernel_0016` and `kernel_0017` if it needs them).
3. Pages' two crossed-save gaps, then generated covers, then social posting (ask `blog.md` §8, 7 first).

## Open questions for the owner

- `blog.md` §8, 7: social posting's home and its Buffer key.
- Earlier ones: the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`; hooks 6 to 8's changes after approval; the Vibrant Mindz content; `mechframe-iac-probe` on Railway.

## Notes

- **IDs:** main lane 0058 and 0061, `kernel_0016` and `kernel_0017`; side lane 0062 and up (`campaigns_0001`). PR numbers come from GitHub just before each push.
- **The full Python suite took 1 h 17 min** here with both lanes at work (3217 passed). Run it with `$env:PYTHONUTF8 = "1"`. This shell sets `PYTHONIOENCODING=utf-8`, so a test reading a child's output as text with no encoding reads it as cp1252. #132 fixed the one that failed. One Postgres connect timed out under load (`test_migrate.py`) and passed alone.
- **Commits from PowerShell:** a here-string passed to `git commit -F -` is split at its quotes. Write the message to a file and use `git commit -F <file>`. Check `git diff --cached --stat` as a step of its own before each commit: once, a rename staged for the next PR rode along (`b55e952`, undone by `3f61134`).
- **CodeRabbit** skipped #131's later docs-only commits; Codex was clear on its first.
- **Still true:** a module's OpenAPI spec carries its version (run `python -m tools.openapi` after a bump). The root lint and black sweep `.claude/worktrees/`. `npx.cmd` mangles arguments with `|` or spaces. The worktrees `multi-agent-worktree-plan-adc83e`, `strange-cray-b32ad4` and `concurrent-session-standby-fbaf9e` (clean, detached at `a8967b2`) can go, a junctioned `node_modules` removed with `cmd /c rmdir` first.
- **`CLAUDE.md` is about 170 lines,** past the ~150 the workspace asks for: lean it when the owner says.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
