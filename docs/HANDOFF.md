# Handoff

Overwritten every session. This one: 2026-11-22, early morning to 08:30 Eastern (Claude Code, the owner's machine), session M4b of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Landed: #121 (`pages`). This handoff is #122. `main` is `2be4d49`.

## State

- **`pages` landed (#121)** to its approved contract.
  - Markdown pages with one-segment addresses. An address the kernel, the site's own pages or another module answers is refused.
  - Moves name the page, so none chains. A page that takes an address ends any move there.
  - A live page's Save changes the site at once. A crossed save is merged field by field (the kit's `SaveConflict`).
  - The list and the editor are drawn to the AdminPages and AdminPost boards.
  - The server copy, and the lifecycle, search, seed, privacy and dashboard hooks.
  - `mechframe add pages`, then `mechframe check`, passes on a new site.
- **Decision 0056**, in #121:
  - `defineModule({ links })` loads a link slot's entries from the module's API. Each new page reads them again once a minute old, and an editor's write reads them at once.
  - `nav.footer` is the footer's menu.
  - The kernel exports `NotFound` and `SLOT_LINKS`.
- **The template's fonts**, in #121: `vite.config.ts` never inlines a font. The template's e2e "every page loads with no console error once its fonts are in" was seen failing first, in a smoke site given a 3,900-byte font.
- **Reviews on #121:**
  - Codex: three findings. CodeRabbit: nine and a nitpick. All fixed, each with a test seen failing first, and all 12 threads resolved.
  - CodeRabbit's re-review of the last push was rate-limited. It landed on green "CI result" with no open findings, the owner's rule.
- **`blog`'s contract:** §8's 5, who writes, is answered: anyone with blog-writing permission writes and publishes, as recommended. Still open: 6 (the Anthropic key, before the AI PR) and 7 (social posting's home and its Buffer token).
- **The progress ledger:** `steps` points at `/_blob/3e1145cfa09a3512ee565b8d2d55e9e5`, the rows from `2be4d49`. Its `data/users/me` `check` isn't written yet, since the page hasn't drawn. Once one passes, delete the older assets `aebed8eb43ca342bcba2bb7284ae57fe`, `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb`.
- **v1.0** is 78% (48 of 61 steps). Step 1 lists #116, #118, #119 and #121.

## Next

1. **`blog`'s first PR**, the blog itself (`dev plans/contracts/blog.md`; the next session's prompt).
2. Then blog's AI PR (ask §8's 6 first), covers, and social posting (ask 7 first). M5 after.

## Open questions for the owner

- `blog.md` §8, 6 and 7.
- **A person's name:** nothing sets `display_name`. Should it be an account field now, or come with hook 10's name and handle?
- Earlier ones:
  - the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389`;
  - hooks 6 to 8's changes after approval;
  - the Vibrant Mindz content;
  - `mechframe-iac-probe` on Railway.

## Notes

- **For VM Website:** its own footer needs `<SlotOutlet name="nav.footer" />` for the footer's menu, and its header's `nav.public` now carries the pages put in the header's menu. Not yet relayed: the owner, or a VM Website session, carries it.
- **A Playwright name is a substring:** "Title" also finds "Title in search results", so say `exact: true`. Testing Library's names are exact.
- **A web test of a save that moves the route** must hold its mocked answer until the route has moved, as a network would. In jsdom the mock answers first and hides a remount.
- **A query's `staleTime` never refetches by itself** while its observer stays mounted, and mocking `Date.now` doesn't fire the timer that marks it stale. Use `query.isStaleByTime(ms)`.
- **`tools.site_smoke` crashes when it prints a failure to a redirected stdout** on Windows: cp1252 can't encode Playwright's "›". Set `PYTHONIOENCODING=utf-8`, or fix its `say`.
- **A signed-out page logs one console error by design:** the session check's 401 (`/api/auth/session`).

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
