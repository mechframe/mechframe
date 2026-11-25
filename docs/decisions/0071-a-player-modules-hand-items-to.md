# 0071: audio-player is a player modules hand items to, and counts plays with nothing kept that identifies anyone

- **Status:** Decided. The owner approved `dev plans/contracts/audio-player.md` on 2026-11-24 as recommended ("Approve as recommended", its six answers). Applied with audio-player 0.1.0; discography 0.1.1 takes it.
- **Context:**
  - Step 2's homepage players (`docs/plans/vibrant-mindz-backend/players-admin.md`) and the Release board's docked bar all play the site's music, and only one may play at a time, a YouTube video included.
  - The scaffold said audio-player "requires kernel only" and that "modules hand it items". The side lane's prompt assumed the other way round, audio-player reading discography's `track_cards`.
  - discography's own Release and Track pages, built to the boards, can only draw the player if they may import it (SPEC 7). The roadmap's `radio` and `podcast` will need the player too, and they shouldn't have to bring discography along.
  - The Dashboard's "Plays this week" needs a count of plays, and no cookie or consent banner should be needed for it.
- **Decision:**
  1. **The requirement runs from the source to the player.** audio-player requires only the kernel. A module that plays through it lists it in `requires`, hands it `PlayerItem`s (`web/public.ts`), and counts their plays from its own public route through `audio_player.public.count`, once it has checked the item is live and playable. It calls `forget` in the transaction that deletes an item. discography 0.1.1 is the first.
  2. **The player is one for the app:** one audio element and one hidden SoundCloud widget, made when first needed. Starting anything pauses the rest, keeping each one's place. `useExclusive` lets another kind of player, embeds' `VideoPlaylist`, take turns with it, with no change to embeds.
  3. **A page move stops it** (§8, 4): the player keeps going only while a part of the page that started it is drawn.
  4. **A play** is `count_after_seconds` (30 by default, 5 to 120) really heard, or nearly all of a shorter track. Each listener counts once per item per UTC day.
  5. **The listener** is an HMAC-SHA256 of the visitor's address, as the rate limits read it (the kernel's `client_address`, now public), and their browser's name, under a random salt made by the day's first play. The salt and the day's listeners are deleted the next day by `audio-player.prune`; daily totals are kept two years. No address, browser name or account is stored, so the module has no export or erase.
  6. **SoundCloud** plays through its widget behind the site's controls, in the consent category `media` (its two hosts in `CSP`). Pressing Play on a SoundCloud item is the visitor's consent, as an embed's Play is. The item shows "on SoundCloud", linked back, as SoundCloud's developer terms ask of a player that hides its widget. When a browser won't start a hidden widget, the widget is shown for its own Play.
- **Alternatives:**
  - *audio-player requires discography:* one PR, counting and naming tracks through `track_cards`. But discography's own pages couldn't use the player without a new kernel slot, and `radio` or `podcast` would require discography.
  - *A kit slot discography's pages draw, filled by audio-player* (as `prose.embed` is by embeds, decision 0060): no requirement either way, but the kernel would own an audio item's shape.
  - *Every 30 seconds heard counts, replays too*, as Spotify counts streams: held back only by the rate limit.
  - *A first-party cookie per listener:* steadier counts, but a cookie that needs consent.
- **Consequences:**
  - Any module with audio to play requires audio-player, and switching audio-player off falls back to that module's own `<audio>` (discography's `Plays`).
  - The kernel's public surface gains `client_address` (SPEC 6).
  - "Plays" are listens by distinct listeners per day, not streams.
  - The Dashboard's card belongs to the module whose items it names (discography's "Plays this week").
- **See:** `dev plans/contracts/audio-player.md`; `modules/audio-player/`; SPEC 6, 8 and 15; decisions 0052 (consent), 0057 (`public.ts`), 0060 and 0070.
