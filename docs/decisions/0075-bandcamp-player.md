# 0075: Bandcamp's own player, a track's else its album's, behind a page's own Listen

- **Date:** 2026-11-28
- **Status:** Decided. The owner approved `dev plans/contracts/bandcamp-player.md` on 2026-11-28 as recommended ("Approve as recommended", its three answers). Applied with discography 0.1.5 and embeds 0.1.2.
- **Context:**
  - VM Website's ask B (`C:\DEV\VM Website\dev plans\2026-11-28-ask-b-bandcamp-player.md`): the owner's order for a track's sound is its uploaded file, else its SoundCloud link, else Bandcamp's own player in place of the site's controls, else "This track can't play right now" (VM Website's `contracts/player-sources.md` §8, 3, approved 2026-11-27). Players' links are entered on the track or album in Music (§8, 4).
  - Bandcamp has no API to drive from the site's buttons, and no way to look a link up: its player needs the id in its embed code. embeds 0.1.1 already read that code in the web's editor (`fromBandcampCode`) and drew Bandcamp's frame behind its own facade.
  - Bandcamp's frame can't be paused from outside, and it never says when its track ends.
- **Decision:**
  1. **discography keeps a Bandcamp player per track and per album** (`discography_0002`): the page's link with the player's id in its fragment, read on the server from the embed code an admin pasted, through embeds' new `from_bandcamp_code`. Only the link is kept; anything else is a field error, `discography.not_bandcamp`.
  2. **The source order** is the upload, then SoundCloud, then the track's own Bandcamp player, then its album's. `plays_from` takes the release. A track that plays from Bandcamp is live everywhere one from SoundCloud is, and every read that names a SoundCloud link names its Bandcamp player beside it.
  3. **audio-player doesn't play it** (§8, 1): `playerItem` is null for it and `playerQueue` goes on without it, so an album plays on past it. The track plays in Bandcamp's player from its own row and its own page.
  4. **Taking turns** (§8, 2): a page's Listen claims its turn through audio-player's `useExclusive`, which pauses audio-player, and audio-player starting puts the frame back to Listen. Unmounting the frame stops it. audio-player 0.1.2 is unchanged.
  5. **A track with no player of its own plays in its album's** (§8, 3), as the owner's order says, though Bandcamp's frame then starts at the album's first or featured track.
  6. **embeds gives a page the frame alone,** `EmbedFrame`, with `Embed`'s sandbox, title and shapes, drawing nothing until `media` is granted, so the page's own Listen is the facade and grants it.
- **Alternatives:**
  - audio-player stopping on a Bandcamp track and showing its player in the dock (VM Website's suggestion). Rejected (§8, 1): with no word from the frame when its track ends, an album would stop there every time, and it needed audio-player 0.1.3 in a third module.
  - audio-player owning the frame's turn. Rejected (§8, 2): it would need audio-player to know embeds, and `useExclusive` already does it.
  - Only a track's own player making it live. Rejected (§8, 3): the owner's order falls back to the album's.
  - The web reading the code and sending the link. Rejected: the server reads what was pasted, so every client gets the same field error, and the two readings are held to one set of cases.
  - A facade slot on `Embed`. Rejected: the boards' Listen sits in place of a player's controls, with no figure or caption.
- **Consequences:**
  - discography 0.1.5 requires embeds `^0.1.2`. Its `playerItem` now returns `PlayerItem | null`, so a site's code that maps tracks to items (a homepage's Spotlight) is told by its type checker to leave Bandcamp's out: `flatMap((each) => playerItem(each, each.release) ?? [])`.
  - No Bandcamp listen is counted: its frame says nothing back.
  - VM Website wires its boards' Bandcamp states (`bcAsk`, `bcFrame`, `bcListen`, held shut by `NO_BANDCAMP`) to `bandcampPlayer(track)`, `EmbedFrame` and `useConsent("media")`, and measures them against the boards at 1440 and 390.
