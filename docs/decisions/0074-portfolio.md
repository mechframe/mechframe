# 0074: portfolio, pieces by discipline, and an artist's own work under two permissions

- **Date:** 2026-11-28
- **Status:** Decided. The owner approved `dev plans/contracts/portfolio.md` on 2026-11-28 as recommended ("Approve as recommended", its eight answers). Applied with portfolio 0.1.0.
- **Context:**
  - Vibrant Mindz shows the collective's paintings, graphic design, animation and video (the module plan's row, `docs/plans/vibrant-mindz-module-plan.md` §2; VM Website's `AdminPortfolio.dc.html` and `Art.dc.html`). It's new code, with no source to lift.
  - The site's artist role is to edit its members' own work (`docs/plans/vibrant-mindz-backend/backend-plan.md` §6). portfolio is the first module to use `require_owner_or`, and `OwnerOr.check` lets through the owner or any staff member whose role holds the permission it names. VM Website's planned seed gives the artist role `portfolio.piece.manage`, which would open every piece to every artist.
  - Uploaded video is VM Website's stage C, not built.
- **Decision:**
  1. **Two permissions.** `portfolio.piece.add` adds pieces, credited to whoever adds them, and changes and deletes the ones credited to them; `portfolio.piece.manage` changes every piece and credits it to anyone who may add pieces, or to no one. Admins and editors hold both; a site's artist role holds `add` (with `media.image.upload` for a picture), never `manage`. An artist's own pieces are theirs only while they still hold `add`: one whose role is taken away keeps no hold on them.
  2. **A piece is credited to an account** (blog's authors): `artist_id`, a foreign key to `auth_user` that a deleted account sets to none, chosen among the accounts that may add pieces, and shown to the public by display name, never by address. Roster lists a member's pieces by that account (`public.py`'s `pieces_by`).
  3. **One picture per piece,** media's image, required, its place recorded with `media.use`.
  4. **Video is a YouTube link for now,** read by embeds (`embeds.public.recognise`, so portfolio requires `embeds ^0.1`) and kept as its watch address. Its page plays it in embeds' player behind the consent facade; nothing loads from YouTube until a visitor plays it.
  5. **Disciplines are the kernel's taxonomy,** `portfolio_discipline`, one per piece, edited as blog's categories are; the seed makes Paintings, Graphic design, Animation and Video. The Art page's chips show those with something live, in staff's order, each an address.
  6. **A piece's own address,** `/art/piece/<slug>`, is the Art page with the board's panel open, so a piece can be shared and crawlers read it (`VisualArtwork`).
  7. **The kernel's lifecycle,** draft, scheduled and published, as releases and posts have it; the Art page lists live pieces newest first.
- **Alternatives:**
  - One permission, artists editing every piece. Rejected (§8, 2): it's what the planned seed would have done by accident.
  - A typed artist name, or a name or an account. Rejected for now (§8, 3): a member's profile lists pieces by account; a guest artist can come later.
  - Up to 12 pictures a piece (the scaffold's `portfolio_image`). Rejected for now (§8, 4): both boards draw one.
  - The four disciplines built into the module. Rejected (§8, 6): another site's are its own.
  - Only the panel, as drawn, with no address per piece. Rejected (§8, 5): crawlers would see only the lists.
- **Consequences:**
  - portfolio 0.1.0's table is `portfolio_piece` (`portfolio_0001`, depending on `kernel_0014` and `media_0001`). It gives `portfolio.piece` to `kernel.refs`, lifecycle and search.
  - **To follow, outside this decision's PR:** VM Website's planned seed still gives its artist role `portfolio.piece.manage`, which opens every piece to every artist. It is to give `portfolio.piece.add` and `media.image.upload` instead; VM Website's session makes that change once portfolio 0.1.0 is on `main`. Roster and licensing face the same trap (`roster.profile.manage`, `licensing.work.manage` in the same seed): their contracts are to split the permission likewise.
  - Module settings are saved under `kernel.settings.manage`, as every module's are, so portfolio declares no settings permission of its own. The Art page reads its lead and commission link through its own public `GET /api/portfolio/art`.
