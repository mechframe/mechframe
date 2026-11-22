# Handoff

Overwritten every session. This one: 2026-11-22, 08:30 to about noon Eastern (Claude Code, the owner's machine), session M4c of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Landed: #123 (`blog`). This handoff is #124. `main` is `c821437`, #123's head.

## State

- **`blog` landed (#123)** to its contract, approved for this first PR. `dev plans/contracts/blog.md` §9 lists what changed as it was built.
  - Posts in Markdown at `/blog/<slug>`, drafted, scheduled and published. A live post's save changes the site at once. A slug left out comes from the title. A live post's new slug leaves a 301 that never chains.
  - One category a post, from the kernel's `blog_category` terms. Writers choose; holders of `kernel.taxonomy.manage` edit them on the board's Categories card.
  - Covers through `media.public` and media's `ImagePicker`; up to three related posts; any writer as the author, readers seeing a display name only.
  - `blog.post.published` goes out once a post, on its first publish, scheduled ones too. Its two switches can't change after that.
  - The board, the editor, `/blog` and the post page; the server copy; the lifecycle, taxonomy, search, seed, privacy and dashboard hooks.
  - `mechframe add media`, `add blog`, then `mechframe check` pass on a new site, and the site's web typechecks and builds.
- **Decision 0057**, in #123: a module's web imports another's `public.ts` as `@/modules/<id>/public`, mapped in the repo's and the template's TypeScript, Vite and Vitest configs (SPEC 7). The kernel's AI writing help is now **decision 0058**.
- **Reviews on #123:** Codex's one and CodeRabbit's nine and a nitpick are fixed, each with a test seen failing first, and all 10 threads resolved. CodeRabbit skipped re-reviewing the fix push. It landed on green "CI result" with no open findings.
- **Two lanes** is a standing rule for this project (the owner): `CLAUDE.md`, "Two lanes". The side lane now is **AI DevKit Development 33 WT**, on M5 (contact, then embeds and campaigns) in `.claude/worktrees/multi-agent-worktree-plan-adc83e`. It claims decision 0059, `contact_0001` and `kernel/backend/kernel/notifications.py`.
- **The theme's `layout.breakpoint.1040`**, in #124 (VM Website Dev 09, the owner's OK, confirmed here): the site header's 20px nav gap now that Blog is a seventh link. Vibrant Mindz's `tokens.json` matches VM Website's copy again (`f8b5a94`, canvas version 83).
- **Media's round 2** from VM Website is recorded: `dev plans/2026-11-22-media-round-2.md`, the owner's line-height choice in it. It's the main lane's next job.
- **The progress ledger:** `steps` points at `/_blob/4cac99854ca40e368540bc714384d490`, the rows from `c821437`. Its `data/users/me` `check` isn't written yet, since the page hasn't drawn. Once one passes, delete the older assets `3e1145cfa09a3512ee565b8d2d55e9e5`, `aebed8eb43ca342bcba2bb7284ae57fe`, `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.
- **v1.0** is 78% (48 of 61 steps). Step 1 lists #116, #118, #119, #121 and #123.

## Next

1. **Media's round 2**, its own PR (`dev plans/2026-11-22-next-session-m4-media-then-ai.md`).
2. **Blog's AI PR** (decision 0058). Ask `blog.md` §8, 6 first. Then generated covers, and social posting (ask §8, 7 first). M5 is the side lane's.

## Open questions for the owner

- `blog.md` §8, 6 and 7.
- **A person's name:** nothing sets `display_name`, so a post's author shows no name on the site. Should it be an account field now, or come with hook 10's name and handle?
- Earlier ones:
  - the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`;
  - hooks 6 to 8's changes after approval;
  - the Vibrant Mindz content;
  - `mechframe-iac-probe` on Railway.

## Notes

- **VM Website, relayed:** #121's footer note is done (VM Website at kernel `e29b2fa` and pages 0.1.0, `1cfe103`, on staging). Before it adds `blog`, `mechframe upgrade kernel` brings the `@/modules/<id>/public` alias; Dev 09 knows.
- **Pages has the editor's two crossed-save gaps blog fixed in #123:** the retry dropping a field typed back to its saved value, and a conflict dropping what was typed while the save waited. A small follow-up for pages' `AdminPage.tsx`, after media's round 2.
- **`CLAUDE.md` is 166 lines,** past the ~150 the workspace asks for: lean it (`C:\DEV\LEAN-CONTEXT-PROMPT.md`) when the owner says.
- **Schema names are app-wide:** two modules' answer models with one name (`Full`, `Person`) rename the kernel's and pages' in the committed specs. Name a module's own (blog's `FullPost`, `BlogPerson`).
- **The e2e server runs with storage off,** so covers are tested by the contract suite (moto) and the web tests.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
