# Next session, main lane (M4, continued): land contact 0.1.1, media's round 3, then blog's AI

Run from `C:\DEV\AI-DevKit`, the main checkout: "Read dev plans\2026-11-22-next-session-m4-contact-round3-ai.md and follow it, starting with section 4."

## 1. The project

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). The repo is public: mechframe/mechframe. This is M4 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Nothing is deployed.

## 2. Rules not in a CLAUDE.md

- **You're the main lane** (`CLAUDE.md`, "Two lanes"). The side lane is **AI DevKit Development 35 WT** (`.claude/worktrees/concurrent-session-standby-fbaf9e`): embeds as #127 (decision 0060), then campaigns (0062 and up).
  - While #127 is open, ask it before touching `MarkdownEditor.tsx`, `Prose.tsx`, `slots/types.ts`, `app/mount.tsx` or `app/lazy.ts`.
  - Tell it before and after every end-to-end run.
- **VM Website Dev 10** (it took over from Dev 09) relays the owner's calls for the site. Confirm a new ask with the owner, send PR numbers as they're pushed and as they land, and never edit `C:\DEV\VM Website`.
- **The owner's call:** Railway, CI's security gates, any third-party account or key (the Anthropic key included).

## 3. State (verify it)

- **main:** `96a6ccc` (#128), then the handoff PR. Check with `git log -1 origin/main` and `gh pr list`.
- **#129** (`feat/contact-public`, contact 0.1.1, yours): pushed green locally; its CI was running at close, Auto-fix on.
- **#127** (embeds, the side lane's): open.
- **The ledger** points at the rows from `96a6ccc`; republish once #129 lands. Its old assets are in `docs/HANDOFF.md`. The rest is there too.

## 4. The job, in order

1. **Land #129** on a green "CI result" with the bots clear, by fast-forward (`CLAUDE.md`, Rules). If `main` moved, merge it in, make the generated files again and rerun the suites first. Tell VM Website Dev 10.
2. **Media's round 3** (`dev plans/2026-11-22-media-round-3.md`): two items, its own PR, every admin page checked after.
3. **Blog's AI PR** (decision 0058). Write its contract first, `dev plans/contracts/kernel-ai.md`, for the owner to approve:
   - `ai.client()` (SPEC 6);
   - the key in `ANTHROPIC_API_KEY` or saved in Settings → AI, encrypted (the owner: "Host variable or Settings"), saying which wins when both are set;
   - Settings → Writing, from VybeSite's `writing_constitution.py` and `writing_styles.py`;
   - the editor's buttons (draft, titles, summary, search words, rewrite) as a kernel entry in embeds' `KERNEL_EDITOR_TOOLS` (`kernel/web/src/app/editorTools.ts`, once #127 lands), from VybeSite's `routers/ai.py` and `services/anthropic_service.py`.
4. **The account's name field** (the owner: now): a Name on the account page, and in People for admins.
5. Then pages' crossed-save gaps (`docs/HANDOFF.md`), generated covers (§8, 3), social posting (ask §8, 7 first).

Close out at a natural break past ~400K tokens, with two prompts, one for each lane.

## 5. Ask the owner, don't decide

`blog.md` §8, 7, and the open questions in `docs/HANDOFF.md`.

## 6. Environment and traps

- **The full suite** takes 26 to 34 minutes, in the background, its log in the scratchpad. Merge `main` first: a landing mid-run means a second run.
  `TEST_DATABASE_URL="postgresql://devkit:devkit@localhost:55432/postgres" MECHFRAME_REQUIRE_DB=1 .venv/Scripts/python.exe -m pytest --cov -q -rfE`
- **End to end:** `npm run build`, then `node node_modules/@playwright/test/cli.js test` with `TEST_DATABASE_URL`. `npx.cmd` mangles `|` and spaces in arguments (vitest's `-t` too): call node directly.
- **More traps** are in `docs/HANDOFF.md`, Notes: a version bump's OpenAPI spec, generated files after a merge, the sweep of the side lane's worktree, `monkeypatch.undo()`.

## 7. Evidence and next IDs

- Evidence: `docs/HANDOFF.md`; `dev plans/done/2026-11-22-media-round-2.md`, "Result"; `blog.md` §9; `contact.md`'s changes after approval.
- Yours: decisions 0058 (the AI) and 0061 (the name field), migrations `kernel_0016` and `kernel_0017`. PR numbers come from GitHub just before each push.

## 8. Candidates for `knowledge/`

1. `animation.finished` rejects with an AbortError when a transition is cancelled: catch it when waiting for fades.
2. Focus an element React just drew from an effect, not a `requestAnimationFrame` asked for in the handler: under load the frame can run first.
3. `npx.cmd` passes arguments through cmd.exe, where `|` and spaces break them: call `node node_modules/<pkg>/<cli>`.
4. `page.route` with a pathname predicate stubs an API, so a layout check can run on data the e2e server can't store.
5. Merge `main` into a branch before its long local suite, not after.
