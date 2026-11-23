# Handoff

Overwritten every session. This one: 2026-11-23, about 08:10 to 13:30 Eastern (Claude Code, the owner's machine, the owner on Remote Control), session M4f of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`, the main lane. Landed: #133 (M4e's handoff) and #135 (the AI's writing help); the side lane landed campaigns (#134) after it. `main` is `3fcdf35`, #134's head; this handoff is its own docs PR.

## State

- **#135, the AI's writing help** (decision 0058; contract `dev plans/contracts/kernel-ai.md`, approved as recommended), landed at `f18f764`:
  - `kernel.ai`: `await ai.client(db)` gives a `Writer`. The key is `ANTHROPIC_API_KEY` or one saved, sealed, in Settings → AI, and a saved key wins. The model is `ANTHROPIC_MODEL` (default `claude-opus-5-5`). `AI_RATE_LIMIT` is one budget a person, `20/1h`. A saved key that can't be opened answers 503, never the host's in its place.
  - `kernel.writing`: VybeSite's six rules as switches, the site's own rules and a five-box brief (a settings section). Writing styles are the table `kernel_writing_style` (migration `kernel_0016`), 50 at most. `kernel.ai.write` and `kernel.writing.manage` go to admin and editor.
  - Settings gains AI and Writing (a style has its own page), built from the kit with no board. Every `MarkdownEditor` gains **Write with AI** through `editor.tools`, for `kernel.ai.write`, drawn while a key can be used. Draft and Rewrite work on the text. Titles, Summary and Search words show for the fields a page hands it. A rewrite that loses a link's address is refused.
  - Blog 0.1.2 hands its title, summary and search fields to the editor. Its `MODULE.md` says `blog.public`'s dates are ISO text.
  - **VM Website Dev 12's finding is fixed** in it: a validator's own words reach its field without pydantic's "Value error, " (`errors.field_message`).
  - **No suite calls Anthropic:** the harness answers with `harness/fake_anthropic.py`. The first real call is the owner's Check in Settings → AI.
  - **The tests:**
    - full Python suite: 3,304 passed, 97.94% coverage;
    - web: 915 passed, 93.9% of lines;
    - `ai.spec.ts`: 3 passed (it runs serially: the site has one key).
  - **The reviews:** Codex's three findings are fixed, each with a test seen failing first:
    - the dialog under StrictMode;
    - long texts for the short tasks;
    - reference-style links in the rewrite guard.
    CodeRabbit was rate-limited and never reviewed #135; cubic is out of its trial. #135 landed on a green "CI result" with no open thread.
- **Campaigns, #134** (the side lane, AI DevKit Development 37 WT; decision 0062, `campaigns_0001`), landed at `3fcdf35`. Its result is §7 of `dev plans/done/2026-11-22-side-lane-m6-campaigns.md`, and its last review round is in the contract's "Changes after approval" (`dev plans/contracts/campaigns.md`).
  - **What it is:** the kernel's `email.queue_message` made public (SPEC 6); campaigns 0.1.0 with double opt-in sign-ups, the Newsletter page to its board, the editor, Settings › Newsletter, the send job at its pace, an IMAP bounce reader, Resend's webhook, and hooks 4, 5, 7 and 8.
  - **The owner chose** a send pace of 400 an hour (2026-11-23), under a paid Spacemail mailbox's 500.
  - **For the owner:** the postal address in Settings › Newsletter, and the Spacemail mailbox's IMAP login typed into the host's variables (`CAMPAIGNS_BOUNCE_IMAP_HOST`, `_USERNAME`, `_PASSWORD`).
  - **For blog (the main lane):** `blog.post.published` could carry the post's `summary`, so a post's email holds it. Campaigns already reads it when it's there.
  - **For VM Website:** `NewsletterSignup` from `@/modules/campaigns/public` in Music's, Blog's and Videos' sections, each with its own `source`. Contact's news box can ask `useNewsletterOn()`. VM Website Dev 12 has been told.
- **VM Website Dev 12** is the site's session now (Dev 10 and 11 are closed). It knows #135 landed. It sent three asks with the owner's OK, all placed in the two prompts:
  - the admin shell's five differences from the boards (main lane);
  - the signed-out 401 (main lane);
  - pages' `public.ts` read (side lane).
