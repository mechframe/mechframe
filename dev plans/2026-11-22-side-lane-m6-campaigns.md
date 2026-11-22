# Side lane: M6, build campaigns

Start a new session **in a worktree** of `C:\DEV\AI-DevKit`. First run `git switch feat/campaigns-module`. That branch is local, not pushed, and holds this file and the approved contract. Then follow this file from section 3.

## 1. The project and your lane

MechFrame: website modules on a FastAPI + Postgres kernel (`CLAUDE.md`, `SPEC.md`). You're the **side lane** (`CLAUDE.md`, "Two lanes"). The main lane is the newest "AI DevKit Development" in the main checkout (`ListAgents`). It does media's round 3, then blog's AI (0058) and the account's name field (0061).

- **Worktree setup and traps** (the main checkout's `.venv`, the `node_modules` junction, Playwright's config on port 8781): `dev plans/done/2026-11-22-side-lane-m5.md`, sections 1 and 4.
- **Before pushing:** campaigns' suites, the kernel tests you touch, `npm run lint`, `npm run typecheck`, ruff, black, mypy, `python -m tools.validate_schemas` and the brand check. CI's full suite gates the PR.
- **End-to-end runs:** tell the main lane before and after each one.

## 2. What you own, and what you don't

- **Yours:**
  - `modules/campaigns/` and its contract;
  - decision 0062, which makes `email.queue_message` public, with SPEC 6's table and a change-log line;
  - migration `campaigns_0001`.
- **Not yours:**
  - `modules/contact`, `blog`, `media` and `embeds`, except to read their `public.*`;
  - the kernel's AI and name field (0058, 0061, `kernel_0016`, `kernel_0017`);
  - `docs/HANDOFF.md`, `CLAUDE.md`'s state and the ledger.
- **The owner's:** every host variable (the Spacemail IMAP login, the postal address) and any third-party account.

## 3. The job

**State, checked 2026-11-22 about 16:45 Eastern:**
- main is at `f560ed5`, with embeds (#127) landed;
- no PR is open, and the newest issue or PR is #130;
- `feat/campaigns-module` is main plus the contract's commits, local only.

1. **Build campaigns to `dev plans/contracts/campaigns.md`** (approved).
   - Read the contract whole first.
   - Then read two modules:
     - `modules/contact/`: the pattern for a public form, Settings, the Inbox's tabs, and hooks 5, 7 and 8;
     - `modules/blog/`: the editor, crossed saves, and `blog.post.published`.
   - **The kernel's part first,** in a commit of its own: decision 0062, SPEC 6, and `queue_message` public with its test.
   - **Lifting from VybeSite:** lift §1's services with `mechframe-module-extractor`, and run the brand check before the PR. Never copy from VybeSite's `dev plans\` or `snapshots\`.
   - **Tests first,** §7 as the list. The bounce reader is tested against a fake IMAP mailbox, and peeks at headers only.
2. **Generated files:**
   - `docs/progress.json`: campaigns' PR and 0062 on its step, then `python -m tools.progress`;
   - `python -m mechframe catalog`, with `cli` on `PYTHONPATH`;
   - `python -m tools.openapi`, then `npm run api:types`.
3. **Land it:**
   - merge main and make the generated files again (take main's copies, never merge them by hand), then run the suites green;
   - take the PR number from GitHub just before the push, and push once;
   - land by fast-forward once "CI result" is green and the bots are clear.
4. **Tell the owner** that the content intake needs the postal address and the Spacemail mailbox's IMAP login, typed into the host's variables by them.

## 4. Open for the owner

Nothing. The editor isn't drawn: if the build needs what §2 doesn't settle, ask first.

## 5. Traps

- PowerShell's `Set-Content -Encoding utf8` writes a BOM. Edit with Edit or Python, and commit with a message file (`git commit -F`).
- eslint's react-hooks 7 forbids a setState in an effect and a ref read during render. Adjust state during render when inputs change.
- `test_site_template` fails on Windows without `PYTHONUTF8=1`, because of black's emoji.
- The review bots' quota is shared and CodeRabbit rate-limits, so push once and batch the fixes. cubic's trial is out.
- Memory notes: `C:\Users\vybec\.claude\projects\C--DEV-AI-DevKit\memory\`.

## 6. Promotion candidates

- `dangerouslySetInnerHTML` needs a stable `{__html}` object, or React rewrites the DOM each render and portals into it vanish.
- A local branch can be checked out in one worktree at a time: detach before handing it on.

## 7. Result

(Filled in by the side lane before it closes: the PR, what was built, tests, the owner's choices, and what the main lane's handoff should say.)
