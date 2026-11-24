# discography

The site's music library: albums, EPs and singles with their tracks in order, credits, streaming links and covers from the media library. A track plays from an uploaded master, made into a public stream file by a job, or from a SoundCloud link. The contract is `dev plans/contracts/discography.md`; decision 0070 records the audio library and its licence check.

## What it does

Staff make a release as a draft, give it a front and a back cover from the media library, its words (title, kind, year, artist line, credit line, summary) and an address under `/music`, then add tracks: uploaded masters (WAV, AIFF, FLAC, Ogg or MP3, up to 60 MB each) or SoundCloud links (a track, or a playlist that plays as one track). A release goes live now or on its release day, through the kernel's lifecycle, and a live release's save changes the site at once. An address it leaves answers 301 to where it is now, its tracks' addresses too.

An upload is judged by its bytes (`soundfile`, libsndfile under LGPL-2.1, decision 0070) and stored in the private bucket. The job `discography.process_track` reads it in a thread and writes a constant-bitrate MP3 at `stream_bitrate_kbps` to the public bucket under an unguessable key, with its length and 1,000 waveform peaks. A replace during the run throws the result away. A track plays from its stream file once it's ready, else from its SoundCloud link, else it can't play: then it's hidden from every public answer, page and `public.py`, and flagged in the admin and on the dashboard.

Credits are rows of a role and a name, on a release or a track. Each name is one person however often it's credited, with a profile state (not linked, the collective, not a member; a member's profile waits for `roster`), and goes with its last credit. The five roles (Artist, Featuring, Produced by, Written by, Mastered by) are the migration's, and staff edit the list. Streaming links come from a fixed list of nine platforms, read from the link's host, per release and for the artist ("Listen everywhere").

Until `audio-player` is on, the site's pages play an upload in the browser's own `<audio controls preload="none">` and offer a SoundCloud track as a "Listen on SoundCloud" link. Nothing loads from SoundCloud.

## Use when / avoid when

Use it when the site belongs to an artist, band, label or collective whose releases need their own pages, credits, streaming links or an on-site player, from uploaded masters or music already on SoundCloud. Avoid it when music is only linked out and never played on the site: that's `embeds`. Avoid it for a beat or sample for sale: that's `licensing`.

## What it adds

