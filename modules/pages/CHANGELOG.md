# Changelog: pages

## 0.1.1

- Its page read, for a site whose own page answers `/:address`: `web/public.ts` (`usePage`, `isMoved` and the answer's types `LivePage` and `PageMoved`, as `@/modules/pages/public`). pages' own page reads through the same hook (MODULE.md, "Extension points").
- The editor's crossed saves, as blog's #123: a save that meets someone else's works from the fields as they stand when it's answered. A field typed back to its saved value while the save waited is asked about, what was typed while it waited survives the conflict's choice, and a publish that lands while a field is asked about shows in the Publish panel.

## 0.1.0

- First version: Markdown pages with addresses, moves that never chain, the header's and footer's menus (decision 0056), the list and the editor, the server copy, and the lifecycle, search, seed, privacy and dashboard hooks (`dev plans/contracts/pages.md`, approved 2026-11-21).
