---
feature: Bandcamp's own player for a track, or its album, in discography, drawn through a frame embeds gives a page (VM Website's ask B; the side lane's M15)
status: approved
approved: 2026-11-28 (the owner: "Approve as recommended", the three answers in §8 as recommended)
plan: `dev plans/2026-11-28-side-lane-m15-bandcamp.md`; VM Website's ask `C:\DEV\VM Website\dev plans\2026-11-28-ask-b-bandcamp-player.md`, its approved `dev plans/contracts/player-sources.md` (§2 B, §8, 3 and 4) and the boards on canvas 123 (`design/site/Main`, `Release`, `Track`, `AdminTracks`, `AdminAlbum` and `AdminMusic.dc.html`; shared parts in `design/generators/player_sources.py`)
pr: one, discography 0.1.5 and embeds 0.1.2, its number read from GitHub just before the push; decision 0075; migration `discography_0002`
---

# Contract: Bandcamp's own player

## 1. Goal

A track with no uploaded file and no SoundCloud link plays in Bandcamp's own player: its own, pasted as Bandcamp's embed code on the track, else its album's. It's live like any other track, on its release's page, its own page, the homepage's players and the admin's lists. A page draws Bandcamp's frame behind a Listen of its own, built from the modules' public parts.

## 2. Interfaces

### discography 0.1.5 (requires `embeds ^0.1.2`)

