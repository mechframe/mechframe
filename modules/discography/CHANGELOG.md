# Changelog: discography

## 0.1.2

- `refs.py` (hook 11, decision 0072; `dev plans/contracts/featured.md` §2, "discography 0.1.2"): `discography.release` ("Albums") and `discography.track` ("Tracks"), drafts too, each `live` while the site plays it, with its line and its release's cover; picked by title, newest edit first, a page at a time. featured's players can hold them now.
- Reads by id for a homepage: `GET /api/discography/releases?ids=` and `GET /api/discography/tracks?ids=` (50 at most, the live ones in the order given), with `useReleases({ ids })` and `useTracks(ids)` in `@/modules/discography/public`.
- The admin drawn nearer its boards (VM Website's parity ask, its `dev plans/2026-11-25-admin-music-parity.md`): the Credits and When groups labelled as fields are, with no outline (D1); a credit's role as wide as its words (D2); 20 px under a page's note (D3); a release's track rows and covers whole at 390 (D4); a track that can't play is a red note everywhere and Credits' note amber (K2); a track that plays is "Live" and "Tracklist to come" amber (K3); Tracks' and Credits' tables in a card (K6); Tracks' panel 340 px and Credits' Roles 280 px (K8).

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
