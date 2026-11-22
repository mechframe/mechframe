# Media round 2: Admin › Media against its board (sent by VM Website)

VM Website Dev 09 measured Admin › Media against the canvas's board (version 82) after #118 and #119, part by part, at 1440 and 390. The owner chose to send all ten on 2026-11-22, about 02:40 Eastern ("Send all ten"), and again at about 09:30 ("Yes, send it"). This is the queue for the PR that fixes them; VM Website checks parity again when it lands. Its own record: `C:\DEV\VM Website\dev plans\2026-11-21-admin-media-parity.md`, "Round 2" (read it, never edit it).

## The admin kit (every admin page)

1. **Line height.** The kit sets 1.5 where the boards leave the browser's normal (about 1.25 at these sizes). The lead line is 23px tall against 19 and the attention box 81 against 76, so everything below sits 10px lower; a tile's name is 19 against 16, the panel's note 18.5 against 16 a line. **The owner chose (2026-11-22): match the boards, and keep 1.5 for prose.** The admin's labels, leads, tiles and panels take the browser's normal; long text (`Prose`, the Markdown editor's text, post bodies) keeps its own.
2. **The search box** is filled `#070A16` where the board's has no fill, and its text is 15px against 14.

## Media's page

3. A tile's corner is 10px against 12.
4. The "No alt text" pill is as wide as its words (97px) where the board's spans the tile (161px at 1440); its text is 13px against 12.
5. The panel starts level with the search box; the board's starts level with the grid, below the search row (42px higher at 1440).
6. The alt box is 81px tall against 64.
7. The hint under it is weight 500 against 400.
8. "Only decoration" is 14px weight 600 against 16px weight 400.
9. "Used in"'s link is bone against `#36B4FF`.
10. The panel is 820px tall against 786: the sum of the above.

## Where the line height comes from (found 2026-11-22)

- It's the theme's type tokens, not the kit: `type.body` is 15px/1.55 in Vibrant Mindz (1.6 in Machined Light) and `type.small` 14px/1.5, set through the `font` shorthand. The base layer gives `body` `type.body`, so the admin inherits 1.55 (`kernel/web/src/app/frames.css`).
- One way that keeps the tokens: a CSS layer after `mf.kit`, scoped to `.mf-admin-look` (`AdminFrame.tsx`), giving the root `line-height: normal`. It also gives it to the kit's and the admin's classes that take `type.small` or `type.body`: `.mf-attention-why`, `.mf-switch-label`, `.mf-table`, `.mf-tab` and the rest, listed with an awk over `kit.css`, `admin.css` and `settings.css`. It leaves `.mf-prose`, `.mf-editor-text` (1.8) and `.mf-input` (1.45, which the board's field has too) alone. Modules' stylesheets are unlayered, so media's own rules are set in `media.css`.
- **Check every admin page after,** not only media's: `kernel/tests/e2e/parity.spec.ts` and the kit page, in both themes. It's an amendment to decisions 0042 and 0044, with no number.

## The tokens the media items need

- A tile's 12px corner is `radius.md` (12 in both themes).
- "Used in"'s `#36B4FF` is Vibrant Mindz's `color.info`, the semantic token to use (Machined Light's is its info-700).
- The hint's weight and "Only decoration"'s size and weight are set in `media.css` after the `font` shorthand.

## Done means

Each item matches its board in both themes (the kit's are tokens, never a theme's hex), media's web tests and e2e pass, axe is clean, and the reply to VM Website names the PR.

## Result (2026-11-22, session M4d, #126)

All ten, in one PR. The kit: inside `.mf-admin-look` the root and each kit, admin and Settings part whose `font` sets type.body or type.small take `line-height: normal` (same layer, one class more specific; `.mf-prose`, `.mf-editor-text` and `.mf-input` keep theirs), and `.mf-search` has no fill, its words type.small. Media 0.1.2: the search row above both columns, the tile's corner `radius.md`, the pill the tile's width in 12px, the alt box two lines at its 64px least height, the hint 400, "Only decoration" 16px 400, "Used in" `color.info`, the facts in normal. Checked in a browser by `modules/media/tests/e2e/media.spec.ts` ("draws to its board", both themes, the library stubbed) and the kit page's two new checks; the whole end-to-end suite (97) passes, axe clean. Axe found one more on the way: the missing-alt tile's visible words ("…webpNo alt text", two inline spans) weren't in its name (WCAG 2.5.3); a space between them fixes it.

Not changed: pages' `.mf-pages-address` and `.mf-pages-by` and blog's `.mf-blog-count` set type.small in their own stylesheets, so they keep 1.5 until those pages' own parity rounds.