- **Routes**, under `/api/discography`:
  - public: `GET /releases?kind=&cursor=&limit=` (`{items, next_cursor}`, live releases newest first, 12 a page), `GET /releases/{slug}` (the release with its playable tracks, credits and links, or `{moved}`), `GET /releases/{slug}/tracks/{track}` (a playable track, lyrics while `show_lyrics` is on, or `{moved}`) and `GET /links` (the artist's own);
  - `discography.release.manage`: `GET`/`POST /admin/releases`; `GET`/`PATCH`/`DELETE /admin/releases/{id}` (credits, links and the tracks' order in one save); `POST …/publish` (`{at?}`) and `…/unpublish`; `POST …/tracks` (a SoundCloud link or no audio) and `POST …/tracks/upload` (multipart, 201); `GET /admin/tracks?q=&show=&cursor=`; `GET`/`PATCH`/`DELETE /admin/tracks/{id}`; `PUT`/`DELETE …/audio` and `POST …/audio/retry`; `GET /admin/people`, `PATCH /admin/people/{id}`; `GET`/`PUT /admin/roles`; `GET`/`PUT /admin/links`;
  - a stale `version` answers 409 `discography.changed` with the row as it is now. An upload over 60 MB answers 413 `discography.too_large` (over the routes' 64 MB, the kernel's `kernel.too_large`), one that isn't audio 415 `discography.not_audio`, one over an hour 422 `discography.too_long`, a link that isn't a SoundCloud track or playlist 422 `discography.not_soundcloud`, and an upload with storage off 503 `discography.storage_off`.
- **Public pages:** `/music`, `/music/:release` and `/music/:release/:track`. The server copy answers each, with `MusicAlbum`, `MusicRecording` and `ItemList` JSON-LD and no audio address, and lists live releases and their tracks in the sitemap and `llms.txt`.
- **The admin pages,** under Music in the sidebar: `/admin/music` (Albums: the releases, New release, the Music settings for an admin), `/admin/music/:id` (the album editor), `/admin/music/tracks` (Tracks, with each track's audio, lyrics and credits beside the list; `?track=` and `?show=` pick one and a filter) and `/admin/music/credits` (Credits, with the roles).
- **Menus:** Music in `nav.public`; Albums, Tracks and Credits in `nav.admin`'s Music section.
- **Tables:** `discography_release`, `discography_track`, `discography_person`, `discography_role`, `discography_credit`, `discography_link` and `discography_move` (migration `discography_0001`, after the kernel's `kernel_0014` and media's `media_0001`).
- **Files:** masters at `discography/masters/<track>/<n>.<ext>` in the private bucket; stream files at `discography/stream/<unguessable>.mp3` in the public one; both removed after the commit that drops them (`discography.delete_files`).
- **Permissions:** `discography.release.manage` (admin, editor) and `discography.settings.manage` (admin); an owner holds every permission. The Music settings save through the kernel's settings routes, so `kernel.settings.manage` too.
- **Events:** emits `discography.release.published` (once a release, the first time it goes live), `discography.release.changed`, `discography.release.deleted`, `discography.track.processed` and `discography.track.deleted`; hears `kernel.content.published`.
- **Hooks:** lifecycle (`discography.release`); search (releases, by their playable tracks' titles, credits and, under `show_lyrics`, lyrics); seed (an album of three tracks made from tones, processed while storage is on, and a SoundCloud-only single); server copy; dashboard (a live release's track that can't play, a failed upload, and storage's two buckets). No export or erase: credits are names staff type, not anyone's account.

## Settings and env vars

- `stream_bitrate_kbps` (int, 256, from 128 to 320): the stream file's constant bitrate, taken to MP3's nearest standard rate. New uploads use it.
- `show_explicit_badge` (bool, true): the Parental Advisory label on explicit releases and tracks.
- `show_lyrics` (bool, true): lyrics on a track's page, for tracks that have them.

No variables of its own. Uploads need the kernel's storage: masters go in `STORAGE_BUCKET`, and until it's set an upload answers 503 `discography.storage_off`. Stream files go in `STORAGE_PUBLIC_BUCKET` at `STORAGE_PUBLIC_URL`; without that pair a track fails once its job's tries are used. While `STORAGE_PUBLIC_URL` is set, the kernel adds its origin to `media-src` so a stream file plays (decision 0070).

## Install notes

`mechframe add media` and `mechframe add embeds` first, then `mechframe add discography`, then the migrations. `soundfile` and `numpy` come with it: declared in `requirements.in`, installed from the hash-pinned `requirements.txt` compiled from it (`python -m pip install --require-hashes -r requirements.txt`). On a site with a separate jobs worker (`JOBS_IN_WEB=false`), processing runs there. Its web binding imports media's `ImagePicker` and `Picture` as `@/modules/media/public` (decision 0057).

## Extension points

- **Backend, `discography.public`**, for modules listing `discography` in `requires`: `track_cards(db, ids)` and `release_cards(db, ids)` give `dict[UUID, Card]` of live, playable items only (title, artist line, the cover as media's `Picture`, `stream_url` or `soundcloud_url`, `duration_ms`, `peaks`, `explicit`, `path`; a release's card carries its playable tracks as `tracks`). Also `releases(db)`, `release(db, slug)`, `track(db, slug, track_slug)` and `path(release, track=None)`, each the API's answer as its model.
- **Web, `@/modules/discography/public`** (decision 0057), for a site's own Music and Release pages: `useReleases({ kind })` (an infinite query), `useRelease(slug)`, `useTrack(release, track)`, `useArtistLinks()`, `isMoved`, `pathOf`, `releaseLine`, `clock` and `KIND_WORDS`, and the answers' types (`ReleaseCard`, `LiveRelease`, `LiveTrack`, `TrackLine`, `MusicCover`, `MusicCredit`, `MusicLink`, `MusicMoved`).
- The events above.

## Known limits

- No M4A or ALAC masters: libsndfile doesn't read them (415). A master's sample rate must be one MP3 holds, or a whole multiple of 44.1 or 48 kHz.
- Nothing is fetched from SoundCloud: no titles, artwork or lengths. A link-only track's length is typed.
- audio-player's custom player, drawn waveform and docked bar, featured's Releases deck, roster's linked profiles, and shop's Buy the CD are their modules' (§6).

## Source and license

New code for MechFrame, proprietary (decision 0008). `soundfile` is BSD-3 and bundles libsndfile (LGPL-2.1), loaded as a library of its own; `numpy` is BSD-3 (decision 0070).