**The source order** (the owner's, player-sources §8, 3):
- `service.plays_from(track: Track, release: Release) -> Literal["upload", "soundcloud", "bandcamp"] | None` returns, in order: the stream file once it's made; else the SoundCloud link; else Bandcamp's player (the track's own `bandcamp_url`, else its release's); else None. It now takes the release, and every caller passes it.
- `service.playable_clause()` gains `Track.bandcamp_url IS NOT NULL OR Release.bandcamp_url IS NOT NULL`, so every query that uses it joins `Release`.
- `service.bandcamp_of(track, release) -> str | None`: the player a Bandcamp track plays in, or None unless `plays_from` is `"bandcamp"`.
- **What counts as playing:** a track that plays from Bandcamp counts everywhere a SoundCloud track does now:
  - the release's tracklist and its `track_count`;
  - its own page, `GET /tracks?ids=`, and `public.track_cards` and `release_cards`;
  - item references (`live`), search, the server copy and the sitemap;
  - the admin's Live and `unplayable`.
- **Its length** is the one staff type, as for a SoundCloud track (the Length field).

**Reads.** Every answer that has `soundcloud_url` gains `bandcamp_url` beside it:
- `PlaysFrom = Literal["upload", "soundcloud", "bandcamp"]`.
- `TrackLine.bandcamp_url: str | None`: the player it plays in when `plays_from` is `"bandcamp"`, else null. `LiveTrack` (`GET /releases/{slug}/{track}`), `TrackCard` (`GET /tracks?ids=`) and `LiveRelease.tracks` (`GET /releases/{slug}`) inherit it.
- **The link's shape** is the page's link with the player's id in its fragment, as embeds reads it: `https://<artist>.bandcamp.com/track/<slug>#bandcamp-track=<id>`, or `…/album/<slug>#bandcamp-album=<id>` for an album's.
- `public.Card.bandcamp_url: str | None` follows the same rule; a release's card takes its first playable track's.
- **Admin answers:**
  - `TrackAudio.plays_from` may be `"bandcamp"`;
  - `TrackAudio.bandcamp_url: str | None` is the track's own player (its field shows it);
  - `FullRelease.bandcamp_url: str | None` is the album's own.

**Writes:**
- **The fields:** `TrackChange` (`PATCH /api/discography/admin/tracks/{track_id}`) and `ReleaseChange` (`PATCH /api/discography/admin/releases/{release_id}`) gain `bandcamp_url: str | None = Field(default=None, max_length=4096)`.
  - It takes what the admin pasted: Bandcamp's embed code, or the link the field shows back.
  - Null or blank clears it.
  - Saving needs `discography.release.manage`, as each save does now.
- `service.bandcamp_player(pasted: str, kind: Literal["track", "album"]) -> str` reads what was pasted:
  - a code (it starts with `<`) goes through embeds' `from_bandcamp_code`;
  - anything else is a link, read by embeds' `recognise`;
  - it must be Bandcamp's, of that kind. Only the link is kept, and nothing in a code runs or loads (embeds reads it by pattern).
- **Anything else** is refused: 422, `discography.not_bandcamp`, on `bandcamp_url`.
  - On a track: "That isn't a Bandcamp track's embed code. On the track's Bandcamp page, choose Share, then Embed, and copy the code."
  - On an album: "That isn't a Bandcamp album's embed code. On the album's Bandcamp page, choose Share, then Embed, and copy the code."

**Web** (`@/modules/discography/public`):
- **The player's items:** `playerItem(track, release): PlayerItem | null` is null for a track that plays from Bandcamp, which audio-player can't play.
  - `playerQueue(release)` leaves those tracks out (§8, 1).
  - A page finds a track in the queue by its key, `discography.track:<id>`, never by its number.
- **New:** `bandcampPlayer(track: Pick<TrackLine, "plays_from" | "bandcamp_url">): string | null`, the link to hand embeds' `EmbedFrame`, or null.
- **The admin, in the boards' words:**
  - **Tracks' editor:** "Bandcamp player" goes under "SoundCloud link", with the hint "Paste the embed code from its Bandcamp page (Share, then Embed). It plays in Bandcamp's own player when the track has no upload or SoundCloud link."
  - **The album's editor:** "Bandcamp player" goes after Summary, with the hint "Paste the album's embed code from Bandcamp (Share, then Embed). Its tracks with no upload or SoundCloud link play in Bandcamp's own player."
  - **Tracks' list:** a Bandcamp track's source says "Bandcamp".
  - **The album's tracks:** the description reads "Each track plays from an uploaded file or a SoundCloud link, else Bandcamp's own player; an upload gets a stream file and a waveform made from it.", and a Bandcamp track's row reads "Bandcamp · 3:49".
  - **AdminMusic's note:** "Tracks play from their uploaded file, or from their SoundCloud link where they have none, else in Bandcamp's own player."
  - **The dashboard's storage note:** "Until both buckets are set, tracks play from SoundCloud links and Bandcamp players only."
- **Discography's own pages** (for a site that keeps its Release and Track pages): a Bandcamp track draws `BandcampPlayer` (`web/components/BandcampPlayer.tsx`, not exported).
  - It's a Listen in embeds' facade words ("Bandcamp", "Plays from Bandcamp, which may set cookies.") that grants `media` and takes its turn through `useExclusive`, then `EmbedFrame`.
  - audio-player starting puts it back to Listen (§8, 2).

### embeds 0.1.2

**`EmbedFrame`** (new in `web/public.ts`, with `EmbedFrameProps = { link: string; words?: string }`) is the provider's `<iframe>` alone, as `Embed` draws it:
- the same sandbox, the same `allow`, the title "<Name> player: <words>", `loading="lazy"` and the same `referrerPolicy`;
- classed by its shape (`mf-embed-frame mf-embed-frame--<shape>`; Bandcamp's is `strip-120`), never by a style;
- it never plays by itself;
- it draws nothing until `media` is granted, and nothing for a link that isn't a player. The page's own Listen is the facade, and it calls `useConsent("media").grant()`.

**`from_bandcamp_code`** (new, Python): `embeds.providers.from_bandcamp_code(code: str) -> tuple[str, str] | None` returns the link and its words. It's the twin of the web's `fromBandcampCode`, and both sides are held to new cases in `tests/providers.cases.json`. `embeds.public` exports it. `fromBandcampCode` stays inside embeds' web, since the admin sends what was pasted.

## 3. Data

The migration is `modules/discography/migrations/discography_0002_bandcamp.py`: revision `discography_0002`, down_revision `discography_0001`, not destructive. Its downgrade drops both columns and the players they hold.

| Table | Column | Type | Null | Default / FK / index |
|---|---|---|---|---|
| `discography_track` | `bandcamp_url` | varchar(500) | yes | none; CHECK `bandcamp_is_track`: `bandcamp_url IS NULL OR bandcamp_url ~ '#bandcamp-track=[0-9]{1,12}$'` |
| `discography_release` | `bandcamp_url` | varchar(500) | yes | none; CHECK `bandcamp_is_album`: `bandcamp_url IS NULL OR bandcamp_url ~ '#bandcamp-album=[0-9]{1,12}$'` |

Access is the routes' permissions, as now. The seed is unchanged.

## 4. Files

- **discography:**
  - backend: `models.py`, `schemas.py`, `service.py`, `public.py`, `refs.py`, `server_copy.py`, `dashboard.py`, and the new migration;
  - web: `player.ts`, `public.ts`, `editing.ts`, `rows.ts`, `pages/AdminTracks.tsx`, `AdminRelease.tsx`, `AdminMusic.tsx`, `Release.tsx`, `Track.tsx`, and the new `components/BandcampPlayer.tsx`;
  - the rest: `openapi.json`, `web/schema.ts`, `module.json` (0.1.5, its summary and `use_when`, and `requires` embeds `^0.1.2`), `MODULE.md`, `CHANGELOG.md`, and tests in `tests/backend`, `contract` and `web`.
- **embeds:** `web/Embed.tsx` (`EmbedFrame` beside `Embed`, sharing its sandbox), `web/public.ts`, `web/embeds.css`, `backend/embeds/providers.py`, `public.py`, `tests/providers.cases.json`, `tests/backend/test_providers.py`, `tests/web/providers.test.ts`, `tests/web/embeds.test.tsx`, `module.json` (0.1.2), `MODULE.md`, `CHANGELOG.md`.
- **Shared:**
  - `docs/decisions/0075-bandcamp-player.md`;
  - `catalog.json`;
  - `docs/progress.json` (step 3's `prs`), then `python -m tools.progress`;
  - `dev plans/README.md`.
  - SPEC: no change.
- **Not touched** (with §8 as recommended): audio-player, featured, media and the kernel.

## 5. Conventions this follows

- `CLAUDE.md`'s Rules and "Two lanes".
- MechFrame's contracts `discography.md` and `embeds.md`, and `audio-player.md` (`useExclusive`).
- Skills `module-contract-lint`, `alembic-multi-module-migrations` and `verify-real-pass`.
- The pattern to copy is the SoundCloud link's path through discography: `soundcloud_link`, its field error, and the Length field.

## 6. Non-goals

- No Bandcamp listens counted: its frame says nothing back.
- No Bandcamp player pasted straight into featured's players (the owner chose Music only, player-sources §8, 4).
- No Spotify player, and nothing fetched from Bandcamp by the server.
- A release's Bandcamp "listen on" link, among its streaming links, stays apart from its player.
- No seeded Bandcamp player (no made-up ids).
- The site's own pages and boards are VM Website's.

## 7. Acceptance

**embeds:**
- **Both sides read codes alike:** the new cases in `providers.cases.json` (an album's code, a track's, a mismatched one, one too long, and something that isn't a code) read the same in Python and TypeScript.
- **`embeds.test.tsx`:** `EmbedFrame` draws nothing before `media`. Once it's granted, it draws one iframe with the sandbox, the title, lazy loading and the `strip-120` class, and no autoplay. It draws nothing for a link that isn't a player.

**discography's backend (`test_service.py` and `test_refs.py`):**
- **The order:** an upload, then SoundCloud, then the track's own Bandcamp player, then the album's, then nothing.
- **What's kept:** a saved code keeps only its link.
- **What's refused:** an album's code on a track, a page link without its player's id, or junk is refused with `discography.not_bandcamp` on `bandcamp_url`; a blank clears it.
- **It's live:** a Bandcamp-only track is in its release's tracks and `track_count`, in `GET /tracks?ids=`, on its own page, `live` in item references, and in the sitemap.
- **Taking the album's player away** takes a track that fell back to it off the site.

**The contract test:** `GET /releases/{slug}` answers `plays_from: "bandcamp"` with `bandcamp_url`, and with `stream_url` and `soundcloud_url` null.

**The migration round trip** passes on an empty and on a seeded database.

**The web:**
- `public.test.tsx`: `playerItem` is null for a Bandcamp track and `playerQueue` leaves it out; `bandcampPlayer` gives the link.
- `discography.test.tsx`:
  - the admin's two fields and their hints;
  - the error under the field;
  - Tracks' "Bandcamp";
  - the Release and Track pages' Listen, then the frame, and audio-player starting puts it back to Listen.

**Gates:** `module-contract-lint`, `python -m tools.validate_schemas`, and `mechframe add` then `mechframe check` on a fresh site. The brand check doesn't apply: nothing is lifted.

**Done when** the site builds the boards' Bandcamp states from these parts and measures them exact at 1440 and 390 (VM Website's check, once this lands).

## 8. Open questions for the owner

1. **A Bandcamp-only track in an album's queue** (Release's dock, the Track page going on through the album). *Recommended:* the queue skips it. audio-player plays the album on without it, and the track still plays in Bandcamp's player from its own row and its own page. Bandcamp's frame can't tell the site when its track ends, so stopping there would end the album at that track every time, and a track playing from its album's player would start at the album's first track. *The other way* (VM Website's suggestion): audio-player stops on it and the dock shows its Bandcamp player. That needs audio-player 0.1.3 to hold an item it can't play, a third module in this PR, cleared with the main lane first, since ask C's video player takes turns with audio-player too.
2. **Taking turns with a frame nothing can pause.** *Recommended:* the site's plan as it stands. The page's Listen claims its turn through `useExclusive`, which pauses audio-player, and audio-player starting calls the page back, which puts the frame back to Listen; unmounting the frame stops it. That's audio-player 0.1.2's public parts unchanged, and discography's own pages do the same. *The other way:* audio-player owns the frame's turn, which needs audio-player to know embeds.
3. **A track with no player of its own plays from its album's.** Bandcamp's frame is then the album's, and it starts at the album's first (or featured) track, not this one. *Recommended:* keep it, as your order says ("else its album's"), and paste a track's own code wherever that track matters. *The other way:* only a track's own player makes it live; an album's player shows on its Release page alone.

## Changes after approval

None.

## Changes as built (discography 0.1.5 and embeds 0.1.2, `claude/mechframe-side-lane-bandcamp-4ebef7`, #174)

None of these changes what was approved:
- `public.ts` also exports `SOURCE` (`discography.track`), so a page finds a track in `playerQueue` by its key.
- `bandcamp_player` keeps one plain form of a link: https, the host in lower case, no trailing slash.
- discography's summary reads "…; tracks play from an upload, SoundCloud or Bandcamp." (a summary is 120 characters at most).
- `remove_audio` keeps a typed length while the track still plays, from SoundCloud or Bandcamp.
- On discography's own pages, the frame takes the focus when it replaces its Listen.
- A Bandcamp-only release hides Play album, and its dock isn't drawn.
