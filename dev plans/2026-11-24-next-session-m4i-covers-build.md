# Next session, main lane (M4i): finish generated covers, then the footer's shift, then social posting

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-24-next-session-m4i-covers-build.md and follow it, starting with section 4."

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe; M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). The side lane is on `discography` in its own worktree (§3). Tell it before and after every end-to-end run, and fold its result into your handoff.
- **Yours:** `modules/blog/`, `modules/media/`, `kernel/backend/kernel/svg.py` and `ai*.py`, the site frame (`kernel/web/src/app/frames.tsx`, `routes.tsx`). **Not yours:** `modules/discography/`, `pages/`, `campaigns/`.
- **VM Website** (Dev 12 landings, Dev 14 the AI, Dev 15 covers and Lighthouse) relays the owner's calls: send each PR number as pushed and landed. Never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key, any download. A contract waits for the owner's approval.

## 3. State (verify it)

- **main:** this handoff's docs PR, on #144 (the AI's model, decision 0064). Check `git log -1 origin/main` and `gh pr list`.
- **Covers, `feat/blog-covers`:** local only, four commits on `7b01b9f`: `kernel.svg` (28 tests), resvg-py 0.5.0 pinned, Inter 4.1's three weights (the owner's OK for the download), the contract.
- **The side lane:** `discography` 0.1.0 is #145 (`feat/discography`, its worktree `.claude/worktrees/discography-0-1-0`); its result is §9 of its own prompt, `dev plans/2026-11-24-side-lane-m8b-discography-web.md`. Fold it into your handoff when it lands. It adds `security.public_origin` and the bucket's origin to `media-src` in `app.py` (decision 0070).
- **Remove `.claude/worktrees/ai-model`** once #144 is on `main`, its `node_modules` junction first (`cmd /c rmdir`).

## 4. The job, in order

0. Land this handoff's PR if it's open, on a green "CI result" with the bots clear.
1. **Finish generated covers** on `feat/blog-covers`. Merge `main` first. The contract is `dev plans/contracts/blog-covers.md`, approved. Its "Changes after approval" says what's built, what's left, and the board's words (canvas version 104), which win where they differ.
   Left: media 0.1.4's `store`; blog's `covers.py`, two routes and 0.1.4; the fake's `COVER`; `CoverDialog.tsx`; SPEC 6 and 15, decision 0065's record, the generated files.
2. **VM Website Dev 15's ask, with the owner's OK:** every page's footer shifts on first load (CLS 0.40), because `SiteFrame` paints before the lazy page fills `<main>`. Write a contract first. Dev 15's record, to read only, is `C:\DEV\VM Website\dev plans\2026-11-24-lighthouse-after-141.md`. **Ask the owner first** whether it goes before or after covers (§5).
3. **Social posting:** ask `blog.md` §8, 7 first (its home, and Buffer's key), then write its contract.

Close out at a natural break past ~400K tokens, with two prompts, one for each lane.

## 5. Ask the owner, don't decide

- Item 2's place against covers.
- `blog.md` §8, 7.
- `docs/HANDOFF.md`'s open questions.

## 6. Environment and traps

- **The full suite** takes about 85 minutes. Merge `main` first; run it in the background, its log in the scratchpad:
  `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest --cov -q -rfE`
  `test_worker.py`'s two process tests fail under its load here; rerun the file alone.
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test <spec>`.
- **Bash heredocs collapse `\\`,** and `\2026` once became a control character. Build backslashes with `chr(92)`.
- **Commits:** `git commit -F <file>`, after `git diff --cached --stat` as a step of its own. Check `git branch --show-current` first: another session once switched this checkout's branch.
- **More:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; the contracts' "Changes after approval".
- **IDs:** yours 0065 (covers), 0066 to 0069, `kernel_0017`, `kernel_0018`, `blog_0002`; the side lane's 0070 and up. Read each PR number from GitHub just before the push.

## 8. Candidates for `knowledge/`

1. Python's expat refuses nothing on its own. Refuse `<!` (not a comment or CDATA) in the whole input before `ET.fromstring`, or use defusedxml.
2. resvg draws `<text>` only with the fonts it's given. On a slim Docker image, bundle the font and pass `skip_system_fonts`.
3. React flushes a click's update before an awaited fetch answers, so a ref set "too late" in a click handler can't be caught in jsdom; only an update made from inside the async path can.
4. A strict event payload (`extra="forbid"`) gains a field only as a new version.
