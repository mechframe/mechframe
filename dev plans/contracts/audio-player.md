---
feature: The audio-player module, the site's one player for its own audio: inline bars and a docked bar, a queue, waveforms, one thing playing at a time (YouTube's playlist player included), SoundCloud tracks behind the same controls, and plays counted without keeping anyone's details (Vibrant Mindz step 2, the second of three; the side lane's M9)
status: approved
approved: 2026-11-24 (the owner: "Approve as recommended", the six answers in §8 as recommended)
plan: `docs/plans/vibrant-mindz-backend/backend-plan.md` (§2, 2) and `players-admin.md` ("Front end"); `dev plans/done/2026-11-24-side-lane-m9-audio-player.md`; VM Website's boards `design/site/Main.dc.html` (the Spotlight bar, the hero's Play, the Releases deck, the Videos player), `Release.dc.html` (the docked bar) and `AdminDashboard.dc.html` ("Plays this week")
pr: #149 (audio-player 0.1.0), then discography 0.1.1's own, #151 (§8, 1); decision 0071; migration `audio_player_0001`
---

# Contract: `audio-player`

## 1. Goal

A visitor plays the site's music in players that look like the boards: the Spotlight bar under the hero, the Releases deck, a release page's track rows and the bar docked at its foot. Only one thing plays at a time: starting any of them pauses the others where they are, and stops a YouTube video. A track from an upload plays its stream file with its real waveform; a SoundCloud track plays through SoundCloud's widget behind the same controls. The team sees "Plays this week" on the Dashboard. audio-player never decides what plays: a page hands it a queue.

## 2. Interfaces

### audio-player 0.1.0 (requires the kernel only, §8, 1)

**Web, `@/modules/audio-player/public`:**

```ts
export type PlayerItem = {
  key: string;                 // "<source>:<id>", unique in a queue
  title: string;
  line: string;                // the words under the title: "Catalyst, petro and J Tone"
  cover?: { src: string; alt: string };
  stream_url?: string;         // a file the browser plays; else
  soundcloud_url?: string;     // a SoundCloud track or playlist
  duration_ms?: number;
  peaks?: readonly number[];   // 0 to 255; without them, a made-up shape that's always the same for its key
  path?: string;               // its page
  count?: () => void;          // called once, when it's been heard long enough (§8, 2)
};
export type PlayerState = "idle" | "loading" | "playing" | "paused" | "failed";
export function usePlayer(): {
  queue: readonly PlayerItem[]; index: number; item: PlayerItem | null; state: PlayerState;
  position_ms: number; duration_ms: number | null; volume: number;
  play(queue: readonly PlayerItem[], index?: number): void; toggle(): void; pause(): void;
  next(): void; prev(): void; seek(ms: number): void; setVolume(volume: number): void;
};
export function useExclusive(pause: () => void): () => void;  // gives `claim`, for a player that isn't this module's
```

Components, each styled by tokens only:
- `<PlayButton queue index label />`: "Play {label}" or, while that item plays, "Pause {label}". The Release board's rows and Play album, and the hero's "Play Catalyst".
- `<Waveform item bars={150} />`: the played and unplayed layers, as the Spotlight draws them. It's a `slider` ("Seek", the arrows move 5 seconds, Home and End), its `aria-valuetext` "1:12 of 3:40".
- `<PlayerBar queue label>{children}</PlayerBar>`: the Spotlight's bar. A region named by `label` ("Spotlight single") holds the cover, the title and line, Previous, Play and Next, and the waveform. `children` sits at its end ("Full album"). It follows the Spotlight's layout under 600px.
- `<PlayerDock label />`: the Release board's docked bar, a region named `label` ("Player"). It holds the cover, the title and line, Previous, Play and Next, a thin progress slider, "Track 2 of 15", Queue (the queue, each row playable) and Volume (a slider, remembered in this browser). Under 700px the progress, Queue and Volume hide. A page draws it in `<AfterFooter>`.
- `<Equalizer playing />`: the three bars beside the row that plays; still under reduced motion.

