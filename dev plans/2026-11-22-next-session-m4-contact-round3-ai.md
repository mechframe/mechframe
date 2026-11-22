# Next session, main lane (M4, continued): media's round 3, a site's mypy, then blog's AI

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-22-next-session-m4-contact-round3-ai.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). The repo is public: mechframe/mechframe. This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). The side lane (the newest "AI DevKit Development … WT") builds campaigns next, from `dev plans/2026-11-22-side-lane-m6-campaigns.md` on its local branch `feat/campaigns-module` (`a8967b2`, not pushed): decision 0062, `campaigns_0001`, the contract approved by the owner on 2026-11-22 (the side lane's report), sent by Spacemail with bounces read over IMAP.
  - Fold its M5 result into your handoff: embeds (#127), and that branch's `done/2026-11-22-side-lane-m5-embeds-campaigns.md`, section 5 (main keeps the old copy until campaigns lands).
  - Tell it before and after every end-to-end run.
- **VM Website Dev 10** (it took over from Dev 09) relays the owner's calls for the site. Confirm a new ask with the owner, send PR numbers as they're pushed and as they land, and never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key (the Anthropic key included).

## 3. State (verify it)

- **main:** `f560ed5`: contact 0.1.1 (#129) and embeds (#127, the text slots `editor.tools` and `prose.embed`) landed after the handoff (#130). No PR is open; VM Website knows of #129. Check with `git log -1 origin/main` and `gh pr list`.
- **Uncommitted, on purpose:** this file's item 2b and `dev plans/2026-11-22-site-mypy-modules.md` (and its `dev plans/README.md` line), added after the handoff. Commit them with round 3's PR.
- **The ledger** points at the rows from `96a6ccc`; republish from `main`'s `rows.json` (made at `f560ed5`). Its old assets, and the rest, are in `docs/HANDOFF.md`.

## 4. The job, in order

1. **Republish the ledger** (`dev plans/progress-ledger/README.md`).
2. **Media's round 3** (`dev plans/2026-11-22-media-round-3.md`): two items, its own PR, every admin page checked after.
2b. **A site's mypy can't see its modules** (`dev plans/2026-11-22-site-mypy-modules.md`, from VM Website): a template fix, its own small PR.
3. **Blog's AI PR** (decision 0058). Write its contract first, `dev plans/contracts/kernel-ai.md`, for the owner to approve:
   - `ai.client()` (SPEC 6);
   - the key in `ANTHROPIC_API_KEY` or saved in Settings → AI, encrypted (the owner: "Host variable or Settings"), saying which wins when both are set;
   - Settings → Writing, from VybeSite's `writing_constitution.py` and `writing_styles.py`;
   - the editor's buttons (draft, titles, summary, search words, rewrite) as a kernel entry in embeds' `KERNEL_EDITOR_TOOLS` (`kernel/web/src/app/editorTools.ts`), from VybeSite's `routers/ai.py` and `services/anthropic_service.py`.
4. **The account's name field** (the owner: now): a Name on the account page, and in People for admins.
5. Then pages' crossed-save gaps (`docs/HANDOFF.md`), generated covers (§8, 3), social posting (ask §8, 7 first).

Close out at a natural break past ~400K tokens, with two prompts, one for each lane.

## 5. Ask the owner, don't decide

`blog.md` §8, 7, and the open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite** takes 26 to 34 minutes, in the background, its log in the scratchpad. Merge `main` first: a landing mid-run means a second run.
  `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov -q -rfE`
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test` with `TEST_DATABASE_URL`. `npx.cmd` mangles `|` and spaces in arguments (vitest's `-t` too): call node directly.
- **More traps:** `docs/HANDOFF.md`, Notes.

## 7. Evidence and next IDs

- Evidence: `docs/HANDOFF.md`; `dev plans/done/2026-11-22-media-round-2.md`, "Result"; `blog.md` §9; `contact.md`'s changes after approval.
- Yours: decisions 0058 (the AI) and 0061 (the name field), migrations `kernel_0016` and `kernel_0017`. PR numbers come from GitHub just before each push.

## 8. Candidates for `knowledge/`

1. `animation.finished` rejects (AbortError) on a cancelled transition: catch it.
2. Focus what React just drew from an effect, not a handler's `requestAnimationFrame`.
3. `npx.cmd` breaks `|` and spaces in arguments: call node directly.
4. `page.route` with a pathname predicate stubs an API for a layout check.
5. Merge `main` into a branch before its long local suite, not after.