- **The progress ledger:** `steps` points at `/_blob/83dbe233a6b4002580bc69cdefa37ca9`, the rows from `3fcdf35`. v1.0 is 80% (49 of 61).
  - Its `data/users/me` `check` isn't written yet: the page hasn't drawn.
  - Once one passes, delete the older assets `03391c9cbf54e626a297614a0cfaa829`, `f973d1010fe6ff42eb7464c80ed06be9`, `d04f4fb64eb82a5cf3c6b5cc8ab5d1b4`, `7cba5e8f7e5bb99d774882ce79d9aaad`, `4cac99854ca40e368540bc714384d490`, `3e1145cfa09a3512ee565b8d2d55e9e5`, `aebed8eb43ca342bcba2bb7284ae57fe`, `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.

## Next

1. **The account's name field** (the owner: now; decision 0061): a Name on the account page, and in People for admins. `auth_user.display_name` (120 characters) is already there, so it may need no migration. Write its contract first.
2. **The admin shell's five differences** from VM Website (below). Four are CSS. The order of a section's pages needs a way for a site or a module's `nav.admin` to set it (decision 0063, if it changes the manifest).
3. **The signed-out session read:** the owner asks that `GET /api/auth/session` answer 200 with no user to a signed-out visitor, so a public page logs no 401. Write a contract first: auth-api's row, the web's session code, the template's end-to-end allowance (decision 0064).
4. Then blog: the post's `summary` in `blog.post.published` (for campaigns), generated covers (`blog.md` §8, 3, through `ai.client(db)`), then social posting (ask §8, 7 first).
- **The side lane, next:** pages 0.1.1, with its page read in `public.ts` (VM Website's ask) and the editor's two crossed-save gaps blog fixed in #123.

## The shell's five differences (VM Website Dev 12, measured on /admin/media at 1440 and 390)

1. `.mf-admin-nav a` is `line-height: 1.4` (admin.css:95); the boards draw `normal`.
2. A section's pages come in `modules.ts`'s order. The boards: Pages, Blog, Newsletter, Inbox, Media.
3. The bell's 32px button puts the icon 7px left: `.mf-admin-icon-button { margin: 0 -7px }`, and drop the phone rule's change to `.mf-admin-notices`' `margin-left`.
4. The person card's View site icon is 3px left: `.mf-admin-person-site { margin-right: -3px }`.
5. Menu at phone width makes the bar 61px, not 55: `.mf-admin-menu { margin: -3px -10px -3px 0 }`.

With these, VM Website measured the sidebar, top bar and phone bar pixel-identical to the board, every focus ring still clear. Its record: `dev plans/2026-11-21-admin-media-parity.md` in VM Website, Round 4.

## Open questions for the owner

- `blog.md` §8, 7: social posting's home and its Buffer key.
- Earlier ones: the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`; hooks 6 to 8's changes after approval; the Vibrant Mindz content; `mechframe-iac-probe` on Railway.

## Notes

- **IDs:** the main lane has 0061, 0063 and 0064, and `kernel_0017` and `kernel_0018`. The side lane has 0062 (campaigns) and 0065 and up. PR numbers come from GitHub just before each push.
- **For the owner:** the AI needs a key. Type `ANTHROPIC_API_KEY` into a site's host variables, or save one in Settings → AI and press Check.
- **Traps met in #135:**
  - React's controlled textarea: `execCommand("insertText")` run in an effect, or while a modal `<dialog>` makes the page inert, loses undo. Type the change after the dialog closes (`window.setTimeout(change, 0)`).
  - Under StrictMode, set an effect's refs in its setup, not only once.
  - An Alembic expression index compares as Postgres reads it back: `lower(name::text)`.
  - Anthropic's SDK 2.x sends the key as `Authorization: Bearer`.
- **The full end-to-end suite** timed out three tests with both lanes at work; each passed alone. CI runs them in 6 to 8 seconds against 27 to 30 here.
- **Still true:**
  - Run the full suite with `$env:PYTHONUTF8 = "1"`, and commit with `git commit -F <file>` after `git diff --cached --stat` as a step of its own.
  - A module's OpenAPI spec carries its version: run `python -m tools.openapi` after a bump.
  - The root lint and black sweep `.claude/worktrees/`, and `npx.cmd` mangles arguments with `|` or spaces.
  - The worktrees `campaigns-module-contract-065954` (its junction already removed), `multi-agent-worktree-plan-adc83e`, `strange-cray-b32ad4` and `concurrent-session-standby-fbaf9e` can go. Remove a junctioned `node_modules` with `cmd /c rmdir` first.
- **`CLAUDE.md` is about 170 lines,** past the ~150 the workspace asks for: lean it when the owner says.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner, never type a key for them, and never edit `C:\DEV\VM Website`.
