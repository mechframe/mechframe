# Side lane (M8b): discography 0.1.0, the contract tests, the web and the PR

Start a session in the existing worktree `C:\DEV\AI-DevKit\.claude\worktrees\discography-0-1-0`, on branch `feat/discography`. Use `EnterWorktree` with that path; don't start a new worktree. Then: "Read dev plans\2026-11-24-side-lane-m8b-discography-web.md and follow it, starting with section 3."

## 1. The project and your lane

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane works in the main checkout on blog: covers, then social posting.

- **The contract** is `dev plans/contracts/discography.md`, approved 2026-11-24. Read it all, including "Changes after approval": soundfile, not PyAV.
- **The worktree:**
  - it already has the junction to the main checkout's `node_modules`;
  - its Python is `C:\DEV\AI-DevKit\.venv\Scripts\python.exe`, which now has soundfile 0.14.0 and numpy 2.5.5;
  - Playwright config on port 8781 (`dev plans/done/2026-11-22-side-lane-m5.md` §4, and the memory note `worktree-playwright-config`).
- **Tell the main lane** before and after every end-to-end run (`ListAgents`: the newest "AI DevKit Development" in the main checkout; on 2026-11-24 that was `AI DevKit Development 41`, which runs blog's and the AI's end-to-end specs).
- **Never edit `C:\DEV\VM Website`.** Send VM Website Dev 12 the PR number when it's pushed and when it lands.

## 2. What you own, and what you don't

- **Yours:**
  - `modules/discography/`;
  - `dev plans/contracts/discography.md`;
  - decision 0070 (written) and 0071 and up;
  - `discography_0001` (written);
  - the kernel's `security.public_origin` and its three lines in `app.py` (the main lane has been told).
- **Not yours:**
  - `modules/blog/`, `kernel/backend/kernel/ai.py`, `ai_routes.py` and `writing.py`;
  - `modules/_audio-player/` and `modules/_featured/`;
  - `docs/HANDOFF.md`, `CLAUDE.md`'s state, and the ledger.

## 3. State (verified 2026-11-24, about 9:30 Eastern)

- **The branch:** `feat/discography`, from `c5debc7` (main, #141), two commits ahead, **local only, not pushed**:
  - `878bbcc`: the backend;
  - the next commit: decision 0070 and the backend tests.
- **The backend is done to the contract:** models, `audio` (soundfile), service, router, job, events, `public.py`, server copy, search, seed, dashboard and the migration. ruff, black and mypy are clean.
- **The backend tests pass:** `modules/discography/tests/backend`, 43 tests (audio, service, job, server copy, seed and dashboard). `tests/test_migrations.py`: all 60 pass, the round trip with a row in each of discography's six tables included (the full suite hasn't run; CI's will).
- **The web is still the scaffold's stubs:** `modules/discography/web/`.
- **Main lane:** #142 (its handoff) landed, with main at `c923962`; blog 0.1.3 was about to push. Merge `main` into this branch before the suites. Check `gh pr list` and `git log -1 origin/main`.

## 4. The job, in order

1. **Contract tests** in `modules/discography/tests/contract/`, copying blog's `conftest.py` (moto S3, harness test app, the Browser class):
   - every route's access;
   - a stale `version` 409;
   - a draft 404, a scheduled release going live, a moved slug's 301;
   - an upload through HTTP: 201, then `POST /api/_test/jobs/run`, then the track plays;
   - the four upload refusals;
   - the body limit on the two upload routes.
2. **The web**, copying blog's `web/` (`api.ts`, `reads.ts`, `public.ts`, `module.web.ts`):
   - admin pages `AdminMusic`, `AdminRelease`, `AdminTracks` and `AdminCredits`, to the boards (VM Website `design/site/Admin*.dc.html`, to read only);
   - public pages `Music`, `Release` and `Track`. A native `<audio controls preload="none">` plays an upload; a SoundCloud track is a link;
   - web tests in `tests/web/`, and an e2e spec;
   - the web checks a file's size before upload (60 MB) and shows the FLAC words.
3. **The rest of the files:**
   - `MODULE.md` and `CHANGELOG.md` rewritten;
   - `tools/host_variables.py` gets a discography line (storage);
   - `package.json`'s `api:types` and `api:check` get discography;
   - SPEC's change log gets a line for decision 0070 (sections 6 and 15).
4. **Make the generated files again:**
   - `python -m mechframe catalog`;
   - `python -m tools.openapi`, then `npm run api:types`;
   - `python -m tools.event_schemas`;
   - `python -m tools.host_variables`;
   - `docs/progress.json` (Step 2), then `python -m tools.progress`.
5. **Check it:** the `module-contract-lint` skill, then `mechframe add discography` and `mechframe check` on a fresh site.
6. **Land it** (as the M8 prompt says, §3, step 4): merge `main` and make the generated files again from main's copies; read the next PR number from GitHub just before the one push; then fast-forward on a green "CI result" with the bots clear.

## 5. Ask the owner, don't decide

Nothing is open. The contract's "Changes as built" lists what the backend did differently (the 409 code, the 60 MB cap, search by release, the roles in the migration). Add to it as the web is built, and flag each in the PR.

## 6. Environment and traps

- **Tests:** set `$env:PYTHONUTF8 = "1"`, `$env:MECHFRAME_REQUIRE_DB = "1"` and `$env:TEST_DATABASE_URL = "postgresql://devkit:devkit@localhost:55432/postgres"`, then run `...\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider modules/discography/tests`, with the log in the scratchpad.
- **The worktree guard** refuses git commands it can't place (`git -C`, pipes after `git`, `&&` chains). Run git plainly from the worktree's root.
- **`@jobs.handler` makes a `Job`:** a test calls `jobs.process_track.run(ctx, payload)`.
- **A job writes in its own session:** `await db.refresh(row)` afterwards; `expire_all` then lazy loads fail with MissingGreenlet.
- **`events.emit` refuses without the app's catalog:** the backend conftest fakes it for every test (`said`).

## 7. Evidence and next IDs

- The contract; decision 0070 (the licence table); `modules/discography/tests/backend/`.
- **IDs:**
  - decisions: the side lane's are 0071 and up;
  - migrations: `discography_0001` is used;
  - PR numbers: read from GitHub at push time.

## 8. Candidates for `knowledge/`

1. PyAV's PyPI wheels bundle GPL libx264 and libx265, though their FFmpeg reports LGPL v3. Check `av.libs` before adopting PyAV in closed source.
2. soundfile 0.14's wheels write MP3 through libsndfile. A constant bitrate is `compression_level=(320-kbps)/288` with `bitrate_mode="CONSTANT"`, and LAME snaps it to the nearest standard rate.
3. `@jobs.handler` returns a `Job`: call `.run`.

## 9. Result

(The side lane writes what shipped here, for the main lane's handoff.)
