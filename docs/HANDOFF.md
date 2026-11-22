# Handoff

Overwritten every session. This one: 2026-11-21, evening Eastern (Claude Code, the owner's machine), session M3 of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Landed: VM Website's items 6 and 7 (#113, #114), the handoff (#115), and the first module, `media`, with per-route body limits (#116). `main` is `fde6a90`.

## State

- **The kernel is done**, K0 to K5; hooks 1 to 8 of the ten are in (decision 0052). Entitlements and profile tabs wait.
- **#113, `<AfterFooter>`** (VM item 6): a page's part after the site frame's footer, a portal into a `display: contents` holder, so a sticky bar sticks over the whole page. Contract `dev plans/contracts/after-footer.md`.
- **#114, the upgrade's new site files** (VM item 7): a template file new in `backend/app/site/` or `web/src/site/` is written where the site has none. With no `SITE_NAME`, one that carries the name stops the run. The owner approved the change to decision 0053 §5.
- **#116, `media`**, landed at `fde6a90`. Its contract is `dev plans/contracts/media.md`, approved 2026-11-21 as recommended. Its "Changes after approval" lists 12 things the build and the reviews moved.
  - **Backend:** VybeSite's upload rules (`pictures`), `media_image`, `media_use` and the sequence `media_file_version_seq` (`media_0001`, which grants admin and editor), the staff routes, `public.py`, and hooks 4, 7 and 8.
  - **Web:** `/admin/media` to the AdminMedia board (which VM Website has since redrawn to match), and `public.ts`'s `ImagePicker` and `Picture`.
  - **Decision 0054, the owner's choice:** a module's `BODY_LIMITS` lets its named routes take more than MAX_BODY_BYTES, up to 64 MB, while it's on. The start refuses an entry that names no route and two that can match one request.
  - **Tests and gates:** Playwright runs `modules/*/tests/e2e`, the owner's OK. A kernel test and three hook contract tests now allow real modules beside the probe. Mutants were caught throughout, and media's backend is at 95.75%.
  - **Reviews:** Codex's 4 and CodeRabbit's 21 findings were fixed with tests, and so were their follow-ups. One was a misread, answered with a test. CodeRabbit hit its chat limit at the end.
- **The progress ledger:** `steps` points at `/_blob/8153bd635ff8bf573eb9965c192da7b3` (from `fde6a90`; step 1 is next). Its `data/users/me` `check` wasn't written yet, since the page hadn't drawn. The old asset `fe086f5b0b23e9e6621a99d0fe0cd7bb` stays until it has.
- **v1.0:** 78% (48 of 61 steps).

## Next

1. **Session M4** (`dev plans/2026-11-21-next-session-m4-pages-blog.md`): `pages`, then `blog`, which requires media.
2. M5 as the plan has it.

## Open questions for the owner

- **A flaky end-to-end test:** `kernel/tests/e2e/sign-in.spec.ts:389`, axe on the account's pages, failed once on main at `0d19081` with `AbortError` and has passed since.
- Hooks 6 to 8's changes after approval; a public name and handle for a person (hook 10); the Vibrant Mindz content; `mechframe-iac-probe` on Railway; the rest of M2's list.

## Notes

- **Cleanup that follows a transaction** decides at the outer transaction's end (`after_transaction_end`, root). A savepoint's release fires `after_commit`, and the kernel's `get_db` closes its session with no rollback (`media.service._when_done`).
- **A key that a rolled-back try may reuse** needs a number no rollback undoes: a Postgres sequence.
- **`npx.cmd` and an argument with a space** fail in cmd: use `--testNamePattern=word` or `--grep=word`.
- **Black's check covers the tests:** run `python -m black --check .` before a push.
- **The full suite** is 25 minutes; run it in the background, editing nothing in that checkout meanwhile. A worktree under `.claude/worktrees/` lets work go on, but remove its folder (`rmdir`) if `git worktree remove` stops on "Permission denied".

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
