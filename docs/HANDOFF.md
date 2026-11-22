# Handoff

Overwritten every session. This one: 2026-11-21 night to 2026-11-22 early morning Eastern (Claude Code, the owner's machine), session M4a of `dev plans/2026-11-21-vibrant-mindz-push-plan.md`. Landed: #118 and #119; this handoff is #120. `main` is `f3fc712`.

## State

- **`pages`' contract is approved** (`dev plans/contracts/pages.md`, 2026-11-21): a Markdown page for now, VybeSite's builder ported after it ("that was really the whole point"; a later step in `docs/progress.json`); the editor in the kernel; a live page's Save changes the site; header and footer menus, through link slots a module loads and a new `nav.footer` (decision 0056, to write with pages' PR). Nothing of `modules/pages/` is built yet.
- **#118, the kernel's Markdown** (decision 0055): `kernel.markdown` (`render`, `plain`, `excerpt`: python-markdown, then nh3 to `server_copy.cleaned`'s allowlist, an `h1` made an `h2`), and the kit's `MarkdownEditor`, `Prose` and `SearchFields`, on the kit page with a Playwright test of the undo. `markdown` and `types-Markdown` joined the pins.
- **#119, media and the kit to the boards** (CodeRabbit was rate-limited and never reviewed it; Codex found nothing; landed on green CI, the owner's rule) (VM Website Dev 08's nine items and canvas version 82, the owner's calls): media 0.1.1's tiles and panel, the kit's `SearchBox`, an action's icon before its words, the attention row at 390, `opacity.55` (required), the session's `name` on the person card, the boards' admin sections by default, the bell after the breadcrumb, and the template's seed test on a stand-in S3. Decisions 0042 and 0044 amended.
- **`blog`'s contract is drafted** (`dev plans/contracts/blog.md`) with the owner's answers: four PRs (the blog, the kernel's AI help, SVG covers into media, social posting), AI help in the kernel, related posts and social posting now, the claims list later. Three smaller questions are still to ask (§8).
- **The progress ledger:** `steps` points at `/_blob/aebed8eb43ca342bcba2bb7284ae57fe` (from `f3fc712`). Its `data/users/me` `check` isn't written yet, since the page hasn't drawn; the assets `8153bd635ff8bf573eb9965c192da7b3` and `fe086f5b0b23e9e6621a99d0fe0cd7bb` stay until it has.
- **v1.0:** 78% (48 of 61 steps). Step 1 lists #116, #118 and #119; VybeSite's builder is a later step after launch.

## Next

1. **Build `pages`** (`dev plans/2026-11-22-next-session-m4-build-pages.md`), one PR with decision 0056.
2. **`blog`**, its four PRs in order; M5 after.

## Open questions for the owner

- `blog.md` §8, 5 to 7: the Anthropic key's home, social posting's home and its Buffer token, who writes.
- **A person's name:** the session answers `name` and the card shows it, but nothing sets `display_name`. An account field now, or with hook 10's name and handle?
- Earlier ones: the flaky axe test at `kernel/tests/e2e/sign-in.spec.ts:389` (once, at `0d19081`); hooks 6 to 8's changes after approval; the Vibrant Mindz content; `mechframe-iac-probe` on Railway.

## Notes

- **`kernel.markdown`** renders per read; a module caps a body itself (100,000). python-markdown expands a tab, so `java<tab>script:` arrives as `java    script:`, a path on the site to a browser.
- **The editor's buttons** type through `document.execCommand("insertText")`, the only call that keeps the browser's undo; jsdom has none, so Vitest takes the fallback and Playwright the real path.
- **A field drawn as a box** (`SearchBox`, the editor) takes the admin's ring on the box (`:has(:focus-visible)`), the control inside none.
- **Worktrees:** Playwright finds no tests in one under `.claude/` and needs `E2E_PYTHON`; run end-to-end specs from the main checkout.
- **A Bash heredoc** turns `\\n` into a newline before Python reads it: write such scripts to the scratchpad with Write.

## Warnings

- Nothing from VybeSite's `dev plans\` or `snapshots\`; run its brand check on lifted code.
- Editing CI's security gates is the owner's call. Never apply a site's `railway.ts` for the owner. Never edit `C:\DEV\VM Website`.
