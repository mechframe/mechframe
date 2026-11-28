# portfolio

The site's visual work: paintings, graphic design, animation and video, each a piece with its picture, who made it, its year and a few words, shown by discipline on the Art page, each at an address of its own. The contract is `dev plans/contracts/portfolio.md`; decision 0074 records the module and its two permissions.

## What it does

A piece has a title, an address under `/art/piece/` (made from the title, editable), one discipline, one picture from the media library, the account it's credited to, a year, a few words about it and, for a video, a YouTube link. It's drafted, scheduled and published through the kernel's lifecycle. The disciplines are the kernel's taxonomy (`portfolio_discipline`): staff holding `kernel.taxonomy.manage` add, rename and delete them on the Portfolio page, as blog's categories are.

**Who may change a piece** (decision 0074): someone holding `portfolio.piece.add`, such as a site's artist role, adds pieces, credited to themself, and changes and deletes the ones credited to them, only while they hold it. Staff holding `portfolio.piece.manage` change every piece and credit it to anyone who may add pieces, or to no one. The kernel's `require_owner_or` lets through anyone holding the permission it names, so an artist role must hold `add`, never `manage`.

Collective › Portfolio shows the pieces as a grid, newest edit first, by discipline: for staff holding `manage`, a warning while some have no artist ("Credit the first"); each tile's pill ("No artist", "Draft", "Scheduled"), and the editor beside the grid for the piece chosen. Add a piece picks its picture first. A save someone else got to first asks which to keep.

The Art page, `/art`, shows the live pieces newest first, with a chip for each discipline that has something live. Each chip is an address, `/art/<discipline>`. A piece's address, `/art/piece/<slug>`, is the same page with the board's panel open above the grid: the big picture, a video's player behind embeds' consent facade, the discipline, the title, "By petro, 2025", the words, "Commission work like this" while the settings have a link, and Close.

## Use when / avoid when

- Use when: the site shows visual work such as paintings, graphic design, animation or video, grouped by discipline.
- Use when: each piece needs its own address, credited to the artist who made it.
- Use when: artists add and edit their own pieces, and staff edit all of them.
- Avoid when: pieces are only for sale and need no showcase; use shop.
- Avoid when: it's an uncurated photo dump; a gallery block on a page is enough.
- Avoid when: the work is music or writing: that's discography or blog.

## What it adds

- **Routes**, under `/api/portfolio`:
  - public: `GET /pieces?discipline=&cursor=&limit=` (live pieces, newest first; 404 `portfolio.discipline_not_found`), `GET /pieces/{slug}` (404 `portfolio.piece_not_found`), `GET /disciplines` (those with a live piece) and `GET /art` (the settings' lead and commission link);
  - `portfolio.piece.add` or `portfolio.piece.manage`: `GET /admin/pieces?q=&discipline=&cursor=` (every piece for `manage`, else yours; `no_artist` for `manage`), `POST /admin/pieces`, `GET`, `PATCH` and `DELETE /admin/pieces/{id}`, `POST /admin/pieces/{id}/publish` (`{at?}`) and `/unpublish`, and `GET /admin/disciplines`;
  - `portfolio.piece.manage`: `GET /admin/artists`;
  - refusals: 403 `kernel.forbidden`; 409 `portfolio.changed` (with the piece now) and `portfolio.slug_taken`; 422 `portfolio.unknown_discipline`, `image_not_found`, `not_youtube`, `not_an_artist` and `bad_year`.
- **Table:** `portfolio_piece` (migration `portfolio_0001`, branch `portfolio`). The discipline is the kernel's `kernel_term_link`.
- **Web:** `/admin/portfolio` (Portfolio, under the sidebar's Collective), a piece in its editor at `/admin/portfolio/<id>` (`/new` for a new one), the Art page at `/art`, `/art/:discipline` and `/art/piece/:slug`, Art in the site's header, and the Settings section "Art page".
- **Hooks:** lifecycle and search (`portfolio.piece`), taxonomy (`portfolio_discipline`), item references (`refs.py`, `portfolio.piece`, "Pieces"), server copy (each page's words, a `VisualArtwork` for a piece, a `CollectionPage` for a list, the sitemap), export and erase (the pieces credited to a person; erase keeps them, uncredited), and the seed (the four disciplines, and three live pieces and a draft while storage is on).
- **Events:** emits `portfolio.piece.deleted` (v1 `{id}`); listens to nothing.
- **Permissions:** `portfolio.piece.add`, `portfolio.piece.manage`.

## Settings and env vars

- `pieces_per_page` (int, default `24`, 6 to 60): pieces on each page of the Art page.
- `lead` (string, default empty): the line under the Art page's title.
- `commission_link` (string, default empty): where "Commission work like this" goes, a path on the site such as `/contact` or an https address; empty hides it.

They're saved on Settings under `kernel.settings.manage`, as every module's are. No env vars: pictures are media's, and a video's player is embeds'.

## Install notes

`mechframe add portfolio` (it needs `media` and `embeds`). The migration makes no discipline: add them on the Portfolio page, or in the site's seed. A site's artist role takes `portfolio.piece.add` and `media.image.upload` (to add a picture), never `portfolio.piece.manage`.

## Extension points

- Backend `public.py`: `async def piece_cards(db, ids) -> list[PieceCard]` (live ones, in the order given) and `async def pieces_by(db, artist_id, *, limit=24) -> list[PieceCard]`, for roster's profile and a shop's listing.
- Web `public.ts`: `PieceCard`, `usePieces({ discipline })`, `usePiece(slug)`, `useDisciplines()`, `pathOf`, `lineOf`, `bylineOf`, and the types `PieceCardData`, `PieceCards`, `LivePiece`, `Discipline` and `PiecePicture`.
- `refs.py` gives `portfolio.piece` to any module that points at things through `kernel.refs`, such as `featured`.

## Known limits

- One picture per piece. Video is a YouTube link only, until VM Website's uploads (stage C); embeds' player sits under the picture, since its facade takes no poster.
- "For sale in the Marketplace" waits for `shop`.
- A piece's address changed while it's live leaves the old one a 404: there are no moves yet.
- Pieces are listed newest first; there's no order of staff's own.

## Source and license

New code for MechFrame, proprietary (decision 0008).
