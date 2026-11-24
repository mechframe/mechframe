# Next session, main lane (M4h): blog 0.1.3, then generated covers, then social posting

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-23-next-session-m4h-blog-covers.md and follow it, starting with section 4."

## 1. The project

MechFrame (`CLAUDE.md`, `SPEC.md`), public at mechframe/mechframe; M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). The side lane's next session builds `discography` 0.1.0, contract first (`dev plans/2026-11-23-side-lane-m8-discography.md`). Tell it before and after every end-to-end run, and fold its result into your handoff.
- **Yours:** `modules/blog/`, `kernel/backend/kernel/ai.py`, `ai_routes.py` and `writing.py`, and blog's contract, `dev plans/contracts/blog.md`. **Not yours:** `modules/_discography/` (it becomes `modules/discography/`), `modules/pages/`, `modules/campaigns/`.
- **VM Website Dev 12** relays the owner's calls. Send it each PR number as it's pushed and as it lands. Never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key (Buffer's included). A contract waits for the owner's approval.

## 3. State (verify it)

- **main:** this handoff's docs PR, on top of #141 (the signed-out session read). Check `git log -1 origin/main` and `gh pr list`.
- **The ledger** shows the rows from #141's head (`docs/HANDOFF.md`, State).

## 4. The job, in order

0. Land this handoff's PR if it's open, on a green "CI result" with the bots clear.
1. **Blog 0.1.3**, one small PR:
   - **`summary` in `blog.post.published`**, so campaigns' email holds it (campaigns already reads it when it's there). Its payload changes, so check SPEC 11's rule on payload versions (`events.py`'s `v`) and run `python -m tools.event_schemas`.
   - **The three crossed-save gaps** in `modules/blog/web/pages/AdminPost.tsx` that pages 0.1.1 closed (#138): a retry and a conflict's choice carry the person's fields (`save(…, carried)`), and each sets `formNow.current = next` before saving again. Copy pages' four tests, and see each one fail first.
   - Add it to `dev plans/contracts/blog.md` §9.
2. **Generated covers** (`blog.md` §8, 3, answered): Claude draws an SVG cover from the post, which is cleaned, made a PNG on the server, and stored in media with alt text, through `await ai.client(db)`. Write its contract first, `dev plans/contracts/blog-covers.md`. It must cover:
   - the SVG cleaner's allowlist;
   - the PNG library, a new pinned dependency (add it to `docs/TESTING.md` and CLAUDE.md's Stack);
   - the fake in `harness/fake_anthropic.py`, so no suite calls Anthropic;
   - its rate limit, against `AI_RATE_LIMIT`;
   - where the button sits on the AdminPost board.
3. **Social posting:** ask `blog.md` §8, 7 first (its home, and Buffer's key), then write its contract.

Close out at a natural break past ~400K tokens, with two prompts, one for each lane.

## 5. Ask the owner, don't decide

Each contract's open questions; `blog.md` §8, 7; the handoff's open questions.

## 6. Environment and traps

- **The full suite** takes over an hour with both lanes at work. Merge `main` first. Run it in the background, its log in the scratchpad:
  `$env:PYTHONUTF8 = "1"; $env:MECHFRAME_REQUIRE_DB = "1"; .venv\Scripts\python.exe -m pytest --cov -q -rfE`
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test`. Under load, rerun a timed-out test alone before calling it a failure.
- **Commits:** `git commit -F <file>`, after `git diff --cached --stat` as a step of its own.
- **More:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- **Evidence:** `docs/HANDOFF.md`; the side lane's result, `dev plans/done/2026-11-23-side-lane-m7-pages-public.md` §5.
- **IDs:** yours are 0064 to 0069, `kernel_0017`, `kernel_0018` and `blog_0002`; the side lane's are 0070 and up, and `discography_0001`.
- **PR numbers:** before each push, read the next one from GitHub (the newest issue or PR, plus one) for the files that name it, and check it once the PR opens.

## 8. Candidates for `knowledge/`

1. ESLint runs out of memory when it walks `.claude/worktrees/`: ignore `.claude/**` in its flat config.
2. pytest-cov's `--cov=<module>` imports the module early and breaks SQLAlchemy (`'InternalTraversal' object is not callable`). Use plain `--cov`.
3. A public "who am I" read should answer 200 with `null`, not 401: the browser logs every 401 as a console error (decision 0063).
4. A layout test against a board should derive from the page's own brand box (`max(brand, 26) + padding`), not a fixed pixel height.
