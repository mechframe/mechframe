# discography

The site's music library: albums, EPs and singles with their tracks in order, credits, streaming links and covers from the media library. A track plays from an uploaded master, made into a public stream file by a job, or from a SoundCloud link. The contract is `dev plans/contracts/discography.md`; decision 0070 records the audio library and its licence check.

## What it does

Staff make a release as a draft, give it a front and a back cover from the media library, its words (title, kind, year, artist line, credit line, summary) and an address under `/music`, then add tracks: uploaded masters (WAV, AIFF, FLAC, Ogg or MP3, up to 60 MB each) or SoundCloud links (a track, or a playlist that plays as one track). A release goes live now or on its release day, through the kernel's lifecycle, and a live release's save changes the site at once. An address it leaves answers 301 to where it is now, its tracks' addresses too.

An upload is judged by its bytes (`soundfile`, libsndfile under LGPL-2.1, decision 0070) and stored in the private bucket. The job `discography.process_track` reads it in a thread and writes a constant-bitrate MP3 at `stream_bitrate_kbps` to the public bucket under an unguessable key, with its length and 1,000 waveform peaks. A replace during the run throws the result away. A track plays from its stream file once it's ready, else from its SoundCloud link, else it can't play: then it's hidden from every public answer, page and `public.py`, and flagged in the admin and on the dashboard.

Credits are rows of a role and a name, on a release or a track. Each name is one person however often it's credited, with a profile state (not linked, the collective, not a member; a member's profile waits for `roster`), and goes with its last credit. The five roles (Artist, Featuring, Produced by, Written by, Mastered by) are the migration's, and staff edit the list. Streaming links come from a fixed list of nine platforms, read from the link's host, per release and for the artist ("Listen everywhere").

The site's pages play through `audio-player` (0.1.1, its contract's "discography 0.1.1" block, `dev plans/contracts/audio-player.md` §2). A release page's Play album and each row's play start its playable tracks as one queue, the row that plays shows the three bars, and the Player docks after the footer, as the Release board draws it. A track's page draws the player's bar with its waveform. A play counts once the player has heard enough of it, through discography's own route, which counts only a live track that plays: once per listener a day, with nothing kept that identifies anyone (decision 0071). The Dashboard's "Plays this week" card, for those who manage the library, shows the last seven days' plays, the change on the seven before and the track that leads.

discography can't be on without `audio-player` (its requirement), so its pages never draw the fallback while the site runs. If the modules read says `audio-player` is off, they play an upload in the browser's own `<audio controls preload="none">` and offer a SoundCloud track as a "Listen on SoundCloud" link, loading nothing from SoundCloud.

## Use when / avoid when

Use it when the site belongs to an artist, band, label or collective whose releases need their own pages, credits, streaming links or an on-site player, from uploaded masters or music already on SoundCloud. Avoid it when music is only linked out and never played on the site: that's `embeds`. Avoid it for a beat or sample for sale: that's `licensing`.

## What it adds