**How the player behaves:**
- **One element:** there's one audio element and one hidden SoundCloud widget for the whole app, made when first needed, so audio-player's own players can never play over each other.
- **One thing at a time:**
  - `play` pauses whatever else had the floor. A paused item keeps its place and resumes from it.
  - `useExclusive(pause)` gives `claim`. A YouTube player calls `claim` as it starts: `<VideoPlaylist onPlay={claim} ref={videos} />`, with `pause` calling `videos.current?.pause()`. That pauses the audio, and starting audio calls `pause`. No change to `embeds` (its contract §2).
- **The queue:**
  - Previous and Next wrap round the queue, as on the boards, and keep playing or paused.
  - At a track's end, with `autoplay_next` on, the next one plays. The end of the last one stops.
  - A track that fails to load says "This track can't play right now" and, with `autoplay_next` on, moves on.
  - A page move stops it all (§8, 4).
- **Counting:** an item's `count` is called once per play-through, once `count_after_seconds` of it has really been heard (time skipped by seeking doesn't count), or at its end if it's shorter (§8, 2).
- **The lock screen and the announcements:** the Media Session gets the title, line, cover, play, pause, previous and next. A polite status line says "Now playing: {title}" when the track changes.
- **SoundCloud** (§8, 5):
  - The first press of Play on a SoundCloud item, while `media` isn't granted, grants it, as an embed's Play does (SPEC 8).
  - Then the Widget API (`https://w.soundcloud.com/player/api.js`) loads, and the widget plays behind the controls, showing the generic waveform.
  - A SoundCloud item always shows "on SoundCloud" by its title, linked to its page there.
  - A playlist plays as one item, the widget running through its tracks.

**HTTP** (`/api/audio-player`, behind `require_module("audio-player")`): `GET /settings` (public) → `PlayerSettings {autoplay_next: bool, count_after_seconds: int}`, with `Cache-Control: public, max-age=60`. The player reads it once per page. That's the only route.

**Backend, `audio_player.public`** (for modules that list `audio-player` in `requires`):

```python
async def count(db: AsyncSession, request: Request, *, source: str, item_id: uuid.UUID) -> bool
async def forget(db: AsyncSession, source: str, item_ids: Iterable[uuid.UUID]) -> None
async def plays(db: AsyncSession, source: str, *, since: date, until: date) -> dict[uuid.UUID, int]
async def add_daily(db: AsyncSession, source: str, item_id: uuid.UUID, day: date, plays: int) -> None  # for a seed
```

- **`count`** is called by the source module's own route, which has checked the item. `source` is `<module>.<type>`, such as `discography.track`.
- **Who's listening:** the listener is an HMAC-SHA256 of the kernel's `client_address(request)` and the `User-Agent`, under the day's random salt. Neither the address nor the browser's name is stored.
- **Counted once:** a listener counts once per item per day (UTC). The second time answers False, and nothing changes.
- **Its transaction:** `count` writes in the caller's transaction; it never commits.

**Settings** (`Settings`, unchanged keys):
- `autoplay_next` (bool, true);
- `count_after_seconds` (int, 30, from 5 to 120).

The boards don't draw them, so they go on Settings › Site as an `admin.settings.section`, "Player": "Play the next track when one ends" and "Count a play after (seconds)".

**The job** `audio-player.prune` (`15 3 * * *`, UTC) deletes the dedupe rows and salts of days before today, and daily totals older than two years (§8, 3).

**CSP:** `("frame-src", "https://w.soundcloud.com", "media")` and `("script-src", "https://w.soundcloud.com", "media")`.

**Permissions and events:**
- **Permissions:** none. The scaffold's `audio-player.stats.read` goes, since the card is discography's (§8, 3).
- **Events:** none emitted or heard.
- **Hooks:** none. It holds no personal data, so no export or erase; and it has no public pages.

### discography 0.1.1 (its own PR, once audio-player is in)

- **Requirements:** `requires` gains `audio-player ^0.1`.
- **Counting:** `POST /api/discography/tracks/{id}/plays` (public, `rate_limit("60/1h")`) answers 204 whether it counted or not. It counts only a live, playable track, through `audio_player.public.count`, with `source` `discography.track`.
- **The Release page:**
  - Play album and each row's play are `PlayButton`s, the release's playable tracks the queue.
  - The row that plays shows `Equalizer`.
  - `PlayerDock label="Player"` sits in `<AfterFooter>`, as the board draws it.
