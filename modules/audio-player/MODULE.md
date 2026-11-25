# audio-player

One player for the site's own audio: a bar inline in a page, a bar docked at the window's foot, a queue and waveforms, only one thing playing at a time (embeds' YouTube player included), SoundCloud tracks behind the same controls, and plays counted with nothing kept that identifies anyone. It never decides what plays: a module hands it items. The contract is `dev plans/contracts/audio-player.md`; decision 0071 records why the requirement runs from the source module to the player, and how plays are counted.

## What it does

A module that plays audio lists `audio-player` in `requires` and hands the player `PlayerItem`s: a key, a title and its line, a cover, a stream file or a SoundCloud link, a length, waveform peaks, its page, and a `count` the player calls once the item has been heard long enough. discography 0.1.1 is the first.

- **One player for the app:** one audio element and one hidden SoundCloud widget, each made the first time it's needed. Starting anything pauses whatever else played, which keeps its place and resumes from it. Another kind of player takes turns through `useExclusive`: embeds' `VideoPlaylist` calls its `claim` as a video starts, and its `pause` is called when audio starts.
- **The queue** is whatever the page hands it. Previous and Next wrap round it, keeping it playing or paused. At a track's end, with `autoplay_next` on, the next one plays; the last one stops. A track that can't load says "This track can't play right now" and moves on. A page move stops it all: the player plays only while a part of the page that started it is drawn.
- **SoundCloud:** pressing Play on a SoundCloud item grants the consent category `media`, as an embed's Play does, then loads SoundCloud's Widget API and plays the widget behind the site's controls, over a made-up waveform. The item says "on SoundCloud", linked back, as SoundCloud's terms ask of a player that hides its widget. A browser that won't start a hidden widget gets the widget itself, for its own Play. A playlist plays as one item.
- **Counting:** an item's `count` is called once a play-through, after `count_after_seconds` really heard (seeking past doesn't count), or nearly all of a shorter track. The source module's route then calls `public.count`, which counts each listener once per item per UTC day. The listener is an HMAC of the visitor's address and browser name under that day's random salt, and both go the next day; only daily totals stay, for two years. No cookie is set and no consent is needed for it.
- **For everyone:** the waveform and the dock's progress are sliders ("Seek", the arrows move 5 seconds, Home and End) read out as "1:12 of 3:40"; the lock screen gets the title, line, cover and its four buttons; a polite status line says "Now playing: …" once for the app; the row's equalizer stands still under reduced motion.

## Use when / avoid when

Use it when the site plays its own audio (albums, singles, readings) that another module holds, when several players on one page, a YouTube player among them, must never play over each other, or when the team wants play counts without a cookie. Avoid it when the audio only lives on SoundCloud or Spotify and a provider's own player is enough: that's `embeds`. Avoid it when music must keep playing while a visitor moves between pages: this player stops on a page move.

## What it adds

- **Routes**, under `/api/audio-player`: `GET /settings` (public): `{autoplay_next, count_after_seconds}`, `Cache-Control: public, max-age=60`. Plays aren't counted here: the source module's own route counts them.
- **Public pages:** none. **Admin pages:** none; Settings, Site gains the section "Player" (`admin.settings.section`).
- **Web, `@/modules/audio-player/public`:** `usePlayer`, `useExclusive`, `PlayButton`, `Waveform`, `PlayerBar` (the Spotlight's bar, a region named by `label`), `PlayerDock` (the Release board's, for `<AfterFooter>`, with Queue and Volume; under 700px those and the progress hide), `Equalizer`, `clock`, and the types `PlayerItem`, `PlayerState` and `PlayerControls`.
- **Backend, `audio_player.public`:** `count(db, request, *, source, item_id) -> bool`, `forget(db, source, item_ids)`, `plays(db, source, *, since, until) -> dict[UUID, int]` and, for a seed, `add_daily(db, source, item_id, day, plays)`. A `source` is `<module>.<type>`, such as `discography.track`; each writes in the caller's transaction and never commits.
- **Tables:** `audio_player_salt` (the day's salt), `audio_player_play` (today's counted listeners) and `audio_player_play_daily` (each item's total per day), migration `audio_player_0001`, after the kernel's `kernel_0002`. No foreign keys.
- **The job** `audio-player.prune` (daily, 03:15 UTC): yesterday's salts and listeners, and daily totals past two years.
- **CSP:** `frame-src` and `script-src` `https://w.soundcloud.com`, both in the consent category `media`.
- **Permissions, events and hooks:** none. The scaffold's `audio-player.stats.read` went: the Dashboard's card is the source module's.

## Settings and env vars

- `autoplay_next` (bool, default `true`): play the next track in the queue when one ends.
- `count_after_seconds` (int, default `30`, from 5 to 120): seconds really heard before a play counts.

No env vars.

## Install notes

`mechframe add audio-player`. A module that plays through it requires it, so `mechframe add discography` brings it in. A site's own page draws the parts from `public.ts`: the homepage's Spotlight as a `PlayerBar`, a release page's dock as a `PlayerDock` inside `<AfterFooter>`, and a YouTube playlist taking turns:

```tsx
const videos = useRef<VideoPlaylistHandle>(null);
const claim = useExclusive(() => videos.current?.pause());
<VideoPlaylist ref={videos} onPlay={claim} items={videoItems} />
```

## Extension points

- **Backend `public.py`:** `count`, `forget`, `plays`, `add_daily`, for a source module.
- **Web `public.ts`:** the hooks and parts above; the hooks take the player from `PlayerContext` (in `hooks.ts`) when one is given, as the module's tests do.
- **Settings:** the two above.

## Known limits

- **No playback across pages,** no listener-built queue, shuffle, repeat or speed.
- **Players inside posts and pages** (embeds' iframes) aren't paused: they have no API there.
- **A SoundCloud playlist** shows the widget's current track's place, not the whole playlist's.
- **A day is a UTC day:** "Plays this week" counts seven of them.
- **Each person counts once a track a day,** the team's own listening included.

## Source and license

New code for MechFrame, proprietary (decision 0008).
