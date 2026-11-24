---
feature: The discography module, the site's music library: releases, tracks, credits and streaming links, with an upload or a SoundCloud link as a track's audio (Vibrant Mindz step 2, the first of three; the side lane's M8)
status: approved
approved: 2026-11-24 (the owner: "Approve as recommended", the five answers in §8 as recommended)
plan: `docs/plans/vibrant-mindz-backend/backend-plan.md` (§2, 3) and `players-admin.md`; `dev plans/2026-11-23-side-lane-m8-discography.md`; the canvas's Music boards (VM Website `design/site/AdminMusic`, `AdminAlbum`, `AdminTracks`, `AdminCredits`, `Music` and `Release.dc.html`; the Album editor at https://claude.ai/artifact/W7EZQumtcK36K3xczG8mNH)
pr: one, to predict at push time; decision 0070; migration `discography_0001`
---

# Contract: `discography`

## 1. Goal

The team keeps every release in one library: albums, EPs and singles, each with its tracks in order, its credits, its streaming links and its front and back covers from `media`. A track plays from an uploaded master, which a job turns into a public stream file, its length and its waveform peaks, or from a SoundCloud link. Live releases get their own pages at `/music`, `/music/<release>` and `/music/<release>/<track>`. `audio-player` and `featured`, step 2's next two modules, read the library through `public.py`. The library itself never puts anything on the homepage (`players-admin.md`, "Library vs placement").

## 2. Interfaces

**Permissions** (granted in `discography_0001`): `discography.release.manage` (owner, admin, editor) covers releases, tracks, uploads, credits and links. `discography.settings.manage` (owner, admin) covers the Music settings.

**Settings:** `stream_bitrate_kbps` (int, 256, from 128 to 320), `show_explicit_badge` (bool, true; the board's "Parental Advisory label") and `show_lyrics` (bool, true; new). The scaffold's `default_audio_source` is gone if §8, 5b is agreed.

**HTTP** (`/api/discography`, behind `require_module("discography")`; RFC 9457 codes `discography.*`; a stale `version` answers 409 `kernel.save_conflict`, as in decision 0046):

| Route | Access | Does |
| --- | --- | --- |
| `GET /releases?kind=&cursor=&limit=` | public | `{items: ReleaseCard[], next_cursor}`: live releases, newest first, 12 a page |
| `GET /releases/{slug}` | public | `Release` (the card, plus `tracks`, `credits` and `links`), or `{moved}` |
| `GET /releases/{slug}/tracks/{track}` | public | `Track` (lyrics only while `show_lyrics` is on), or `{moved}` |
| `GET /links` | public | The artist's own links, the Music page's "Listen everywhere" |
| `GET /admin/releases`, `POST /admin/releases` | manage | Every release with its badges (`tracklist_to_come`, `unplayable`: how many of its tracks can't play); create one as a draft |
| `GET`, `PATCH`, `DELETE /admin/releases/{id}` | manage | The album editor. `PATCH` takes the fields in §3, `credits`, `links` and `track_ids` (the order) in one save |
| `POST /admin/releases/{id}/publish` `{at?}`, `/unpublish` | manage | Through `kernel.lifecycle`. A release day is a time in Eastern |
| `POST /admin/releases/{id}/tracks` | manage | JSON `{title, soundcloud_url?}`: a track with a link or no audio yet |
| `POST /admin/releases/{id}/tracks/upload` (multipart `file`) | manage | A track per file, titled from its tags or its name and queued for processing; 201 |
| `GET /admin/tracks?q=&show=all\|cant_play\|no_lyrics\|no_credits&cursor=` | manage | The Tracks board |
| `GET`, `PATCH`, `DELETE /admin/tracks/{id}` | manage | Title, slug, explicit, lyrics, SoundCloud link, a typed length for a link-only track, credits |
| `PUT /admin/tracks/{id}/audio` (multipart), `DELETE …/audio`, `POST …/audio/retry` | manage | Replace, remove or retry the upload |
| `GET /admin/people`, `PATCH /admin/people/{id}`, `GET`/`PUT /admin/roles` | manage | The Credits board: each name with its profile state and what it's credited for; the roles list |
| `PUT /admin/links` | manage | The artist's own links |

An upload over 64 MB (the kernel's route ceiling, decision 0054) answers 413 `discography.too_large`, with the message "Export it as FLAC: it keeps every bit at about half the size." A file with no audio stream answers 415 `discography.not_audio`. One over 60 minutes answers 422 `discography.too_long`. A link that isn't a SoundCloud track or playlist answers 422 `discography.not_soundcloud`. With storage off, an upload answers 503 `discography.storage_off`.

**The job** `discography.process_track` (3 tries, 30-minute timeout, keyed by the track). It downloads the master and reads it with soundfile in a thread (§8, 1, as changed after approval). It encodes the stream file and works out the duration and 1,000 peaks. It writes `processing_percent` as it goes, in short transactions of its own. It stores the stream under `storage.unguessable_key`, so nobody can find a draft's audio before release day. It commits only if the track still has that master (a replace during the run throws its result away), then emits `discography.track.processed`. `discography.delete_files` removes masters and stream files after the commit that drops them.

**Plays from:** the stream file once it's ready; otherwise the SoundCloud link; otherwise the track can't play. A track that can't play is hidden from the public answers, the pages and `public.py`, and flagged in the admin.

**`public.py`** (for modules that list `discography` in `requires`): `track_cards(db, ids)` and `release_cards(db, ids)` give `dict[UUID, Card]`, live and playable items only. A card has the title, artist line, the cover as media's `Picture`, `stream_url` or `soundcloud_url`, `duration_ms`, `peaks`, `explicit` and `path`. Also `releases(db)`, `release(db, slug)` and `path(...)`, each the API's answer as its Pydantic model, as `blog.public` gives them.

**`web/public.ts`:** `useReleases`, `useRelease`, `useTrack`, `useArtistLinks`, `isMoved`, `pathOf` and the answers' types, for a site's own Music and Release pages (VM Website's). discography's own pages read through the same hooks.

**Pages:**
- Admin, under `nav.admin`'s Music section: `/admin/music` (releases, with the Music settings panel), `/admin/music/:id` (the album editor), `/admin/music/tracks` and `/admin/music/credits`, as the boards draw them. The scaffold's `/admin/discography` becomes these.
- Public, under `nav.public` as Music: the three pages in §1.
- Until `audio-player` is on, a page plays an uploaded track in a native `<audio controls preload="none">` and offers a SoundCloud track as a "Listen on SoundCloud" link. Nothing loads from SoundCloud.

**Events:**
- `discography.release.published` `{release_id, slug, title, kind, path}`: once a release, the first time it goes live, as blog's is.
- `discography.release.changed` `{release_id}`: a live release or one of its tracks was saved (for the homepage's cache).
- `discography.release.deleted` `{release_id, track_ids}`.
- `discography.track.processed` `{track_id, release_id, duration_ms}`.
- `discography.track.deleted` `{track_id, release_id}`.

The scaffold's `album.*` and `track.published` events are gone (§8, 5a).

**Hooks** (§8, 4): lifecycle, search, seed, server copy, dashboard; no export or erase.

## 3. Data

Branch `discography`, `discography_0001`, `depends_on` `kernel_0014` (search) and `media_0001` (covers' uses), as blog's.

| Table | Columns |
|---|---|
| `discography_release` | `id`, `version`, `kind` (`album`, `ep`, `single`), `title` (≤ 200), `slug` unique (CHECK, ≤ 80), `year` (smallint, 1900 to 2100, null), `artist_line` (≤ 200), `credit_line` (≤ 300), `summary` (≤ 300), `cover_id` and `back_cover_id` (media image ids, no FK across modules), `tracklist_to_come` (bool), `announced_at`, the lifecycle's columns (`discography.release`), `created_at`, `updated_at` |
| `discography_track` | `id`, `version`, `release_id` → release `ON DELETE CASCADE`, `position` (unique with `release_id`, deferrable), `title` (≤ 200), `slug` (≤ 80, unique with `release_id`), `explicit`, `lyrics` (≤ 20,000, null), `soundcloud_url` (≤ 500, null), `soundcloud_kind` (`track`, `set`), `master_key`, `master_name` (≤ 150, a label only), `master_bytes`, `stream_key`, `duration_ms`, `peaks` (jsonb: 1,000 integers from 0 to 255, each the loudest sample in its slice, scaled so the loudest slice is 255), `audio_state` (`none`, `processing`, `ready`, `failed`), `processing_percent`, `audio_error` (a code), `created_at`, `updated_at` |
| `discography_person` | `id`, `version`, `name` (≤ 120, unique on `lower(name)`), `profile` (`unlinked`, `collective`, `member`, `not_member`), `roster_profile_id` (uuid, set only when `member`; no FK, roster's step 3) |
| `discography_role` | `id`, `name` (≤ 60, unique), `position`. Seeded Artist, Featuring, Produced by, Written by, Mastered by |
| `discography_credit` | `id`, `person_id` → person `RESTRICT`, `role_id` → role `RESTRICT`, `release_id` or `track_id` (CHECK exactly one; each `CASCADE`), `position`. A person whose last credit goes is removed in the same save |
| `discography_link` | `id`, `release_id` (null for the artist's own) `CASCADE`, `platform` (`spotify`, `apple-music`, `youtube`, `youtube-music`, `amazon-music`, `soundcloud`, `bandcamp`, `tidal`, `deezer`, read from the link's host), `url` (≤ 500), `position`, unique (`release_id`, `platform`) |
| `discography_move` | `old_path` (≤ 170) PK, `release_id` `CASCADE`, `track_id` (null) `CASCADE`, `created_at`: an old slug answers 301, as pages' moves do |

Files: masters in the private bucket at `discography/masters/<track_id>/<n>.<ext>`; streams in the public bucket at `discography/stream/<unguessable>.mp3`.

## 4. Files

- `modules/discography/`, laid out as `blog`'s, with `requires` `media ^0.1` and `embeds ^0.1` (§8, 2).
- `backend/discography/`: `__init__` (`BODY_LIMITS` of 64 MB on the three upload routes, and `CSP`), `models`, `schemas`, `service`, `audio` (soundfile: the probe, the stream file, the peaks), `jobs`, `router`, `public`, `lifecycle`, `search`, `seed`, `dashboard`, `server_copy`, `events`.
- `web/`: `module.web.ts`, `api.ts`, `public.ts`, `reads.ts`, and pages `AdminMusic`, `AdminRelease`, `AdminTracks`, `AdminCredits`, `Music`, `Release` and `Track`.
- `requirements.in`: `soundfile` and `numpy` (decision 0070), re-pinned with hashes.
- **The kernel:** the public bucket's origin joins `media-src` while it's set, so a stream file plays (decision 0070). That's one line in `security.py`, and the main lane hears of it first.
- Generated again: `catalog.json`, OpenAPI and `schema.ts`, event schemas, host variables, `progress.json`. `modules/_discography/` becomes `modules/discography/`, and `MODULE.md` and `module.json` say what's agreed here.

## 5. Conventions this follows

- SPEC 4 to 11 and 16.
- `mechframe-module-extractor`, `alembic-multi-module-migrations` and `module-contract-lint`.
- The hooks as `hooks.md` defines them.
- `blog` for covers through media (decision 0057), the public surface, moves and the server copy.
- `media` for uploads judged by their bytes; the kit for every screen; decision 0035 for the job.

## 6. Non-goals

- **audio-player's:** the custom player, the drawn waveform, the docked bar, SoundCloud's widget behind consent, and one thing playing at a time.
- **featured's:** the homepage's Releases deck and Spotlight, and the boards' "On the Releases deck" badge and "Preview on the deck".
- **shop's (step 5):** Buy the CD.
- **roster's (step 3):** linking a credit to a member's profile, and the artist line as a link. The `member` state and its column wait for it.
- Selling or downloading tracks (`downloads`, `licensing`), ISRC and UPC codes, and distributors.
- Asking SoundCloud or any other platform anything: no oEmbed, no API, no artwork or titles fetched.
- Uploads over 64 MB, and uploads straight to the bucket.
- Comments and reactions on releases.

## 7. Acceptance

- **Contract tests:**
  - every route's access, and a stale `version` 409;
  - a draft's 404, a scheduled release going live, a moved slug's 301;
  - a track that can't play missing from every public answer;
  - the four upload refusals;
  - a SoundCloud track and a playlist accepted, and a profile refused;
  - covers' uses recorded and released.
- **The job,** with a WAV the test writes with the standard library's `wave`: an MP3 stream at the setting's bitrate whose duration is within 50 ms, 1,000 peaks, and `track.processed` emitted. A replace during the run is thrown away; a retry finishes. No suite calls SoundCloud.
- **Server copy:** each page's JSON-LD (§8, 3), the sitemap and `llms.txt`, and no audio address in any of them.
- **Data and hooks:** the migration round trip; the seed twice gives the same; the dashboard's items; search finds a track by its credit.
- **Web:** the four admin boards and three public pages in both themes, axe clean, at 1440 and 390.
- **Gates:** `validate_schemas`, `module-contract-lint`, `oss-licence-gate` on soundfile and the libsndfile its wheels carry (decision 0070), then `mechframe add discography` and `mechframe check`.

## 8. Open questions for the owner

1. **How an upload becomes a stream file and peaks, and where it runs.** (Answered with soundfile instead, after the licence check: see "Changes after approval".)
   - *Recommended at first:* PyAV in the kernel job above. Its wheels carry FFmpeg's libraries, pinned by hash like every other dependency, so the job runs the same on your PC, in CI and on Railway, with no Dockerfile change.
   - The stream is AAC in `.m4a` at `stream_bitrate_kbps`, 44.1 kHz stereo, set up to play before it's fully loaded; every browser's `<audio>` plays it. Masters can be WAV, AIFF, FLAC, MP3, M4A or Ogg, up to 64 MB.
   - On Vibrant Mindz it runs in the site's worker service (`python -m app.worker`, with `JOBS_IN_WEB=false` on the web service), as decision 0035 chose. Adding that Railway service is your step. Until then it runs in the web process.
   - *The other way:* the `ffmpeg` command from apt in the Dockerfile. It's unpinned and outside the hash checks, and it isn't on your PC, so the tests would skip there.
2. **What a SoundCloud link stores.**
   - *Recommended:* the link in its plain form (`https://soundcloud.com/<artist>/<track>`, or `/sets/<playlist>`), its kind, and a length you type if you want one shown. The link is checked with `embeds`' `recognise`, so any link discography takes is one `audio-player` can play. That makes `embeds` a requirement.
   - A playlist link plays as one track, the way Catalyst plays its full album until its tracklist is in. It gets a generic waveform.
   - Nothing is fetched from SoundCloud: its API needs an app registration.
   - *The other way:* SoundCloud's oEmbed at save time, through the kernel's outbound guard, to fill in the title and artwork.
3. **The public pages' server copy.**
   - *Recommended:* `/music/<release>` answers a `MusicAlbum` JSON-LD: `albumReleaseType` from its kind, `byArtist` as a `MusicGroup` named by the artist line, `datePublished` from the year, the front cover as `image` and `og:image`, and `track` as `MusicRecording`s (name, position, ISO 8601 duration, address).
   - `/music/<release>/<track>` answers a `MusicRecording` with `inAlbum`. `/music` answers an `ItemList` of the albums.
   - No stream address goes to crawlers. Lyrics appear in the page's text only while `show_lyrics` is on. The sitemap and `llms.txt` list live releases and their tracks.
4. **Which hooks it fills.** *Recommended:*
   - **lifecycle:** `discography.release`. Drafts and a scheduled release day; tracks go live with their release.
   - **search:** releases and tracks, by title, artist line, credits and lyrics.
   - **seed:** an album of three tracks made from generated tones, processed by the real job while storage is on and "No audio yet" while it's off, plus a SoundCloud-only single and the five roles.
   - **dashboard:** `ATTENTION` for a live release's track that can't play and for a failed upload; `SETUP` for storage's two buckets.
   - **No export or erase:** credits are names typed by staff, not anyone's account.
   - **Not taxonomy:** roles get their own table, so whoever manages releases can edit them.
5. **Where the six boards and the plan's data model differ.** *Recommended:*
   - a. **Releases with a kind** (album, EP, single), every track on one. `album` becomes `release` in the tables, the events and `release_cards`; nothing reads them yet.
   - b. **A track may have both an upload and a SoundCloud link,** and plays the upload once it's ready, as the Music settings panel says. `default_audio_source` goes.
   - c. **Explicit is marked on each track.** A release shows Parental Advisory when any of its tracks is explicit.
   - d. **Front and back covers come from media.** The plan's `screen_url` and `screen_focus` aren't drawn, so they wait for the Releases deck's contract.
   - e. **Credits are rows** of a role and a name, on a release or a track, gathered on the Credits board with each name's profile state. The Tracks board's credits textarea becomes rows.
   - f. **Lyrics belong to the track** and show on its own page, under `show_lyrics`.
   - g. **Streaming links come from a fixed list of platforms,** per release and for the artist ("Listen everywhere").
   - h. **A track that can't play is hidden** from public lists, as the album editor says, though the Release board lists it.
   - i. **Drafts and scheduling for releases,** which the boards don't draw, plus "Tracklist to come" as a switch on the release.

## Changes after approval

- **2026-11-24: soundfile, not PyAV** (the owner's choice, after the `oss-licence-gate` check). PyAV 19.0.2 is BSD, and its FFmpeg calls itself LGPL v3. But its Windows and manylinux wheels both bundle libx264 and libx265, which are GPL, in the same process as the module's closed-source code. The gate rates that "don't ship".
  - soundfile 0.14.0 (BSD-3) bundles libsndfile 1.2.2 (LGPL-2.1, loaded as a library of its own), with hash-pinned wheels for Windows and manylinux.
  - It reads WAV, AIFF, FLAC, Ogg and MP3 masters; no M4A or ALAC (415 `discography.not_audio`).
  - It writes the stream as MP3 at a constant `stream_bitrate_kbps`, taken to MP3's nearest standard rate: 256 kbps measured at 257. MP3's patents have expired.
  - numpy reads the peaks. The ffmpeg program from apt, the third option, lost: not pinned by hash, and absent from the owner's PC.
  - Decision 0070 keeps the gate's table.
