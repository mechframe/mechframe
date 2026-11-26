# Changelog: audio-player

## 0.1.1

- The Settings section ("Player" on Settings › Site) spans its card, as the other sections do. Its 640px cap is gone, and the card itself stops at 760px. At 1440, its hint fits on one line, as the board draws it.

## 0.1.0

- The player, built to its approved contract (`dev plans/contracts/audio-player.md`; decision 0071; migration `audio_player_0001`): one audio element and one hidden SoundCloud widget for the app, the queue, one thing playing at a time with `useExclusive` for embeds' YouTube player, and a page move stopping it.
- `PlayButton`, `Waveform` (a Seek slider for what plays), `PlayerBar` (the Spotlight's), `PlayerDock` (the Release board's, with its queue and volume) and `Equalizer`, styled by tokens only.
- SoundCloud in the consent category `media`, its Play the visitor's consent, "on SoundCloud" by its title, and the widget itself when a browser won't start it hidden.
- Plays counted once per listener per item per UTC day, the listener an HMAC under a daily salt deleted the next day, daily totals kept two years (`public.count`, `forget`, `plays`, `add_daily`; the job `audio-player.prune`).
- `GET /api/audio-player/settings`, and the section "Player" on Settings, Site.
- The scaffold's `audio-player.stats.read`, `rollup_plays`, `server_copy.py` and `events.py` went.
