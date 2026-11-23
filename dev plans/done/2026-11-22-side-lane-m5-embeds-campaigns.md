# Side lane: M5 continued, land embeds, then campaigns

Start a new session **in a worktree** of `C:\DEV\AI-DevKit` (Code tab → New session → this project, in a worktree). Then: "Read dev plans\2026-11-22-side-lane-m5-embeds-campaigns.md and follow it, starting with section 3."

This is for the side lane's next session. While **AI DevKit Development 35 WT** is still running, it carries on, and this prompt waits.

## 1. The project and your lane

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane works in the main checkout: it lands contact 0.1.1 (#129), then media's round 3, then blog's AI and the account's name field.

- **The worktree** uses the main checkout's `.venv` python and a junction to its `node_modules`. The setup, the Playwright config for a worktree, and the traps are in `dev plans/done/2026-11-22-side-lane-m5.md`, sections 1 and 4.
- **Before pushing:** your module's suites, `npm run lint`, `npm run typecheck`, ruff, black and mypy. CI's full suite gates the PR.
- **Tell the main lane** (`ListAgents`, the newest "AI DevKit Development" in the main checkout) before and after every end-to-end run.

## 2. What you own, and what you don't

- **Yours:** `modules/embeds/` and `modules/campaigns/` with their contracts; the kernel files #127 changes (`MarkdownEditor.tsx`, `Prose.tsx`, `slots/types.ts`, `app/mount.tsx`, `app/lazy.ts`, `app/editorTools.ts`) until it lands; decision 0060 (embeds) and 0062 and up (campaigns); `campaigns_0001`.
- **Not yours:** `modules/contact/`, `modules/blog/` and `modules/media/`; the kernel's AI (0058) and the account's name field (0061, `kernel_0016`, `kernel_0017`); `docs/HANDOFF.md` and `CLAUDE.md`'s state.

## 3. The job

1. **Embeds, #127** (`feat/embeds-module`, in `.claude/worktrees/concurrent-session-standby-fbaf9e`): read `gh pr view 127` and its threads.
   - If it's open with "CI result" green and the bots clear: merge `main`, make the generated files again, run its suites, then land it by fast-forward (`CLAUDE.md`, Rules).
   - Then tell the main lane: blog's AI buttons register as a kernel entry in `KERNEL_EDITOR_TOOLS`.
2. **Campaigns:** its contract (decision 0062, `campaigns_0001`) was drafted on a local branch in that worktree, waiting on the owner. Find it with `git branch -a`.
   - It listens to `contact.news.requested` (`{message_id, email, name}`, at least once) and `blog.post.published`.
   - Ask the owner about the email service before its sends. Code only after the owner approves the contract.

## 4. Evidence

- `dev plans/contracts/embeds.md` (on #127) and `contact.md`.
- Decision 0060 (on #127).
- `modules/contact/` is the pattern for a public form, hooks 5, 7 and 8, and a list-and-panel admin page.

## 5. Result

AI DevKit Development 35 WT ran this prompt, 2026-11-22, to about 16:40 Eastern.

- **Embeds, #127, landed** at `f560ed5` by fast-forward. It has "CI result" green and no open threads after Codex's 2 findings and CodeRabbit's 19, each fixed with a test seen failing first. CodeRabbit was rate-limited on the last commit, and cubic's trial is out of reviews. The PR adds:
  - `modules/embeds` 0.1.0;
  - decision 0060, the kit's text slots `editor.tools` and `prose.embed`; blog's AI buttons go in `KERNEL_EDITOR_TOOLS` (`kernel/web/src/app/editorTools.ts`);
  - `test_hook_consent` made to hold for any module with media hosts.
  The main lane was told.
- **Campaigns' contract is approved** (`dev plans/contracts/campaigns.md`, on the local branch `feat/campaigns-module`, not pushed). The owner's choices:
  - SMTP through the site's mailer, with Resend only where a host blocks SMTP;
  - double opt-in;
  - a post's email goes as it goes live;
  - owner and admin send;
  - bounces are read over IMAP in this PR, since the site sends by Spaceship's Spacemail;
  - `send_per_hour` is 6,000 by default, since Spacemail has no sending limit. (Since changed, 2026-11-23: Spaceship documents 500 an hour for a paid mailbox and 20 on a trial, so the owner chose 400; `dev plans/contracts/campaigns.md`, §8 6.)
- **For the main lane's handoff:**
  - #127 landed and step 1's row lists it;
  - campaigns is built next, in the side lane, from `dev plans/2026-11-22-side-lane-m6-campaigns.md` (on `feat/campaigns-module`);
  - it claims decision 0062 and `campaigns_0001`.