- **Routes**, under `/api/discography`:
  - public: `GET /releases?kind=&cursor=&limit=` (`{items, next_cursor}`, live releases newest first, 12 a page), `GET /releases/{slug}` (the release with its playable tracks, each with its `id`, credits and links, or `{moved}`), `GET /releases/{slug}/tracks/{track}` (a playable track, lyrics while `show_lyrics` is on, or `{moved}`), `GET /links` (the artist's own) and `POST /tracks/{id}/plays` (204 whether it counted or not; 60 an hour from one address, then 429 `kernel.rate_limited`); by id (0.1.2), for a homepage's players: `GET /releases?ids=` (50 at most, the live ones in the order given, one page) and `GET /tracks?ids=` (`{items}`, the live tracks that play in the order given, each a `TrackCard`: a `TrackLine` with its `release: {title, slug, artist_line, cover, path}`);
  - `discography.release.manage`: `GET /admin/plays` (`{this_week, last_week, leading}`, the Dashboard card's, by UTC days); `GET`/`POST /admin/releases`; `GET`/`PATCH`/`DELETE /admin/releases/{id}` (credits, links and the tracks' order in one save); `POST …/publish` (`{at?}`) and `…/unpublish`; `POST …/tracks` (a SoundCloud link or no audio) and `POST …/tracks/upload` (multipart, 201); `GET /admin/tracks?q=&show=&cursor=`; `GET`/`PATCH`/`DELETE /admin/tracks/{id}`; `PUT`/`DELETE …/audio` and `POST …/audio/retry`; `GET /admin/people`, `PATCH /admin/people/{id}`; `GET`/`PUT /admin/roles`; `GET`/`PUT /admin/links`;
  - a stale `version` answers 409 `discography.changed` with the row as it is now. An upload over 60 MB answers 413 `discography.too_large` (over the routes' 64 MB, the kernel's `kernel.too_large`), one that isn't audio 415 `discography.not_audio`, one over an hour 422 `discography.too_long`, a link that isn't a SoundCloud track or playlist 422 `discography.not_soundcloud`, and an upload with storage off 503 `discography.storage_off`.
- **Public pages:** `/music`, `/music/:release` and `/music/:release/:track`. The server copy answers each, with `MusicAlbum`, `MusicRecording` and `ItemList` JSON-LD and no audio address, and lists live releases and their tracks in the sitemap and `llms.txt`.
- **The admin pages,** under Music in the sidebar: `/admin/music` (Albums: the releases, New release, the Music settings for an admin), `/admin/music/:id` (the album editor), `/admin/music/tracks` (Tracks, with each track's audio, lyrics and credits beside the list; `?track=` and `?show=` pick one and a filter) and `/admin/music/credits` (Credits, with the roles).
- **Menus and cards:** Music in `nav.public`; Albums, Tracks and Credits in `nav.admin`'s Music section; "Plays this week" in `admin.dashboard.widget`, for `discography.release.manage`.
- **Tables:** `discography_release`, `discography_track`, `discography_person`, `discography_role`, `discography_credit`, `discography_link` and `discography_move` (migration `discography_0001`, after the kernel's `kernel_0014` and media's `media_0001`).
- **Files:** masters at `discography/masters/<track>/<n>.<ext>` in the private bucket; stream files at `discography/stream/<unguessable>.mp3` in the public one; both removed after the commit that drops them (`discography.delete_files`). A master whose upload or replace doesn't commit is deleted in the background once the transaction ends, unless a track names it then (0.1.3). It's best effort: if that read or the delete fails, the master stays in the private bucket, which no address reaches.
- **Permissions:** `discography.release.manage` (admin, editor) and `discography.settings.manage` (admin); an owner holds every permission. The Music settings save through the kernel's settings routes, so `kernel.settings.manage` too.
- **Events:** emits `discography.release.published` (once a release, the first time it goes live), `discography.release.changed`, `discography.release.deleted`, `discography.track.processed` and `discography.track.deleted`; hears `kernel.content.published`.
- **Plays:** audio-player's, as `discography.track`. Deleting a track or a release forgets its tracks' plays in the same transaction.
- **Hooks:** lifecycle (`discography.release`); search (releases, by their playable tracks' titles, credits and, under `show_lyrics`, lyrics); seed (an album of three tracks made from tones, processed while storage is on, and a SoundCloud-only single, each with two weeks of daily plays ending on the day it's run); server copy; dashboard (a live release's track that can't play, a failed upload, and storage's two buckets); item references (0.1.2, `refs.py`, hook 11): `discography.release` ("Albums", its line "2026, petro and J Tone, 15 tracks", live while on the site with a track that plays) and `discography.track` ("Tracks", its line "Catalyst, petro and J Tone", live while its release is on the site and it plays), each with its release's cover, picked by title, drafts too, newest edit first, so `featured`'s players can hold them. No export or erase: credits are names staff type, not anyone's account.

## Settings and env vars

- `stream_bitrate_kbps` (int, 256, from 128 to 320): the stream file's constant bitrate, taken to MP3's nearest standard rate. New uploads use it.
- `show_explicit_badge` (bool, true): the Parental Advisory label on explicit releases and tracks.
- `show_lyrics` (bool, true): lyrics on a track's page, for tracks that have them.

No variables of its own. Uploads need the kernel's storage: masters go in `STORAGE_BUCKET`, and until it's set an upload answers 503 `discography.storage_off`. Stream files go in `STORAGE_PUBLIC_BUCKET` at `STORAGE_PUBLIC_URL`; without that pair a track fails once its job's tries are used. While `STORAGE_PUBLIC_URL` is set, the kernel adds its origin to `media-src` so a stream file plays (decision 0070).

## Install notes

`mechframe add media`, `mechframe add embeds` and `mechframe add audio-player` first, then `mechframe add discography`, then the migrations. `soundfile` and `numpy` come with it: declared in `requirements.in`, installed from the hash-pinned `requirements.txt` compiled from it (`python -m pip install --require-hashes -r requirements.txt`). On a site with a separate jobs worker (`JOBS_IN_WEB=false`), processing runs there. Its web binding imports media's `ImagePicker` and `Picture` as `@/modules/media/public`, and audio-player's `PlayButton`, `PlayerBar`, `PlayerDock`, `Equalizer` and `usePlayer` as `@/modules/audio-player/public` (decision 0057).

## Extension points

- **Backend, `discography.public`**, for modules listing `discography` in `requires`: `track_cards(db, ids)` and `release_cards(db, ids)` give `dict[UUID, Card]` of live, playable items only (title, artist line, the cover as media's `Picture`, `stream_url` or `soundcloud_url`, `duration_ms`, `peaks`, `explicit`, `path`; a release's card carries its playable tracks as `tracks`). Also `releases(db)`, `release(db, slug)`, `track(db, slug, track_slug)` and `path(release, track=None)`, each the API's answer as its model.
- **Web, `@/modules/discography/public`** (decision 0057), for a site's own Music and Release pages: `useReleases({ kind, ids })` (an infinite query; with `ids`, one page of the live ones in the order given; given an empty `ids` array, an empty page and no request, while `useReleases()` with no `ids` at all lists the newest), `useTracks(ids)` (a homepage's Spotlight: `items.map((each) => playerItem(each, each.release))`; given an empty array, an empty list and no request), `useRelease(slug)`, `useTrack(release, track)`, `useArtistLinks()`, `isMoved`, `pathOf`, `releaseLine`, `clock` and `KIND_WORDS`; `playerItem(track, release)` and `playerQueue(release)`, a site's Spotlight and deck queues for audio-player, each item counting its play through discography's route; and the answers' types (`ReleaseCard`, `LiveRelease`, `LiveTrack`, `TrackLine`, `TrackCard`, `TrackRelease`, `MusicCover`, `MusicCredit`, `MusicLink`, `MusicMoved`).
- The events above.

## Known limits

- No M4A or ALAC masters: libsndfile doesn't read them (415). A master's sample rate must be one MP3 holds, or a whole multiple of 44.1 or 48 kHz.
- Nothing is fetched from SoundCloud: no titles, artwork or lengths. A link-only track's length is typed.
- A release page's tracklist draws a made-up waveform shape: only a track's own page has its peaks.
- The plays are only the Dashboard card's: no stats page, charts or exports (audio-player's contract §6).
- How a homepage draws featured's Releases deck and Spotlight is the site's own; roster's linked profiles and shop's Buy the CD are their modules' (§6).

## Source and license

New code for MechFrame, proprietary (decision 0008). `soundfile` is BSD-3 and bundles libsndfile (LGPL-2.1), loaded as a library of its own; `numpy` is BSD-3 (decision 0070).
