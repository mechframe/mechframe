---
feature: The portfolio module, the site's visual work by discipline: pieces with a picture, who made them, their year and a few words, optionally a YouTube video; the public Art page, a page per piece, and Admin › Collective › Portfolio, where an artist adds and edits their own pieces and staff edit all of them (Vibrant Mindz step 3; the side lane's M14)
status: approved
approved: 2026-11-28 (the owner: "Approve as recommended", the eight answers in §8 as recommended)
plan: `docs/plans/vibrant-mindz-module-plan.md` §2 (its row) and `docs/plans/vibrant-mindz-backend/backend-plan.md` (§6, the artist role); VM Website's boards `design/site/AdminPortfolio.dc.html` (Portfolio) and `Art.dc.html` (the Art page); the scaffold `modules/_portfolio/` (2026-11-15)
pr: one, portfolio 0.1.0, its number read from GitHub just before the push; decision 0074; migration `portfolio_0001`
---

# Contract: `portfolio`

## 1. Goal

The collective's visual work goes on the site without a deploy. Paintings, graphic design, animation and video are each a piece: a picture, who made it, its year and a few words, and for a video, its YouTube link. The Art page shows them by discipline and opens each one bigger. Each piece has its own address, which a visitor can share and which search engines and AI crawlers read. An artist adds and edits their own pieces. Staff edit every piece and credit each one to its artist.

## 2. Interfaces

### portfolio 0.1.0 (requires the kernel, `media ^0.1` and `embeds ^0.1`; decision 0074)

**A piece** (content type `portfolio.piece`, "Piece") has these fields:
- `title`, 1 to 200 characters;
- `slug`: its address, made from the title and editable (120 at most, unique). It's lowercase letters and digits joined by single hyphens, blog's and discography's rule, held by a CHECK;
- its **discipline**: exactly one term of the vocabulary `portfolio_discipline` ("Disciplines", not hierarchical), set through `taxonomy.tag` (hook 2);
- `artist_id`: the account it's credited to, or none (§8, 3). That account is also the one that may edit it as its own;
- `year`, from 1000 to next year, or none;
- `about`: plain text, up to 2,000 characters, its line breaks kept;
- `image_id`: its picture, a media image (required);
- `video_url`: a YouTube video, or none (§8, 1). It's kept as `https://www.youtube.com/watch?v=<id>`, with its `video_id`;
- the kernel's lifecycle (hook 1): draft, scheduled or published, plus `version`.

**Permissions** (§8, 2):
- `portfolio.piece.add`: "Add pieces, and edit and delete the ones credited to you" (admin, editor). A site gives it to its artist role.
- `portfolio.piece.manage`: "Edit and delete every piece, and credit it to anyone who may add pieces" (admin, editor).
- The Art page's settings are saved under the kernel's `kernel.settings.manage`, as every module's are: portfolio declares no settings permission (as built; the approved draft named `portfolio.settings.manage`).

**Who may change a piece** (as built): staff holding `manage` change every piece; someone holding `add` changes only a piece credited to them, while they hold it. The routes read both through `require_owner_or` (`router.who`), and the service checks them on the locked row (`service.may_change`). The approved draft said `require_owner_or("portfolio.piece.manage")` then `check(piece.artist_id)`, which passes the owner whatever they now hold.

**HTTP** (`/api/portfolio`, behind `require_module("portfolio")`).

**Public reads:**
- `GET /pieces?discipline=&cursor=&limit=` → `{items: [PieceCard], next_cursor}`, the live pieces, newest first (by `published_at`, then id). `limit` is 1 to 60, the settings' `pieces_per_page` when it's left out.
  - A discipline that isn't one answers 404 `portfolio.discipline_not_found`.
  - `PieceCard` is `{id, slug, title, discipline: {slug, label} | null, artist: str | null, year, picture: Picture | null, has_video: bool, path}`; `picture` is null only when the library lost the image.
  - `artist` is the account's display name, never its address, and null without one.
  - `Picture` is media's `Picture`: `{id, url, srcset, width, height, alt, decorative}`.
