# Next session (M2): hooks 6 to 8

Run from `C:\DEV\AI-DevKit`: "Read dev plans\2026-11-21-next-session-m2-hooks-6-to-8.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`), public repo mechframe/mechframe. The kernel is done; hooks 1 to 5 are in (#97 to #99, #102, #103). This is session M2 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, with M1's stretch, hook 6, first. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **Each hook** is built to `dev plans/contracts/hooks.md` (decision 0052): its §2 row, §6 and its §7 test. Follow `skills/mechframe-hook-designer/SKILL.md` steps 3 to 6. `git show --stat 7f4a777` (#103's first commit) lists every place a hook touches. A change is a dated line under "Changes after approval", told to the owner in the PR.
- **Hooks 9 and 10 wait** (the owner, 2026-11-21): don't start them.
- **Landing:** push once local suites are green; land by fast-forward on a green "CI result" with no open thread. CodeRabbit keeps reviewing after a fix: answer each new finding with a fix and a test, or a reply saying why not. Stage by name; gitleaks on the staged diff.
- **Never edit `C:\DEV\VM Website`:** a Vibrant Mindz session works there.
- **The owner's call:** any Railway project, apply or variable, and CI's security gates.

## 3. State (2026-11-21, midday Eastern; check it, don't trust it)

- **main** should be #104's head (this handoff), with #103 (hook 5) landed at `3f0a79b` before it. `git log -1 origin/main`, `gh pr list`. **If #104 is open,** land it on a green "CI result", then republish the ledger if `docs/progress.json` changed (`dev plans/progress-ledger/README.md`).
- The rest: `docs/HANDOFF.md`.

## 4. The job, in order

Stack the PRs: start the next on a branch from the last while its CI runs, and merge `main` in once the first lands.

0. **Read the Vibrant Mindz handoff's "For MechFrame" list,** if it has one (`C:\DEV\VM Website\docs\HANDOFF.md`, read only).
1. **#105, hook 6, consent categories** (§2 row 6, §7 test 6, which has a Vitest half): the `CSP` entries' third item; `consent` on `GET /api/kernel/site`; `CONSENT_MODE` (`ask` by default) in `KernelConfig`, both `.env.example` files and the template's `railway.ts`; `useConsent` and `<ConsentGate>`, the choice in `__Host-mf_consent`, set by script. The CSP itself doesn't change.
2. **#106, hook 7, export and erase** (§2 row 7): it builds 14.7's export (a job, a ZIP in private storage, a mailed link) and `privacy.py`'s two functions; the start refuses `data_hooks` that disagree.
3. **#107, hook 8, dashboard cards** (§2 row 8): `dashboard.py`'s `ATTENTION` and `SETUP`, `GET /api/kernel/admin/setup`, the Set up card. Then decision 0052's Status reads "1 to 8 applied".

Close out at a natural break past ~400K tokens; the next prompt names what's left (M3).

## 5. Ask the owner, don't decide

- Fields and the gap ring; hooks 4 and 5's changes after approval (`bot.verify` gained `db=`); a public name and handle for a person (hook 10, which waits). The rest: `docs/HANDOFF.md`, "Open questions".

## 6. Environment and traps

- **The full suite** (Git Bash, in the background, its log in the scratchpad, about 25 minutes, no edits and no branch switch meanwhile, since CLI tests copy the kernel): `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov`. Run the hook's own tests and a mutant script first. **Never `--cov=<one kernel module>`.**
- **A review fix on a stacked PR, and CRLF after a pop:** `docs/HANDOFF.md`, "Notes".
- **Contract tests** call only routes in `docs/contracts/auth-api.md`. More: `docs/HANDOFF.md`, "Notes".
- **The Bash tool decodes `\n` and `\uXXXX`:** write patch scripts with the Write tool.

## 7. Evidence and next IDs

Decision 0052, the contract, the plan, `docs/HANDOFF.md`. Next free: PR #105, decision 0053, migration `kernel_0015`.

## 8. Candidates for `knowledge/`

1. A test-support route can stand for an environment variable a suite can't set on a running server.
2. Files a transaction's work writes go after its commit; an idempotent rerun converges.
3. A Pydantic field named like an imported module hides it in its own annotation.
4. A kernel call from a route reads through the route's session: a second connection can starve a small pool.