- **The Track page** draws a `PlayerBar`.
- **While audio-player is off** (`useModuleEnabled`), both pages keep today's `Plays`.
- **`web/public.ts`** gains `playerItem(track, release)` and `playerQueue(release)`, so a site's homepage builds its Spotlight and deck queues from discography's answers, counting included.
- **Deleting** a track or a release calls `audio_player.public.forget` in the same transaction.
- **The Dashboard card** (`admin.dashboard.widget`, for `discography.release.manage`) is drawn as AdminDashboard draws it:
  - "Plays this week" holds the last 7 days' total and the change on the 7 before ("Up 18% on last week").
  - It names the leading track ("Gather Around leads") and links to Music.
  - With none yet, it reads "No plays yet this week".
- **The seed** gives its seeded tracks two weeks of daily plays, through `add_daily`.

## 3. Data

Branch `audio-player` (the module's id, as every branch is labelled), `audio_player_0001`, `depends_on` `kernel_0002` as contact's and campaigns' do; no foreign keys.

| Table | Columns |
|---|---|
| `audio_player_salt` | `day` (date) PK, `salt` (bytea, 32 random bytes): one per day, made by its first play (`ON CONFLICT DO NOTHING`) |
| `audio_player_play` | `day`, `source` (≤ 40), `item_id` (uuid), `listener` (char 64, the hex HMAC); PK all four. Kept to the end of its day: it's only there to count each listener once |
| `audio_player_play_daily` | `source`, `item_id`, `day`, `plays` (int, CHECK ≥ 0); PK (`source`, `item_id`, `day`), index (`source`, `day`). A counted play adds 1 in the same transaction. Kept two years |

No user ids, addresses or browser names anywhere: `data_hooks` stay false.

## 4. Files

- **`modules/_audio-player/` becomes `modules/audio-player/`**, its `module.json` and `MODULE.md` saying what's agreed here.
  - `backend/audio_player/`: `__init__` (`CSP`), `models`, `schemas`, `service` (the salt, the listener, the count), `router`, `public`, `jobs`. `server_copy.py` and `events.py` go: it has no pages and no events.
  - `web/`: `module.web.ts` (the settings section), `api.ts`, `public.ts`, `store.ts` (the element, the queue, the claims, counting), `soundcloud.ts` (the Widget API), `components/` (the five above and `SettingsSection`), `player.css`.
- **The kernel:** `client_address` joins `kernel/__init__.py` and SPEC 6's table, since the listener needs the address behind Railway's proxy, as the rate limits read it. It's one line, and the main lane hears of it first.
- **The harness:** an e2e page with a `PlayerBar`, a `PlayerDock` in `AfterFooter` and a `VideoPlaylist` on a fake YouTube API, playing a WAV the harness serves.
- **Generated again:** `catalog.json`, OpenAPI and `schema.ts`, host variables, `progress.json`.
- **Decision 0071:** a generic player that modules hand items to, and plays counted without personal data.
- **discography 0.1.1:** `module.json`, `router`, `service` (the deletes), `dashboard`, `seed`, `web/pages/Release.tsx` and `Track.tsx`, `web/public.ts`, `web/widgets/PlaysCard.tsx`, tests, `CHANGELOG.md`.

## 5. Conventions this follows

- SPEC 6 to 8 and 10.
- The skills `mechframe-module-extractor`, `alembic-multi-module-migrations` and `module-contract-lint`.
- `discography` for the layout.
- `embeds` (decision 0060) for the consent facade and `VideoPlaylist`'s handle.
- `after-footer.md` for the dock.
- The memories `race-tests-that-really-race` (the salt's first play) and `react-render-time-sync-traps`.

## 6. Non-goals

- **What plays:** no queue the listener builds, no shuffle, repeat, speed or downloads.
- **Playback across pages** (§8, 4).
- **Pausing the players inside posts and pages:** embeds' iframes have no API there.
- **The homepage's Spotlight bar, hero button and album deck as finished components:** they're the site's code, built from these parts. Slots and placements are `featured`'s.
- **A stats page, charts, per-track columns, date ranges or exported plays:** the boards draw only the card.
- **Leaving out the team's own plays:** each person counts once a track a day anyway.
- **Keyboard shortcuts for the whole page,** which would fight scrolling.
- **Tagged previews** (licensing, step 6), and asking SoundCloud anything beyond its widget.

## 7. Acceptance

- **Backend:**
  - one listener counts once per item per day;
  - another address or browser counts again, and so does the next day;
  - two first plays of a day at once make one salt (a real race, checked with a mutant);
  - `forget` and the prune;
  - no row holds an address or a `User-Agent` (a test searches every column for them).
- **HTTP:** `/settings` is public and follows a save, with a 404 while the module is off.
- **Web (Vitest), the store:**
  - starting one item pauses another, which resumes where it was;
  - `claim` pauses the audio, and starting audio calls the video's `pause`;
  - wrapping, the end of an item, the end of the queue;
  - `count` once after 30 s heard, never for seeking past, and at the end of a short track;
  - a page move stops it;
  - a failed stream moves on;
  - SoundCloud on a fake `SC.Widget`: Play grants `media`, then plays, with the credit shown;
  - the Media Session.
- **Web, the components:** in both themes at 1440 and 390, axe clean; the waveform's keys; nothing moves under reduced motion.
- **E2E:**
  - on the harness page, the WAV really plays, and starting the bar pauses the dock's item and the video;
  - the dock rides the window's foot;
  - one region per player, each named.
- **discography 0.1.1:**
  - the count route's access, its 204 for a draft or a track that can't play with nothing counted, and its 429;
  - the card's figures;
  - the Release page with its dock, in both themes;
  - with audio-player off, the native player.
- **Gates:** `validate_schemas`, `module-contract-lint`, then on a fresh site `mechframe add` media, embeds, audio-player and discography, and `mechframe check`.
- **Your live check:** a SoundCloud track and an upload play from the bar in Safari on an iPhone and in a desktop browser (§8, 5).

## 8. Open questions for the owner

1. **Which way the requirement runs.**
   - *Recommended:* audio-player needs only the kernel, and a module that plays through it requires it. discography 0.1.1 does, in a second, small PR.
   - That's how the scaffold describes it ("modules hand it items"), and the roadmap's `radio` and `podcast` will require it too. It's also the only way discography's own Release page gets the drawn dock without a new kernel slot.
   - The count then goes through discography's route, which checks the track, and the Dashboard card is discography's, since it names a track and links to Music.
   - *The other way:* audio-player requires discography, as this lane's prompt assumed, counting and naming tracks through `track_cards`. That's one PR. But discography's own pages then can't use the player without a new kernel slot, and `radio` or `podcast` would have to bring discography along.
2. **What counts as a play.**
   - *Recommended:* 30 seconds really heard (the setting, 5 to 120), or the whole track when it's shorter.
   - Each listener counts once per track per day, so replays and reloads don't pad the number.
   - The listener is a hash under a salt that changes daily and is deleted with the day, so nothing that identifies anyone is kept, no cookie is set, and no consent is needed.
   - *The other way:* every 30 seconds heard counts, replays too, as Spotify counts streams, held back only by the rate limit.
3. **Whether stats are kept daily.**
   - *Recommended:* one total per track per day, kept two years. The card needs 14 days; two years leaves room for a stats page later.
   - The card is the only place plays show, as the boards draw it.
   - *The other way:* weekly totals only, which the card can still draw but a later stats page couldn't break down.
4. **Whether the queue survives a page move.**
   - *Recommended:* no, as the boards draw it. The Release page's dock is the page's own, drawn in `AfterFooter`, and starts paused. No other board draws a bar that stays.
   - A page move stops the music, and the next page starts fresh.
   - *The other way:* the player keeps going. The site's own footer then draws `PlayerDock` on every page, the dock comes off the Release page, and a new board is needed for where it sits on the homepage.
5. **Whether a SoundCloud track plays in the widget or opens SoundCloud.**
   - *Recommended:* in the widget, hidden behind the site's controls, as `players-admin.md` plans. Catalyst, the spotlight's placeholder, is SoundCloud-only.
   - SoundCloud's developer terms ask an app that doesn't show their widget to credit SoundCloud and the creator and link back (developers.soundcloud.com/docs/api/terms-of-use, /docs/api/buttons-logos). Hence the "on SoundCloud" link by its title, which the boards don't draw.
   - Some browsers, Safari on iPhones above all, may not let a page start a hidden player's sound. If your iPhone check shows that, the widget shows itself in the bar for that track, for its own Play.
   - *The other ways:* SoundCloud's own player always shown in the bar for a SoundCloud track, in place of the waveform; or "Listen on SoundCloud", leaving the site.
6. **What's added beyond the boards.** *Recommended:* all of it. Each is small, and most are for keyboard and screen-reader use.
   - seeking on the waveform and the dock's progress, with the time read out to a screen reader;
   - the dock's Queue and Volume working (the board draws them with nothing behind them);
   - the phone's lock-screen controls;
   - "Now playing" said aloud when the track changes;
   - the "on SoundCloud" credit;
   - the two settings on Settings › Site.

## Changes after approval

None yet.

## Changes as built (audio-player 0.1.0, `feat/audio-player`)

- **`PlayerState` gains `blocked`:** a browser wouldn't start the hidden widget, so SoundCloud's own player shows for its Play (§8, 5). Its note reads "Press Play in SoundCloud's player to start it."
- **The parts take a little more than §2 named:**
  - `PlayerDock` takes the `queue` it starts while nothing plays (the release's tracks), as well as its `label`. Until something plays, it shows that queue's first, and its Previous does nothing.
  - `PlayerBar` takes `previousLabel` and `nextLabel` ("Previous spotlight track"), and `bars`.
  - `PlayButton` takes `className` and its own `children`, its name staying "Play {label}".
  - A queue of one draws no Previous or Next.
- **A shorter track counts once 90% of it is heard,** as "nearly all of it": a seek to its end doesn't count.
- **The job is `audio-player.prune`;** the scaffold's `rollup_plays` went, since a counted play adds to its day's total at once.
- **The hooks read the player from `PlayerContext`** when one is given (the tests' own, on fake outputs), else the app's one.
- **The e2e page is the harness's `/player.html`.** Its axe check leaves out embeds' playlist, whose "Prev" is named "Previous video", which axe's `label-content-name-mismatch` refuses. That's embeds' to fix, and is reported in the PR.

## Changes as built (the reviews of #149)

- **SoundCloud waits for consent unloaded** (Codex). An item the queue reaches without `media` granted isn't loaded at all, since loading it already reaches SoundCloud. Play loads it, from its start, once allowed. The track that played stops when consent is gone and Next moves to another (CodeRabbit).
- **The consent the player reads is one value for the app,** `configure({ mediaGranted })`. Every part sets it from the kernel's consent, and a press that grants it sets it at once, whichever part was pressed (CodeRabbit).
- **A SoundCloud playlist has one timeline** (CodeRabbit), going beyond §2's "plays as one item, the widget running through its tracks":
  - its tracks' lengths add up;
  - the place is the tracks before plus where the playing one is;
  - a seek into another track skips to it and seeks once it plays;
  - while the widget hasn't given every track's length, it runs a track at a time, each with its own length, and still ends only after its last track (the track count is kept apart);
  - a length that's one track's, not the whole item's, never makes it "short" for counting. The item's own `duration_ms` does, when its module gives one; else it counts after the setting's seconds.
- **The widget's answers:** a getter's answer for an earlier load is dropped, and FINISH reads the track it knows. The same link loaded again starts over. A Widget API that failed to load is asked for again (Codex).
- **The dock's Escape gives focus back** to Queue or Volume when the panel held it (CodeRabbit).
- **The settings route answers through `answer()`,** as SPEC 7 asks of a route that sets a header. A source is refused unless it `fullmatch`es `<module>.<type>` (CodeRabbit).

## Changes as built (discography 0.1.1, #151)

The "discography 0.1.1" block is built as §2 says. What it didn't name is in discography's contract, "Changes as built (0.1.1)": the card's read and its words, Play album's name, and the seed's plays dated by the real clock. One thing reaches back here: **"While audio-player is off" can't happen while the site runs,** since the kernel turns discography off with it (discography requires it). The pages keep `Plays` only for a modules read that says it's off. No change to audio-player.