- `GET /pieces/{slug}` → `Piece`, which is `PieceCard` plus `about` and `video: {url, video_id} | null`. A draft or a slug with no piece answers 404 `portfolio.piece_not_found`.
- `GET /disciplines` → `{items: [{slug, label}]}`: the disciplines that have a live piece, in the vocabulary's order.

**Admin routes** (behind the admin gate):
- `GET /admin/pieces?discipline=&q=&cursor=&limit=` (`add` or `manage`) → `{items: [AdminPiece], next_cursor, no_artist}`, newest edit first. `limit` is 1 to 100, 50 when it's left out.
  - With `manage`, every piece. Without it, the pieces credited to you, and `no_artist` is null.
  - `no_artist` counts the pieces with no artist, for the page's note.
- `GET /admin/pieces/{id}` (owner or `manage`) → `AdminPiece`.
  - `AdminPiece` is `{id, slug, title, discipline | null, artist: {id, name} | null, year, about, image_id, picture | null, video, status, publish_at, published_at, version, updated_at, path}`.
  - `path` is null while the piece isn't live.
- `POST /admin/pieces` (`add`) takes `NewPiece {title, discipline, image_id, slug?, artist_id?, year?, about?, video_url?}` → 201 `AdminPiece`, a draft.
  - Without `manage`, the piece is credited to you, and an `artist_id` naming someone else is 403 `kernel.forbidden`.
- `PATCH /admin/pieces/{id}` (owner or `manage`) takes `{version, ...any of NewPiece's fields}` → `AdminPiece`. Changing `artist_id` needs `manage`.
- `POST /admin/pieces/{id}/publish` `{at?}` puts it live now, or schedules it for `at`. `POST /admin/pieces/{id}/unpublish` makes it a draft again. Both are open to the owner or `manage`, and both answer `AdminPiece`, as discography's releases do.
- `DELETE /admin/pieces/{id}` (owner or `manage`) → 204.
- `GET /admin/artists` (`manage`) → `{items: [{id, name}]}`: every active account that may add pieces (an owner, or a role holding `portfolio.piece.add`). This is blog's `authors`, copied.

**Refusals:**
- 409:
  - `portfolio.changed`, with the piece as it is now;
  - `portfolio.slug_taken`.
