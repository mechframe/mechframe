# Changelog: portfolio

## 0.1.0

- The first build (`dev plans/contracts/portfolio.md`, decision 0074), from the Vibrant Mindz backend scaffold of 2026-11-15:
  - pieces with a picture from media, one discipline (the kernel's `portfolio_discipline`), the account they're credited to, a year, a few words and an optional YouTube link, drafted, scheduled and published through the kernel's lifecycle;
  - two permissions: `portfolio.piece.add` (add pieces, and change your own while you hold it) and `portfolio.piece.manage` (every piece, and its credit);
  - Collective › Portfolio, drawn to VM Website's AdminPortfolio board: the note while pieces have no artist, the chips, the tiles and their pills, the editor, and the Disciplines dialog;
  - the Art page at `/art`, `/art/:discipline` and `/art/piece/:slug`, drawn to the Art board, with its server copy (`VisualArtwork`, `CollectionPage`, the sitemap);
  - search, item references (`portfolio.piece`), export and erase, the seed, and the Settings section "Art page";
  - `public.py`'s `piece_cards` and `pieces_by`, and `public.ts`'s `PieceCard` and reads.
