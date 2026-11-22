# embeds

YouTube, SoundCloud, Spotify and Bandcamp players from a pasted link, and a YouTube playlist player for a site's own pages. The contract is `dev plans/contracts/embeds.md`.

## What it does

A writer clicks Embed in any editor (pages', blog's, any module's `MarkdownEditor`), pastes a link and, if they like, the words to show under the player. For Bandcamp they paste its embed code from Share, then Embed, since Bandcamp has no other way to name its player. The dialog says what it found ("A playlist on YouTube"), or that the link will stay a plain link, and puts `[words](link)` in a paragraph of its own.

**On the site,** every `Prose` draws a paragraph that holds only such a link as that provider's player (the slot `prose.embed`, decision 0060). Until the visitor plays, it's the site's own facade: the provider's name, the words, Play (or Listen), and "Plays from YouTube, which may set cookies." Nothing loads from the provider until then. The click grants the consent category `media` (hook 6) for the whole site, then the provider's player loads:
- in a sandbox (scripts, same origin, pop-ups, presentation; never forms, downloads or our page's navigation);
- lazily, named by what it holds, and never playing by itself, except a YouTube video just after its Play.

The words sit under the player, linked to the original, which still works if a player is refused. A link in a sentence, a link to another host, and every link on a site without `embeds` stay as the server drew them, and the server's copy never changes.

**`VideoPlaylist`** plays a list of YouTube videos in one player (VM Website's `videos-player.md`):
- a 16:9 stage and its bar, the list beside it at the stage's height, stacked under 980px;
- the facade first, with the site's poster, and YouTube's thumbnails only once `media` is granted (the owner, 2026-11-22);
- the IFrame API on `youtube-nocookie.com`, rolling on to the next video with Autoplay on, and stopping after the last;
- Prev and Next that wrap, and a row's click that plays it;
- `onPlay`, and a handle's `pause()`, for `audio-player`'s one-thing-at-a-time store (step 2).

## Use when / avoid when

Use it when writers put videos and tracks from those four providers in pages and posts by pasting a link, when nothing from them should load before a visitor plays, and when a page plays a list of YouTube videos in one player. Avoid it for the site's own audio and video files, or previews that must be tagged (`audio-player`, `media`), and for videos only members or buyers may see: a provider's player can't keep a video private. The list a homepage player plays is `featured`'s; it draws this module's `VideoPlaylist`.

## What it adds

| Kind | Items |
| --- | --- |
| Routes | None |
| Tables | None |
| Slots | `editor.tools` (the Embed button), `prose.embed` (the players) |
| Permissions | None: anyone who may edit a text may embed in it |
| Events | emits: none; listens: none |
| Notifications | None |
| CSP, all in `media` | `frame-src` `https://www.youtube-nocookie.com`, `https://w.soundcloud.com`, `https://open.spotify.com`, `https://bandcamp.com`; `script-src` `https://www.youtube.com` (the IFrame API); `img-src` `https://i.ytimg.com` (thumbnails) |

**For a site's own pages** (`@/modules/embeds/public`, decision 0057):
- `Embed` (`{link, words?}`): the player above;
- `VideoPlaylist` (`{items, autoplay?, onPlay?, ref?, label?}`), each item `{url, title, poster?}`, any YouTube link or a bare id;
- `recognise(link)`, `wordsFor(embed, words)` and `youtubeId(link)`.

**For another module's backend** (`embeds.public`, with `embeds` in its `requires.modules`): `recognise(link)` and `words_for(embed, words)`, the same reading of a link, for a place that can't hold a player, such as `campaigns`' emails.

## Settings and env vars

None.

## Install notes

`mechframe add embeds`, nothing else: no keys, no accounts. A site that sets CONSENT_MODE `off` shows the players at once, never playing by themselves.

## Extension points

A provider is one more entry in `backend/embeds/providers.json` and its twin `web/providers.json` (kept equal by the tests), its player's host in `CSP`, and its cases in `tests/providers.cases.json`, which the backend and the web both answer.

## Known limits

- Four providers: YouTube, SoundCloud, Spotify and Bandcamp. No oEmbed lookups: a player is built from the link alone.
- Every provider's host is in the CSP while the module is on; there's no switch per provider.
- A player in text can't be paused from outside, so "one thing plays at a time" covers only `VideoPlaylist`, through `onPlay` and `pause()`, once `audio-player` arrives (step 2).
- An email can't hold a player: `public.py` gives `campaigns` the link and its words for a card instead.
- Bandcamp needs its embed code, since it has no public way to look a link up.

## Source and license

Lifted from VybeSite at `2416bc1`: `backend/app/services/embeds.json` and `embeds.py`, and `frontend/src/lib/embeds.ts`, `embeds.cases.json`, `components/MediaEmbed.tsx`, `EmbedPicker.tsx` and `MarkdownParagraph.tsx`. Proprietary, as `module.json`'s `source` says.