- 422:
  - `portfolio.unknown_discipline`;
  - `portfolio.image_not_found` (media hasn't got it);
  - `portfolio.not_youtube` (embeds' `recognise` reads no YouTube video);
  - `portfolio.not_an_artist` (an account that can't add pieces);
  - `portfolio.bad_year`;
  - the schema's own, for lengths.

**What a save does besides:**
- records the picture's place with `media.use(image_id, owner="portfolio.piece:<id>", label=title, link="/admin/portfolio?piece=<id>")`, and `media.release`s the old picture or, on a delete, every picture;
- indexes the piece for search: hook 3's `search.py`, with its title, about, artist and discipline;
- audits each action as `portfolio.piece.created`, `.changed` (the fields' names), `.published`, `.scheduled`, `.unpublished` and `.deleted`. Each holds the piece's id, never its words: a title may hold an `@` the audit refuses as an address (featured's lesson).

**Backend, `portfolio.public`** (for a site's own code, and for modules listing `portfolio` in `requires`, roster first):

```python
async def piece_cards(db: AsyncSession, ids: Sequence[uuid.UUID]) -> list[PieceCard]   # the live ones, in the order given
async def pieces_by(db: AsyncSession, artist_id: uuid.UUID, *, limit: int = 24) -> list[PieceCard]   # live, newest first
```

**Item references (hook 11), `refs.py`:**
- one type, `portfolio.piece` ("Pieces");
- its line is "Graphic design, by petro, 2026", leaving out what it hasn't got;
- its picture's smallest copy is the `image`;
- `path` is `/art/piece/<slug>` while it's live, and `live` means published;
- `pick` finds pieces by title, drafts too, newest edit first.

With this, `featured` can feature art and roster can point at pieces, and neither imports portfolio.

**Server copy (SPEC 9):**
- `/art`, `/art/<discipline>` and `/art/piece/<slug>` each have their head and words.
- Each piece is a `VisualArtwork`: `name`, `image`, `artform` (its discipline), `creator` (a `Person`, by name), `dateCreated` (its year), `description` and `url`.
- A list is a `CollectionPage` with an `ItemList`.
- The sitemap holds `/art`, each discipline with a live piece, and each live piece.

**Settings** (a section "Art" on the admin Settings page, `admin.settings.section`, under `portfolio.settings.manage`):
- `pieces_per_page` (int, 24, from 6 to 60);
- `lead` (str, "", 300 at most): the line under the Art page's title;
- `commission_link` (str, ""): a path on the site, such as `/contact`, or an https address. Empty hides "Commission work like this".

**Hooks:**
- lifecycle, taxonomy, search, refs, server copy;
- export and erase (hook 7, blog's): an export lists the pieces credited to the person; an erase keeps the pieces and removes the credit;
- the seed makes the four disciplines: Paintings, Graphic design, Animation, Video.
- No Dashboard card and no job.

**Events:**
- It emits `portfolio.piece.deleted` (v1 `{id}`). Publishing is the kernel's `kernel.content.published`.
- It listens to nothing: the scaffold's `auth.user.deleted` goes, since the foreign key and hook 7 cover a deleted account.

**Web:**
- **`/admin/portfolio`** (`portfolio.piece.add`) is "Portfolio" in the sidebar's Collective section (icon `people`), drawn as the board.
  - **The title and lead:** "Portfolio", then the disciplines' labels joined ("Paintings, graphic design, animation and video.") and "Everything live here shows on the Art page." Then "Add a piece", which opens media's `ImagePicker`; the picture chosen starts a draft in the editor.
  - **The note** (`manage` only, while `no_artist` > 0):
    - its title is "No piece has an artist yet", or "{n} pieces have no artist";
    - its words are "The Art page names no artist on them until each is credited.";
    - its button is "Credit the first", which opens that piece.
  - **The chips:** "All" and each discipline, in the vocabulary's order. "Disciplines" opens a dialog to add, rename and delete them, as blog's categories (`kernel.taxonomy.manage`).
  - **The tiles:** the picture, the title, the discipline, and a pill: "No artist", "Draft" or "Scheduled". A live piece with an artist has no pill.
  - **The editor** (320 px beside the grid; below it at 390):
    - the picture, with "Change picture";
    - the fields Title, Discipline, By, Year, About the piece, Video (a YouTube link) and Address;
    - By is a menu of `GET /admin/artists` for `manage`, and your own name, fixed, for anyone else;
    - Save, Publish or Unpublish (with "Schedule"), "View on the site" while it's live, and Delete;
    - the kit's SaveConflict and its unsaved-changes guard.
  - **What the board draws that waits:** "For sale in the Marketplace" waits for `shop` (§6).
- **`/art`, `/art/:discipline` and `/art/piece/:slug`** are drawn as the Art board.
  - **The top:** the title "Art" and the setting's `lead`.
  - **The chips:** "All" and each discipline of `GET /disciplines`. Each chip is a link to `/art/<slug>`, with `aria-current`.
  - **The grid:** the picture, the title, and "{discipline}, by {artist}" (no "by" without an artist), with "Load more".
  - **A piece's address opens the board's panel above the grid** (§8, 5):
    - the big picture; for a video, embeds' player behind its consent facade, the piece's picture its poster;
    - the discipline, the title, "By {artist}, {year}" and the about;
    - "Commission work like this", while the setting has a link;
    - Close, which goes back to the list it came from, or `/art`.
  - **Focus** moves into the panel when it opens, and back to the piece's tile on Close.
  - **Nothing live:** "Nothing here yet."
- **`@/modules/portfolio/public`:** `PieceCard` and its type, for roster's profile.

## 3. Data

Branch `portfolio`, migration `portfolio_0001`. Its `depends_on` is `kernel_0014` and `media_0001`, as blog's and discography's are.

| Table | Column | Type | Null | Default / FK / index |
|---|---|---|---|---|
| `portfolio_piece` | `id` | uuid | no | PK |
| | `slug` | varchar(120) | no | unique; CHECK the slug rule |
| | `title` | varchar(200) | no | |
| | `artist_id` | uuid | yes | FK `auth_user.id` ON DELETE SET NULL; index |
| | `year` | smallint | yes | CHECK `year >= 1000` |
| | `about` | text | no | `''` |
| | `image_id` | uuid | no | media's image, no FK (SPEC 10) |
| | `video_url` | varchar(500) | yes | CHECK: both video columns or neither |
| | `video_id` | char(11) | yes | |
| | `status`, `publish_at`, `published_at` | lifecycle's | | `*lifecycle.columns()`, `*lifecycle.table_args("portfolio_piece")` |
| | `version` | int | no | 1 |
| | `created_at`, `updated_at` | timestamptz | no | now; index (`status`, `published_at` desc) |

- **The discipline** is the kernel's `kernel_term_link`, not a column.
- **The scaffold's** `owner_user_id`, `discipline`, `description`, `shop_product_id` and its table `portfolio_image` go (§8, 4).
- **Export and erase are true:** a piece names the account it's credited to.

## 4. Files

- **`modules/_portfolio/` becomes `modules/portfolio/`** (`git mv`), its `module.json`, `MODULE.md` and `CHANGELOG.md` saying what's agreed here:
  - `backend/portfolio/`: `__init__` (`CSP` empty, since embeds' covers YouTube), `models`, `schemas`, `service`, `router`, `public`, `refs`, `search`, `lifecycle`, `server_copy`, `privacy`, `seed`, `events`. The scaffold's `jobs.py` goes.
  - `migrations/portfolio_0001_portfolio.py`.
  - `web/`: `module.web.ts`, `api.ts`, `public.ts`, `pages/PortfolioAdmin.tsx`, `pages/Art.tsx` (the scaffold's `Public.tsx`), `components/` (the tile, the editor, the Disciplines dialog, the panel, `PieceCard`), `settings/ArtSettings.tsx`, `portfolio.css`.
  - `tests/`: `backend`, `contract`, `web` and `e2e`.
- **Generated again,** each by its own tool (`docs/COMMANDS.md`): `openapi.json` by `python -m tools.openapi`, then `schema.ts` by `npm run api:types` once `package.json`'s `api:*` lines name portfolio; `catalog.json` by `mechframe catalog`; `docs/HOST-VARIABLES.md` by `python -m tools.host_variables`; the event's schema by `python -m tools.event_schemas`; and `docs/PROGRESS.md` and the ledger's rows by `python -m tools.progress`, from `docs/progress.json`, which is edited by hand.
- **The decision:** `docs/decisions/0074-portfolio.md`.
- **Elsewhere:** a row in `dev plans/README.md`. SPEC doesn't change.
- **Not mine:** VM Website's `site-additions/backend/app/site/seed.py` gives the artist role its permissions (§8, 2). Its session changes it.

## 5. Conventions this follows

- SPEC 6 to 10 and 14.8.
- The skills `mechframe-module-extractor`, `alembic-multi-module-migrations` and `module-contract-lint`.
- blog's patterns: its authors (`service.authors`, `GET /admin/authors`), its categories (taxonomy, `Categories.tsx`) and its privacy hook.
- discography's: its covers (`ImagePicker`, `media.use` and `release`), publish and unpublish, `refs.py` and its admin boards' build.
- featured's: a YouTube link kept as its watch address, and an audit that holds no words.
- The memories `new-module-hidden-tests`, `react-render-time-sync-traps` and `worktree-playwright-config`.

## 6. Non-goals

- **Uploaded video and animation files.** These wait for VM Website's stage C. Until then a video is a YouTube link (§8, 1).
- **"For sale in the Marketplace":** a piece's link to a product waits for `shop`, which will give `shop.product` through refs.
- **A member's profile tab** ("No art from J Tone yet."): roster's. portfolio gives `pieces_by` and `PieceCard`.
- **More than one picture per piece** (§8, 4), and a zoom, lightbox or slideshow.
- **Ordering pieces by hand,** pinning them, or collections other than disciplines.
- **Comments, reactions and sharing to social** (`content.share`) on a piece: later, once those modules say what they attach to.
- **Vimeo or other video hosts:** embeds would need them first.
- **Prices, sales or commissions taken** on the site: "Commission work like this" is only a link.

## 7. Acceptance

- **Backend (pytest):**
  - each field's limits and each 409 and 422;
  - the guard: an artist (holding `add` only) adds a piece credited to themself, edits and deletes their own, and gets 403 on another's and on crediting someone else; an editor holding `manage` edits every piece;
  - lifecycle: a draft is 404 in public, a scheduled piece goes live at its time, unpublish;
  - one discipline per piece through taxonomy, and a deleted discipline leaving the piece under All only;
  - media's `use` and `release` on save, change and delete;
  - the YouTube link read by embeds, and anything else refused;
  - `refs` (its line and `live`), `search`, `server_copy` (each page's words, the JSON-LD and the sitemap), export and erase;
  - two saves of one piece at once making one version, a real race checked with a mutant.
- **HTTP:** each route's access; the public reads hold no draft and no address.
- **Web (Vitest):**
  - the admin: chips, tiles and pills, the note, the editor's By for `manage` and for an artist, publish, delete, the Disciplines dialog, the conflict;
  - the Art page: the chips as links, the grid, the panel's focus and Close, the commission link shown only when set, the video's consent facade;
  - the settings section.
- **E2E** (from the main checkout, the other lane told before and after):
  - Portfolio and the Art page in both themes at 1440 and 390, axe clean;
  - a piece added, published and opened at its address;
  - nothing loads from YouTube before a visitor plays the video.
- **Gates:** `module-contract-lint`, then on a fresh site `mechframe add` media, embeds and portfolio, and `mechframe check`.

## 8. Open questions for the owner

1. **What video is, for now.**
   - *Recommended:* any piece may have a YouTube link, read by embeds. Its page plays it behind embeds' consent facade, and the piece's own picture is the poster. Nothing loads from YouTube until a visitor plays it, and the grid always shows the site's own picture.
   - *The other ways:*
     - Animation and Video pieces are pictures only until stage C's uploads.
     - Vimeo too: embeds gets a Vimeo player first (embeds 0.1.2, its own PR).
2. **What an artist may edit.**
   - *Recommended:* the two permissions above. `require_owner_or` lets through anyone holding the permission it names. So an artist given `portfolio.piece.manage`, as VM Website's planned seed does, could edit every piece. Instead the artist role takes `portfolio.piece.add`, plus `media.image.upload` to add a picture. VM Website's session changes its seed.
   - Roster's `roster.profile.manage` and licensing's `licensing.work.manage` are in the same seed with the same trap. I'd tell the main lane for roster's contract.
   - *The other way:* one permission, and artists may edit every piece.
3. **Who a piece is "By".**
   - *Recommended:* an account, as blog's authors are: chosen from the accounts that may add pieces, and shown by display name. When roster comes, a member's profile lists the pieces credited to the member's account.
   - *The other ways:*
     - a typed name, for a guest artist with no account, which gives no right to edit;
     - an account or a typed name, as staff choose.
4. **One picture or several.**
   - *Recommended:* one, as both boards draw.
   - *The other way:* up to 12 in order: the first in the grid, the rest a strip under the big one on the piece's view (the scaffold's `portfolio_image`).
5. **A piece's own address.**
   - *Recommended:* `/art/piece/<slug>` is the Art page with the board's panel open above the grid. A piece can then be shared, and crawlers read it.
   - *The other way:* the panel only, as drawn, with no address per piece. Crawlers would then see only `/art` and the disciplines.
6. **Disciplines.**
   - *Recommended:* the kernel's taxonomy, edited on Portfolio as blog's categories are. The seed makes the four. The Art page's chips show only the disciplines with something live, in one order for both pages. Today the boards' orders differ: Paintings first in the admin, Graphic design first on the Art page.
   - *The other way:* the four built into the module.
7. **Smaller calls, each as recommended unless you say:**
   - the Art page lists pieces newest first;
   - a new piece is a draft until Publish, as releases are. The board's Save only saves, and its lead says "Everything live here";
   - added beyond the boards: the Video and Address fields, Publish and Schedule, Delete, the pills Draft and Scheduled, the Disciplines dialog, Load more, and the Settings section (the lead and the commission link). "Commission work like this" shows only when a link is set.
8. **The order of work.** *Recommended:* one PR, portfolio 0.1.0. Then VM Website's seed change (2), sent to its session.

## Changes after approval

None.

## Changes as built (portfolio 0.1.0, `claude/mechframe-side-lane-portfolio-5d6e12`)

None changes what was approved; each says what §2 meant, or adds what a screen needed.

- **The settings are saved under `kernel.settings.manage`,** as every module's are (the kernel's Settings page saves each section), so `portfolio.settings.manage` would have done nothing: portfolio declares only `add` and `manage`.
- **An artist's own pieces are theirs only while they hold `add`.** Each piece route asks which of the two the person holds (`router.who`); someone whose artist role is taken away keeps no hold on the pieces still credited to them. A route answers 403 to someone holding neither. The admin page, its sidebar link and a new piece need `add`.
- **The Art page reads its lead and commission link** through a public `GET /api/portfolio/art` (`ArtPage {lead, commission_link}`), since the kernel's settings read is the admin's, as contact's page reads its intro through its own route.
- **`GET /admin/disciplines`** (`add` or `manage`) answers each discipline with its id, position and pieces, drafts included, for the admin's chips and the Disciplines dialog, as blog's `GET /admin/categories` does.
- **The answers:**
  - a card's video flag is `has_video`, since `LivePiece`'s `video` is the link itself;
  - `picture` is null only when the library lost the image; `AdminPiece` holds `image_id` too;
  - `GET /pieces` takes `limit` (1 to 60), the settings' `pieces_per_page` when it's left out.
- **The video** plays in embeds' own player under the picture: embeds' facade takes no poster, so the picture stands above it rather than behind it. Nothing loads from YouTube until a visitor plays it, as approved.
- **A discipline can't be named "piece"** in the dialog: its address would be `/art/piece`, beside the pieces' own.
- **A live piece's address changed** leaves its old one a 404: portfolio keeps no moves of the kind blog keeps (Known limits).
- **The audit** records `portfolio.piece.changed` with the names of the fields changed, and `portfolio.piece.deleted` with the slug, never a title.
- **The seed** makes the four disciplines as the seeded editor (a seed never makes an owner), and its pieces only while media's storage is on.
- **The e2e spec stands in the pieces' reads** at the browser: the e2e server runs with storage off, so media can't give any picture an address, and a piece can't be added there. The disciplines (added through the dialog) and the Art page's settings are the server's own. Adding, publishing and opening a piece at its address are the HTTP contract suite's, with real pictures in a fake S3.
- **A piece in the editor has its own address,** `/admin/portfolio/<id>` (`/new` for a new one), with the discipline filter in the query (`?discipline=`): the kit's unsaved-changes guard asks only on a move to another path, so a `?piece=` query let another piece replace unsaved edits (Codex on #171). Its picture's use in the media library links there.
- **Publish and Unpublish keep what's typed and not yet saved,** still unsaved: the answer is taken in against the piece as saved before it, not the form as it stands (Codex on #171).
- **cubic on #171**, each with a test seen failing first where it's a behaviour:
  - a piece credited to a manager who can't add pieces is refused, as any other credit is (`portfolio.not_an_artist`);
  - a piece's `video_id` is 11 of YouTube's letters, a CHECK beside the contract's `char(11)`, so the table holds no shorter id;
  - a scheduled piece has "Back to a draft"; a new piece's Publish moves the page on only once it's live; a save's conflict counts every field it sent as the person's;
  - every `VisualArtwork` has a description (the line when there are no words), and a description with no space in it is cut where it is;
  - each discipline's sitemap date is its own newest piece; the disciplines' counts and a reindex's documents are read in a few queries, not one a discipline or a piece;
  - only the slug's own constraint is a 409 `portfolio.slug_taken`; any other failure of a save goes up as it is;
  - the Art page says when its disciplines or its words couldn't be read, with Try again; the Disciplines dialog says a rename's or a delete's failure beside its row;
  - the panel's heading keeps the site's focus outline;
  - the e2e spec adds a piece through Add a piece and publishes it, with media's library and the piece's writes stood in.
