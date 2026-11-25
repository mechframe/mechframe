# 0073: featured, the homepage's players as slots staff fill, live worked out at each read

- **Date:** 2026-11-25
- **Status:** Decided. The owner approved `dev plans/contracts/featured.md` on 2026-11-25 as recommended ("Approve as recommended", its eight answers). Applied with featured 0.1.0, after hook 11 (decision 0072, #153) and before discography 0.1.2.
- **Context:**
  - Vibrant Mindz's homepage has three players (the Spotlight's tracks, the Releases deck's albums, the Videos player's YouTube links), which staff choose and schedule without a deploy (`docs/plans/vibrant-mindz-backend/players-admin.md`, VM Website's `AdminPlayers.dc.html`).
  - featured has to point at discography's things without requiring it (decision 0072), take YouTube's links, and leave how a page draws a player to the site.
- **Decision:**
  1. **A slot is a named list.** Its `key` is what the site's code reads, its `label` its tab, `accepts` the types of `kernel.refs` it takes or `"youtube"`, `kinds` a link's kinds, and `on_dashboard` whether the Dashboard shows it. An admin makes slots on Players (`featured.slot.manage`); a site's own seed makes them for a demo.
  2. **A placement is an item `{type, id}` or a YouTube link,** each with an optional start and end, in its list's order. No foreign key reaches another module.
  3. **What's live is worked out at each read,** with no job:
     - live while `starts_at <= now < ends_at`, an open end counting as always;
     - an item only while its source says `live`, and a gone one never;
     - a placement whose module is off is left out, and shows `hidden` on Players;
     - every live thing plays, in order. The board's "Queued" isn't used.
  4. **A save is the whole list,** checked against the `version` it read under the slot's row lock, so two saves at once make one version and the other answers 409 `featured.changed` with the slot as it is now. A kept placement whose module is off stays as it is; one whose item is gone is left out.
  5. **YouTube's links are read by embeds** (`embeds.public.recognise`, so featured requires `embeds ^0.1`) and kept as the video's watch address, built from its id. Titles come from YouTube's oEmbed, asked about that address alone, all at once and each given a second, while the setting `oembed_titles` is on.
  6. **The public read,** `GET /api/featured/slots/{key}` and `featured.public.live`, answers what's live now with `Cache-Control: public, max-age=60`. The web's `useFeatured(key)` reads it.
  7. **The Dashboard** warns two days before an `on_dashboard` slot goes empty (something live, all of it ending by then, nothing scheduled), asks in setup for something live in each player, and shows each such slot's card.
- **Alternatives:**
  - A job that announces each start and end, as the scaffold had. Rejected: the read already knows the time, and a minute's cache is soon enough for a release day.
  - Only the first live item playing, the rest queued behind it. Rejected (the owner's §8, 3): the Spotlight's previous and next move through every live track.
  - Slots the site declares in its own code. Rejected (§8, 2): a new kind of site file the kernel would read.
  - A poster, length and date for each video. Rejected (§8, 5): YouTube's thumbnail is the poster on the site.
- **Consequences:**
  - featured 0.1.0's tables are `featured_slot` and `featured_placement` (`featured_0001`, depending on `kernel_0002`). Admins and editors hold `featured.placement.manage`, admins `featured.slot.manage`.
  - The harness's probe notes give `probe.note` (hook 11), and its test support has a fake YouTube (`harness.fake_youtube`), so no test asks YouTube. Its `/featured.html` draws a slot through `useFeatured`.
  - The kit's `SaveBar` gains `what`, the words after its count, for the board's "2 changes not saved: Hook It Up added, Gather Around scheduled" (the main lane's OK, 2026-11-25).
  - discography 0.1.2 gives `discography.track` and `discography.release`, which is when Vibrant Mindz's three players can be made.
