# Next session, main lane (M4j): social posting, its contract first

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-24-next-session-m4j-social.md and follow it, starting with section 4."

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe; M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). The side lane is on audio-player (#149), then discography 0.1.1, in `.claude/worktrees/discography-0-1-0`. Tell it before and after every end-to-end run, and fold its result into your handoff.
- **Yours:** `modules/social/` (new), `modules/blog/`, `dev plans/contracts/social.md`. **Not yours:** `modules/audio-player/`, `modules/discography/`, `kernel/__init__.py`'s `client_address` line (#149's).
- **VM Website Dev 17** is the site's session: send it each PR number as pushed and landed. Never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key (the Buffer account included), any download. A contract waits for the owner's approval.
- **Resolve review threads by their comment's id**, never "every open thread": that closed CodeRabbit's newest ones unread last session.

## 3. State (verify it)

- **main:** this handoff's docs PR, on `1a1b4b8` (#148, the footer's shift, after #147, covers). Check `git log -1 origin/main` and `gh pr list`.
- **Open:** #149, audio-player 0.1.0 (the side lane's).
- **The ledger** shows the rows from `1a1b4b8`.

## 4. The job, in order

0. Land this handoff's PR if it's open, on a green "CI result" with the bots clear. GitHub refuses the fast-forward until "CI result" passes.
1. **Social posting's contract,** `dev plans/contracts/social.md` from `C:\DEV\_templates\feature-CONTRACT.md`, for the owner. The owner's answers (`blog.md` §8, 7):
   - a `social` module any module shares through, blog first, then releases and products;
   - its Buffer token: `BUFFER_ACCESS_TOKEN` on the host, or one saved in Settings, sealed, the saved one winning, with a Check: `kernel.ai`'s key is the pattern (`kernel/backend/kernel/ai.py`, decision 0058);
   - the source is VybeSite's `backend/app/services/buffer_service.py`, `routers/social.py`, `models/social.py` and `schemas/social.py` (read only; its brand check on what's lifted).
   Settle in the contract: what a module calls (a `public.py` share, or an event social hears), which channels, what's posted (title, link, summary, cover), when (blog's "Post it in Community" switch is community's; social needs its own), and failures shown where.
2. **Build it** once approved: the module, blog's hand-off, the fake Buffer for every suite (no suite calls Buffer), and the docs.
3. **Then step 1's close:** check step 1's six modules against the push plan's "done when", and mark it in `docs/progress.json`.

Close out at a natural break past ~400K tokens, with the main lane's prompt; the side lane writes its own.

## 5. Ask the owner, don't decide

The contract's open questions; `docs/HANDOFF.md`'s open questions (discography's settings permission, the flaky axe test, hooks 6 to 8, the Vibrant Mindz content, `mechframe-iac-probe`).

## 6. Environment and traps

- **The full suite** takes about 55 minutes. Merge `main` first; run it in the background, its log in the scratchpad:
  `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest --cov -q -rfE`
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec>`.
- **Scripts with backslashes** go in a file written with the Write tool, never a Bash heredoc. Check bytes with `od -c`.
- **Never `prettier --write` an existing file.**
- **Commits:** `git commit -F <file>`, after `git branch --show-current`.
- **More:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; the contracts' "Changes after approval" (`blog-covers.md`, `footer-shift.md`).
- **IDs:** yours 0067 to 0069, `kernel_0017`, `kernel_0018`, `blog_0002`, `social_0001`; the side lane's 0072 and up. Read each PR number from GitHub just before the push.

## 8. Candidates for `knowledge/`

1. GitHub threads: resolve by the comment's id; a loop over "every unresolved thread" closes reviews nobody read.
2. Layout-shift tests: count only shifts whose sources are the element under test, or a page's own content growing reads as the frame's fault.
3. A layered stylesheet's rule loses to an unlayered one at any specificity: a framework's "must win" rule needs `!important`.
4. A thread can't be stopped in Python: a time limit on C code (resvg) needs a process of its own.
5. A browser draws an SVG `<img>`'s text in its own fonts: preview with the server's own render when the PNG is what's kept.
