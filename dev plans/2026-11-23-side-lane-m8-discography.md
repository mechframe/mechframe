# Side lane (M8): discography 0.1.0, contract first

Start a new session **in a worktree** of `C:\DEV\AI-DevKit` (Code tab → New session → this project, in a worktree). Then: "Read dev plans\2026-11-23-side-lane-m8-discography.md and follow it, starting with section 3."

This is for the side lane's next session. AI DevKit Development 40 WT landed pages 0.1.1 (#138) and is done.

## 1. The project and your lane

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane works in the main checkout on blog: 0.1.3, then generated covers, then social posting.

- **The worktree** uses the main checkout's `.venv` python, a junction to its `node_modules`, and a Playwright config on port 8781. Setup and traps: `dev plans/done/2026-11-22-side-lane-m5.md`, sections 1 and 4.
- **Before pushing,** run:
  - discography's suites, and any kernel tests you touch;
  - `npm run lint`, `npm run typecheck`, ruff, black, mypy and `python -m tools.validate_schemas`.

  CI's full suite gates the PR.
- **Tell the main lane** (`ListAgents`: the newest "AI DevKit Development" in the main checkout) before and after every end-to-end run.
- **Never edit `C:\DEV\VM Website`.** Send VM Website Dev 12 the PR number when it's pushed and when it lands.

## 2. What you own, and what you don't

- **Yours:**
  - `modules/_discography/`, renamed `modules/discography/` in the PR that adds its first migration and tests;
  - `dev plans/contracts/discography.md`;
  - decisions 0070 and up, if any are needed;
  - `discography_0001`.
- **Not yours:**
  - `modules/blog/`, `kernel/backend/kernel/ai.py`, `ai_routes.py` and `writing.py` (the main lane's);
  - `modules/_audio-player/` and `modules/_featured/` (step 2's next two);
  - `docs/HANDOFF.md`, `CLAUDE.md`'s state, and the ledger.

## 3. The job

**State, checked 2026-11-24, morning Eastern:** `main` is #141 (the signed-out session read) plus the main lane's handoff PR. Check with `git log -1 origin/main` and `gh pr list`.

1. **Write the contract first**, `dev plans/contracts/discography.md` from `_templates/feature-CONTRACT.md`, for the owner's approval. Its inputs:
   - the scaffold's `MODULE.md` and `module.json`;
   - `docs/plans/vibrant-mindz-backend/backend-plan.md` (decision 3: an upload or a SoundCloud link per track) and `players-admin.md`;
   - the "Admin: Album editor" board (the link is in `MODULE.md`).

   Ask the owner, with a recommendation for each:
   - how an upload becomes a stream file and peaks: ffmpeg in a kernel job, and on which host;
   - what a SoundCloud link stores;
   - the public pages' server copy (`MusicAlbum` and `MusicRecording` JSON-LD);
   - which hooks it fills (lifecycle, search, seed, export, dashboard).
2. **Build it to the approved contract,** following the `mechframe-module-extractor` and `alembic-multi-module-migrations` skills. Then run the `module-contract-lint` skill on it.
   - Covers come through `media`'s `public.py` and `public.ts`, as blog's do (decision 0057).
   - `public.py` gives `track_cards` and `album_cards`, which `audio-player` and `featured` will read.
3. **Make the generated files again:**
   - `python -m mechframe catalog` (with `cli` on `PYTHONPATH`);
   - `python -m tools.openapi`, then `npm run api:types`;
   - `python -m tools.event_schemas`;
   - `python -m tools.host_variables`;
   - `docs/progress.json` (Step 2), then `python -m tools.progress`.
4. **Land it:**
   - Merge `main`, then make the generated files again from main's copies, and run the suites green.
   - Just before the push, read GitHub's newest issue or PR number. Write the next one where the changelog and `progress.json` name this PR.
   - Push once and open the PR, then check it got that number.
   - Land by fast-forward on a green "CI result" with the bots clear (`CLAUDE.md`, Rules).

## 4. Evidence

- `dev plans/contracts/blog.md` and `media.md`: the latest module contracts, and the shape to copy.
- `modules/blog/`: covers through media, and `public.py` and `public.ts`.
- VM Website's boards and specs, to read only: `C:\DEV\VM Website\design\specs\players-admin.md`.

## 5. Result

(The side lane writes what shipped here, for the main lane's handoff.)
