---
feature: mechframe upgrade kernel (a site takes the kernel's changes; session M3 of the Vibrant Mindz push plan)
status: approved
approved: 2026-11-21 (the owner: "Approve as recommended", the four answers in §8)
plan: dev plans/2026-11-21-vibrant-mindz-push-plan.md, M3; SPEC 12 and 13; cli/README.md
pr: 108 for this contract, docs only (predicted at push time); the build's own predicted when M3 starts
---

# Contract: `mechframe upgrade kernel`

## 1. Goal

A site made with `mechframe new` takes the kernel's changes from MechFrame's `main` with one command. Its own edits are kept, and it's told exactly what's left for an agent to merge. Today a site is refreshed by making a new one and moving its own parts across (the push plan, "Until `mechframe upgrade` exists").

## 2. Interfaces

`mechframe upgrade kernel [--site <dir>] [--from <ref>] [--base <commit>] [--merged <path>]... [--dry-run]`

- **New files** come from a Git ref of the CLI's own checkout, `--from main` by default (`git show <ref>:<path>`), never its working tree. So it works whatever branch the checkout is on. It fetches nothing, so `main` is the checkout's local `main`, and `git fetch` beforehand is the caller's job.
- **The base** is what the site was given. The lock gains `kernel.commit`, the commit the copy came from. `new` writes it only when every file it copies matches `HEAD`: the kernel's, the template's, the pins and the theme's `tokens.css`. `upgrade` always writes it.
- **An older lock** has no commit. Its candidates are the commits on `--from`'s history whose kernel files match every hash in the lock. If they all hold the same template files, pins and `tokens.css`, that's the base. If they differ there, the lock can't tell them apart, so it's refused, naming the first and last candidate, until `--base` names one; a template-only commit, such as a README fix, mustn't pass for a site edit. `--base` always overrides. With no candidate at all, it's refused too.
- **Each file is compared three ways:** L is the lock's hash, S the site's file, N the new one.

| Case | Does |
| --- | --- |
| S = L, N ≠ L | Writes N |
| S ≠ L, N = L | Keeps the site's (`check` still lists it as edited) |
| S = N | Writes nothing; the lock takes N |
| S ≠ L, N ≠ L, S ≠ N | **Conflict** |
| New in N, nothing at its place in the site | Writes it |
| New in N, a file of the site's at its place | **Conflict** |
| Gone from N, S = L | Deletes it |
| Gone from N, S ≠ L; missing from the site, N ≠ L | **Conflict** |
| Missing from the site, N = L | Stays missing |

- **Whole or not at all.** With any conflict, nothing in the site changes but `.mechframe/upgrade/`. That folder gets one unified diff per conflict, the base to N, for an agent to apply to the site's file, plus `README.txt` listing them. The command exits 1. Once the agent has merged a file, `--merged <path>` (once per file) keeps the site's file as it is, and the lock takes N's hash. With no conflicts left, it writes every file, takes `kernel.version` from the ref's `kernel.json`, sets `kernel.commit` to the ref's commit and records N's hashes, then empties `.mechframe/upgrade/`.
- **The template's files** follow the same rule. These are the pinned `requirements*.in` and `.txt`, `web/src/theme/tokens.css` for the lock's theme, and `templates/site/`'s files with the site's name and theme written in. The lock holds no hashes for them, so their base is the base commit's copy. Left out: the site's own folders (`backend/app/site/`, `web/src/site/`), the two registries (written from the lock), `.env.example` and `.railway/railway.ts`. The kernel's settings that are new since the base are printed, to add to the last two.
- **Prints next:** `pip install` if the pins changed, `npm ci` if the web package files did, the migrations (decision 0049's stop before a destructive one stands), the site's tests and `mechframe check`. `--dry-run` prints the table's verdict for each file and writes nothing.
- **Exits:** 0 when it's done, or there's nothing to do; 1 on conflicts, with the diffs written; 2 when it's refused: not a site, a lock that doesn't validate, not a Git checkout, an unknown ref, or no base found.

## 3. Data

No database. In `schema/lock.schema.json`, `kernel` gains an optional `commit`, matching `^[0-9a-f]{40}$`. Old locks still validate.

## 4. Files

- `cli/mechframe/upgrade.py` (new) and `cli/mechframe/gitref.py` (new; `rev-parse`, `show`, `log`, `ls-tree`, run with `git -C <checkout>`).
- `__main__.py`; `new.py` (writing `kernel.commit`); `schema/lock.schema.json`.
- Tests: `cli/tests/test_upgrade.py`, on a throwaway Git repo made in a temp folder with a kernel at two commits.
- Docs: SPEC 12 and 13, `cli/README.md`, and a new decision, 0053 if it's still free.

## 5. Conventions this follows

`add`'s whole-or-nothing and its refusals (decision 0050). The lock's hashes read `\r\n` as `\n` (decision 0047). Tests first, from the table in §2.

## 6. Non-goals

- `upgrade <id>` for a module. It waits for a module's second version (SPEC 12), and then uses the same code.
- `mechframe diff`.
- Conflict markers written into the site's files.
- Fetching or pulling.
- `check` saying how far behind `main` a site is.
- Downgrades.
- Touching the site's own folders.

## 7. Acceptance

- `test_upgrade.py`: one test per row of §2's table, and that a conflict writes nothing but the diffs. Then `--merged` clears a conflict, and a second run with none left writes everything.
- Also: an old lock's base found by its hashes; refused, naming its candidates, when candidates that match on the kernel differ in the template's files (a template-only commit between them), until `--base` names one; a bad `--base` refused; `new` leaving out `kernel.commit` when a copied file differs from `HEAD`; `--from` read from a ref while the working tree is on another branch; `--dry-run` writing nothing; the template's files and `tokens.css` under the same rule; and the exits.
- The live check: `tools.site_smoke`'s site, made at one commit and upgraded to a later one, passes its tests and `mechframe check`. Then the Vibrant Mindz site takes `main`'s kernel with it, in its own session.

## 8. Open questions

None. The owner answered all four on 2026-11-21, as recommended:

1. The base comes from Git: the lock's `kernel.commit`, new files from `--from main`'s commit, and an older lock's base found by its hashes.
2. When both sides changed a file, it stops, writes only the diffs, and takes `--merged` for each.
3. The template's files (the pins, `tokens.css`, `templates/site/`) follow the same rule as the kernel's copy.
4. The command is `mechframe upgrade kernel`, with `upgrade <id>` for a module later.

## Changes after approval

- 2026-11-21 (Codex on #108): **an older lock's base, found by its hashes, is refused when it's ambiguous.** The lock holds hashes only for the kernel's files. So several commits can match it while differing in the template's files: `4e9be32`, for one, changed only `templates/site/README.md`. Taking the newest match would make the site's older copy look like a site edit, and the fix would be kept out. Now the candidates must agree on the template's files, pins and `tokens.css`, or `--base` names one. For the same reason, `new` writes `kernel.commit` only when every file it copies matches `HEAD`, not just the kernel's. The owner's answer 1 stands; this narrows how it finds the base.
