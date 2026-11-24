# Changelog: discography

## 0.1.0

- The music library, built to its approved contract (`dev plans/contracts/discography.md`; decision 0070; migration `discography_0001`): releases with a kind (album, EP, single), their tracks in order, credits as rows of a role and a name, streaming links from nine platforms, and front and back covers from media.
- Uploads judged by their bytes with `soundfile`; the job `discography.process_track` makes each master a constant-bitrate MP3 under an unguessable key, with its length and 1,000 peaks. A SoundCloud track or playlist plays where there's no finished stream file (an upload still being made, or one that failed, plays from the link, and a replaced upload's old stream plays until the new one is ready); a track with neither is hidden from the site and flagged in the admin.
- A release holds 100 tracks at most, as many as a save orders. Search follows the lyrics setting when it's saved. A job's last try that fails says so on the track, and a stream file it couldn't save is deleted again.
- The admin's Albums (with the Music settings), the album editor, Tracks and Credits boards; the site's `/music`, `/music/:release` and `/music/:release/:track`, an upload in the browser's own player and a SoundCloud track as a link; the server copy with `MusicAlbum`, `MusicRecording` and `ItemList` JSON-LD.
- `public.py` (`track_cards`, `release_cards`, `releases`, `release`, `track`, `path`) and `web/public.ts` for `audio-player`, `featured` and a site's own pages.
- Hooks: lifecycle, search, seed, server copy and dashboard.
