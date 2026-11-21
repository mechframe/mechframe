# Next session (M3): `media`, then M4

Run from `C:\DEV\AI-DevKit`: "Read dev plans\2026-11-21-next-session-m3-media.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`), public repo mechframe/mechframe. The kernel is done, and hooks 1 to 8 of the ten are in (#97 to #99, #102, #103, #107, #109, #110; decision 0052). This is session M3 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **`mechframe upgrade kernel` is built** (#111, decision 0053, from another session): a site takes the kernel's changes with it now (`cli/README.md`).
- **`media`** is lifted with `skills/mechframe-module-extractor/SKILL.md`, filling the hooks it needs, then linted with `module-contract-lint` and brand-checked. Its brief is in `docs/plans/vibrant-mindz-backend/extraction/`.
- **Hooks 9 and 10 wait** (the owner, 2026-11-21).
- **Landing:** push once the local suites are green; land by fast-forward on a green "CI result" with no open thread. Stage by name; run gitleaks on the staged diff.
- **Never edit `C:\DEV\VM Website`.**
- **The owner's call:** any Railway project, apply or variable, and CI's security gates.

## 3. State (2026-11-21, late afternoon Eastern; check it, don't trust it)

- **main** should hold #110 (`096e51e`) and this handoff (#112), with #109 (hook 7) and #110 (hook 8) landed. `git log -1 origin/main`, `gh pr list`. **If either is open:** land it on a green "CI result" (#110 fast-forwards once #109 is in), then republish the ledger (`dev plans/progress-ledger/README.md`).
- **A worktree** may be left at `.claude/worktrees/hook8`. Before `git worktree remove`, delete its `node_modules` junction with `cmd /c rmdir`, or the main checkout's `node_modules` goes too.
- The rest: `docs/HANDOFF.md`.

## 4. The job, in order

0. **Read the Vibrant Mindz handoff's "For MechFrame" list** (`C:\DEV\VM Website\docs\HANDOFF.md`, read only).
1. **`media`** (one PR): `blog` requires it. Its brief is in `docs/plans/vibrant-mindz-backend/extraction/`; it fills the hooks it needs (seed data, export and erase, consent for any embed host).
2. Then M4 (`pages`, `blog`), and M5 as the plan has them.

Close out at a natural break past ~400K tokens.

## 5. Ask the owner, don't decide

- Hooks 6 to 8's changes after approval (the contract's list).
- A public name and handle for a person (hook 10, which waits).
- More: `docs/HANDOFF.md`, "Open questions".

## 6. Environment and traps

- **The full suite** takes about 25 minutes on a quiet machine and hours at 100% CPU (other sessions). Run it in the background, its log in the scratchpad: `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov`. Edit nothing in that checkout meanwhile.
- **To keep working while it runs,** use a worktree under `.claude/worktrees/` with this checkout's `.venv` python and a `node_modules` junction. Write patch scripts with paths for the folder you mean; a `ROOT` left pointing at the main checkout edits it.
- **`eslint .` scans `.claude/worktrees/`:** lint by folder.
- **PR numbers go fast** when two sessions run. Predict at push time and check again just before.
- **Test traps:** `jobs/run` doesn't tick the scheduler (queue a scheduled job by name). A 404 `kernel.not_found` reads as "not built". A unit fixture restores kernel globals with `monkeypatch`. The contract suite's fake storage is per test.
- **The Bash tool decodes `\n` and `\uXXXX`,** and git writes CRLF on a merge: write patch scripts with the Write tool.

## 7. Evidence and next IDs

`docs/HANDOFF.md`, decisions 0052 and 0053, the hooks contract. Next free: PR #113 (#112 is this handoff), decision 0054, migration `kernel_0016`.

## 8. Candidates for `knowledge/`

1. A session-scoped fixture's environment outlives every test after it: set variables per test.
2. A scheduler that a test's "run due jobs" doesn't tick: queue the job by name.
3. A unit fixture that reinstalls a global hides a server that never installs it: restore the global with monkeypatch.
4. Parallel sessions on one PC: the CPU, the review bots' quotas and PR numbers are shared.
5. A worktree that shares `node_modules` by junction: remove the junction before the worktree.
