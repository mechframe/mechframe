# Handoff

Overwritten every session. This one: 2026-11-24, about 07:45 to 12:00 Eastern (Claude Code, the owner's machine, the owner on Remote Control at times), session M4h of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane. Landed: #142 (M4g's handoff), #143 (blog 0.1.3) and #144 (the AI's model). Started: generated covers, on a local branch. This handoff is its own docs PR.

## State

- **#143, blog 0.1.3,** landed at `7b01b9f`:
  - `blog.post.published` is version 2 and carries the post's `summary`, so campaigns' email holds it. A payload refuses fields it doesn't declare, so the field had to be a new version (SPEC 11 and 13).
  - The editor's three crossed-save gaps are closed as pages' were (#138), each with a test seen failing first.
- **#144, the AI's model from Anthropic's list** (decision 0064; `dev plans/contracts/ai-model.md`, approved as recommended), landed at `083342a`, with Codex's one finding and CodeRabbit's four fixed, each with a test seen failing first:
  - Settings → AI's Model row is a dropdown of the newest Opus, Sonnet and Haiku. It's read from Anthropic each time the page opens, with a budget of its own (60 an hour a person).
  - A saved model wins over `ANTHROPIC_MODEL`, and it's saved only through `PUT /admin/ai/model`, which checks it against the list. That's settings' new `own_route` (SPEC 7).
  - The six states are VM Website's boards (AdminAI, canvas versions 101 and 102).
- **Generated covers** (decision 0065; `dev plans/contracts/blog-covers.md`, approved as recommended, its board at canvas version 104) are on **`feat/blog-covers`, local and never pushed:**
  - `kernel.svg`, the cleaner and the PNG step, with 28 tests and two mutants seen caught;
  - resvg-py 0.5.0, pinned with hashes;
  - Inter 4.1's Regular, SemiBold and Bold, downloaded with the owner's OK, its OFL licence beside them, in NOTICE;
  - media 0.1.4's `public.store`, with its test;
  - the contract, with what's left and the board's words, in its "Changes after approval".
  - That's four commits on `7b01b9f`, ending at `dacb1ca`.
- **The tests:**
  - #144's branch, merged with #143: full Python suite 3,526 passed, 97.86%; web 973 passed, 93.45% of lines; `ai.spec.ts` 4 passed;
  - #143: 3,507 passed, and `blog.spec.ts` in both themes.
- **The ledger:** `steps` points at `/_blob/3de1f2c6100eb28a99d08e6fb1e413f9`, the rows from `083342a`. v1.0 is still 80% (49 of 61). Its `data/users/me` `check` isn't written yet: the page hasn't drawn. Once one passes, delete the older assets, the M4g handoff's list plus `6c0facbe467733921b7f2f3d765230d2`.
- **The side lane** (AI DevKit Development 44 WT) opened **`discography` 0.1.0 as #145** (`feat/discography`, from `.claude/worktrees/discography-0-1-0`). It will merge `main` again after #144, before landing.
  - Its result is §9 of its own prompt, `dev plans/2026-11-24-side-lane-m8b-discography-web.md`, in that PR.
  - Besides the module, #145 touches SPEC 6 and 15, `docs/progress.json` (Step 2), `catalog.json`, `docs/HOST-VARIABLES.md` and `package.json`'s `api:*` scripts.
  - Its one kernel change: `security.public_origin`, and `STORAGE_PUBLIC_URL`'s origin in `media-src` (decision 0070). It merges beside #144's line in `app.py`.
  - It takes decisions 0071 and up.
- **VM Website:**
  - Dev 12 has had every landing.
  - Dev 14 drew the AI boards.
  - Dev 15 drew Draw a cover (canvas version 104) and sent the footer's layout shift (Next, 2).

## Next

1. **Finish generated covers** on `feat/blog-covers`, after merging `main`: media 0.1.4's `store`, blog's task, routes and dialog, the fake's `COVER`, and the docs.
2. **The site frame's footer shifts** on every page's first load (CLS 0.40; VM Website Dev 15, with the owner's OK). `SiteFrame` paints the footer before the lazy page fills `<main>`. Contract first. Its record, to read only, is `C:\DEV\VM Website\dev plans\2026-11-24-lighthouse-after-141.md`.
3. **Social posting:** ask `blog.md` §8, 7 first.

## Open questions for the owner

- Whether the footer's shift (Next, 2) goes before covers or after them.
- `blog.md` §8, 7: social posting's home, and its Buffer key.
- Earlier ones:
  - the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`;
  - hooks 6 to 8's changes after approval;
  - the Vibrant Mindz content;
  - `mechframe-iac-probe` on Railway.

## Notes

- **IDs:**
  - the main lane used 0064 and 0065, and has 0066 to 0069, `kernel_0017`, `kernel_0018` and `blog_0002`;
  - the side lane has 0070 (written) and up.
- **Still stale:** `modules/campaigns/MODULE.md` (lines 42 and 73) and `dev plans/contracts/campaigns.md` still say blog's payload is v1, with no summary. Both are campaigns' files, so the fix waits for campaigns' next version.
- **Flaky on this PC:** `test_worker.py`'s `test_a_killed_worker_s_job_is_finished_by_the_next` and `test_the_web_process_runs_none_when_not_asked` failed under the full suite's load twice, and passed alone both times. CI is green on them.
- **Traps met:**
  - A Bash heredoc collapses `\\` to `\`, and `\2026` once became a control character. Build backslashes with `chr(92)`.
  - Another session switched this checkout's branch 37 seconds after I made one (the reflog shows it). Check `git branch --show-current` before committing.
  - CodeRabbit's free reviews run out after a few pushes an hour. It answers "Review limit reached".
  - ruff's S314 flags `xml.etree`. `kernel.svg` refuses a DOCTYPE or an entity in the whole input first, with a `noqa` that says why.
- **Still true:**
  - Run the full suite with `$env:PYTHONUTF8 = "1"`. It takes about 85 minutes here.
  - Commit with `git commit -F <file>`.
  - A module's OpenAPI spec carries its version.
  - The root lint and black sweep `.claude/worktrees/`, and `npx.cmd` mangles arguments.
- **`CLAUDE.md` is about 170 lines.** Lean it when the owner says.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`. Run its brand check on lifted code: covers lift VybeSite's styles and wordmark.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, and never edit `C:\DEV\VM Website`.
