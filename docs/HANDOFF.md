# Handoff

Overwritten every session. This one: 2026-11-22, about 10:50 Eastern to 14:00 (Claude Code, the owner's machine), session M4d of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane. Landed: #126 (media's round 2) and #128 (blog 0.1.1). Open: #129 (contact 0.1.1, this lane's) and #127 (embeds, the side lane's). `main` is `96a6ccc`, #128's head; this handoff is its own docs PR.

## State

- **#126, media's round 2**, landed at `e558bf4`: all ten of VM Website's items, the owner's choice for the first (match the boards, keep 1.5 for prose).
  - The kit: inside `.mf-admin-look` the root and each part whose `font` sets type.body or type.small take `line-height: normal`; `Prose`, the editor's text and fields keep theirs; the `SearchBox` has no fill. Decisions 0042 and 0044 amended.
  - Media 0.1.2 drawn to the board; `media.spec.ts` checks it in a browser in both themes, the library stubbed. The result: `dev plans/done/2026-11-22-media-round-2.md`.
- **#128, blog 0.1.1**, landed at `96a6ccc`: blog's public surface for a site's own Blog and Post pages (VM Website's ask, placed first by the owner). `@/modules/blog/public` gives `usePosts`, `usePost`, `useCategories`, `isMoved` and the types; `blog.public` gives `posts`, `newest`, `post`, `categories` and `path`. It also fixed a shared e2e flake: `theme()` now treats a cancelled fade as finished.
- **#129, contact 0.1.1**, pushed, CI running, Auto-fix on. `useContactForm`, `useSendMessage`, `fieldErrors` and their types in `@/modules/contact/public` (VM Website Dev 10's ask; the owner gave it to the main lane), and "Message sent" taking focus in an effect (it missed under load). Land it on green CI with the bots clear, then tell VM Website Dev 10.
- **The side lane:** Dev 33 WT landed contact (#125, decision 0059) and closed. **AI DevKit Development 35 WT** has embeds up as #127 (decision 0060), in `.claude/worktrees/concurrent-session-standby-fbaf9e`.
  - Embeds adds the `editor.tools` slot, with `KERNEL_EDITOR_TOOLS` in `kernel/web/src/app/editorTools.ts`; blog's AI buttons register there.
  - Embeds changes `MarkdownEditor.tsx`, `Prose.tsx`, `slots/types.ts`, `app/mount.tsx` and `app/lazy.ts`. Ask Dev 35 WT before touching any of them while #127 is open.
  - Campaigns' contract (decision 0062, `campaigns_0001`) is drafted on its local branch, waiting on the owner.
- **The owner's answers today:** blog's public surface before blog's AI. Contact 0.1.1 in the main lane. The Anthropic key in "Host variable or Settings" (`blog.md` §8, 6). A person's name as an account field now.
- **The progress ledger:** `steps` points at `/_blob/7cba5e8f7e5bb99d774882ce79d9aaad`, the rows from `96a6ccc`. Step 1 lists #116, #118, #119, #121, #123, #125, #126 and #128; v1.0 is 78% (48 of 61). Its `data/users/me` `check` isn't written yet, since the page hasn't drawn. Once one passes, delete the older assets `4cac99854ca40e368540bc714384d490`, `3e1145cfa09a3512ee565b8d2d55e9e5`, `aebed8eb43ca342bcba2bb7284ae57fe`, `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.

## Next

1. **Land #129**, then tell VM Website Dev 10.
2. **Media's round 3** (`dev plans/2026-11-22-media-round-3.md`): the attention alert 3px short, and the alt box's resize handle.
3. **Blog's AI PR** (decision 0058): its contract `dev plans/contracts/kernel-ai.md` first, with the key's two places and which wins. The buttons go through embeds' `editor.tools` as a kernel entry.
4. **The account's name field** (the owner: now; decision 0061 and `kernel_0017` if it needs them).
5. Pages' two crossed-save gaps, then generated covers, then social posting (ask §8, 7 first).

## Open questions for the owner

- `blog.md` §8, 7: social posting's home and its Buffer key.
- Earlier ones: the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`; hooks 6 to 8's changes after approval; the Vibrant Mindz content; `mechframe-iac-probe` on Railway.

## Notes

- **IDs:** main lane 0058 and 0061, `kernel_0016` and `kernel_0017`; side lane 0060 (embeds) and 0062 and up (campaigns, `campaigns_0001`). PR numbers come from GitHub just before each push: embeds took #127, which this lane had expected.
- **The full Python suite takes about 26 to 34 minutes** here with the side lane at work. Merge `main` before it, not after: a landing between them means a second run.
- **Under load,** parity's `/nowhere` heading once took over 5s. The theme step and contact's focus were real races, both fixed.
- **A module's OpenAPI spec carries its version:** after a version bump, run `python -m tools.openapi` (`tests/test_openapi.py` catches it).
- **The root lint and black sweep `.claude/worktrees/`,** so the side lane's work in progress shows in this lane's runs. Read the file paths before counting a failure as yours.
- **`npx.cmd` mangles arguments** with `|` or spaces (`-g "a|b"`, `-t "two words"`): run `node node_modules/<pkg>/…` directly.
- **Worktrees:** `.claude/worktrees/multi-agent-worktree-plan-adc83e` (Dev 33 WT's, done) and `strange-cray-b32ad4` (old, detached) can go. Remove a junctioned `node_modules` with `cmd /c rmdir` first.
- **`CLAUDE.md` is 168 lines,** past the ~150 the workspace asks for: lean it when the owner says. `AGENTS.md` mirrors it but its title; M4c left it behind, and this handoff brings it back in step.
- **CodeRabbit** skipped #128 (its free review limit, shared by both lanes); Codex was clear.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
