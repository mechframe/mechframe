# Changelog: discography

## 0.1.3

- Tracks' and Credits' tables name each row by its track or person, through the kit's `rowHeader` (#158; VM Website's K6): the name is the row's header, at 600, and the track that's open is 700, as the Tracks board draws it.
- VM Website's board check of 0.1.2 (P1 to P6): a `<p>` laid out as a row keeps no margins, so the Publish card's status line and the panel's Audio line sit where the boards put them (P1); the Music settings' switches are the kit's switch rows, touching (P2); a credit's row stacks wherever it's narrow, its role on a line of its own and its name the row's width beside its remove button, on a phone and always in Tracks' panel (P3); the panel's Save and Discard are small (P4); P5 and P6 are the row names above.
- #145's review items left for later (CodeRabbit), each with a test seen failing first, or against a mutant where the code was right:
  - a master whose upload or replace doesn't commit is deleted from the private bucket in the background once the transaction ends, unless a track names it then: a rollback, a savepoint rolled back inside a commit, and a put that stored the file and then failed all count. A commit that raised keeps it, as the server may still have taken it, its reply lost. It's best effort;
  - a reindex reads a page's tracks, credits and lyrics setting once, not once a release (`service.documents`);
  - credit, streaming-link and role rows keep their own keys as the rows before them go, and a removal puts the focus in the row that took its place, or on Add (`web/rows.ts`);
  - discography's downgrade alone, with the shared tables kept, takes its search documents, covers' uses and grants, and leaves blog's;
  - a master replaced after its job has read it never takes that job's result.

## 0.1.2

- `refs.py` (hook 11, decision 0072; `dev plans/contracts/featured.md` §2, "discography 0.1.2"): `discography.release` ("Albums") and `discography.track` ("Tracks"), drafts too, each `live` while the site plays it, with its line and its release's cover; picked by title, newest edit first, a page at a time. featured's players can hold them now.
- Reads by id for a homepage: `GET /api/discography/releases?ids=` and `GET /api/discography/tracks?ids=` (50 at most, the live ones in the order given), with `useReleases({ ids })` and `useTracks(ids)` in `@/modules/discography/public`; an empty `ids` is an empty answer, with no request (Codex on #159).
- The admin drawn nearer its boards (VM Website's parity ask, its boards' items D1 to D4, K2, K3, K6 and K8): the Credits and When groups labelled as fields are, with no outline (D1); a credit's role as wide as its words (D2); 20 px under a page's note (D3); a release's track rows and covers whole at 390 (D4); a track that can't play is a red note everywhere and Credits' note amber (K2); a track that plays is "Live" and "Tracklist to come" amber (K3); Tracks' and Credits' tables in a card (K6); Tracks' panel 340 px and Credits' Roles 280 px (K8).

## 0.1.1

- Plays through `audio-player`, which it now requires (`dev plans/contracts/audio-player.md` §2, "discography 0.1.1"; decision 0071): the Release page's Play album and each row's play, the three bars by the row that plays and the Player docked after the footer; the Track page's bar with its waveform. If the modules read says `audio-player` is off, both pages keep the browser's own player.
- `POST /api/discography/tracks/{id}/plays` (public, 60 an hour from one address) counts a live track that plays through `audio_player.public.count`, and answers 204 whether it counted or not. A tracklist's lines carry each track's `id`.
- The Dashboard's "Plays this week" (`admin.dashboard.widget`, for `discography.release.manage`), from `GET /admin/plays`: the last seven days' plays, the change on the seven before, and the track that leads.
- Deleting a track or a release forgets its plays in the same transaction. The seed gives each track it makes two weeks of daily plays, ending on the day it's run.
- `web/public.ts` gains `playerItem(track, release)` and `playerQueue(release)`.

## 0.1.0

- The music library, built to its approved contract (`dev plans/contracts/discography.md`; decision 0070; migration `discography_0001`): releases with a kind (album, EP, single), their tracks in order, credits as rows of a role and a name, streaming links from nine platforms, and front and back covers from media.
- Uploads judged by their bytes with `soundfile`; the job `discography.process_track` makes each master a constant-bitrate MP3 under an unguessable key, with its length and 1,000 peaks. A SoundCloud track or playlist plays where there's no finished stream file (an upload still being made, or one that failed, plays from the link, and a replaced upload's old stream plays until the new one is ready); a track with neither is hidden from the site and flagged in the admin.
- A release holds 100 tracks at most, as many as a save orders. Search follows the lyrics setting when it's saved. A job's last try that fails says so on the track, and a stream file it couldn't save is deleted again.
- The admin's Albums (with the Music settings), the album editor, Tracks and Credits boards; the site's `/music`, `/music/:release` and `/music/:release/:track`, an upload in the browser's own player and a SoundCloud track as a link; the server copy with `MusicAlbum`, `MusicRecording` and `ItemList` JSON-LD.
- `public.py` (`track_cards`, `release_cards`, `releases`, `release`, `track`, `path`) and `web/public.ts` for `audio-player`, `featured` and a site's own pages.
- Hooks: lifecycle, search, seed, server copy and dashboard.
