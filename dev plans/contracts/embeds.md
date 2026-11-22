---
feature: The embeds module, players from a pasted link and the YouTube playlist player (Vibrant Mindz step 1; M5's second job)
status: approved
plan: `docs/plans/vibrant-mindz-backend/extraction/embeds.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M5); `docs/plans/vibrant-mindz-backend/videos-player.md` and `players-admin.md` (copies of VM Website's specs); `docs/plans/vibrant-mindz-module-plan.md` §4
approved: 2026-11-22, §8, 1 as recommended (the owner: "As recommended")
pr: #127, after `contact`'s (#125)
---

# Contract: `embeds`

## 1. Goal

A writer pastes a YouTube, SoundCloud, Spotify or Bandcamp link into a page or a post with the editor's Embed button. The site draws it as that provider's player, on its own line, under the writer's words. Nothing loads from the provider until the visitor clicks Play on a facade drawn by the site (hook 6, `media`). The click is the consent, so visitors see no new banner (decision 0052). The module also gives sites the YouTube playlist player for Vibrant Mindz's Videos section and `/videos` page.

Lifted from VybeSite (`services/embeds.json`, `services/embeds.py`, `lib/embeds.ts`, `components/MediaEmbed.tsx`, `components/EmbedPicker.tsx`, `components/MarkdownParagraph.tsx`, #103). VybeSite draws Markdown in the browser. MechFrame makes it HTML on the server and the kit's `Prose` draws it (decision 0055), so the players come in through two new kit slots (§2, "The kernel's addition").

## 2. Interfaces

**The providers:** `modules/embeds/providers.json` is VybeSite's `embeds.json` as it is. It lists each provider's hosts, its kinds (a YouTube video, short or playlist; a SoundCloud track or set; a Spotify track, episode, album, playlist, artist or show; a Bandcamp album or track), each kind's player address, shape and words ("A video on YouTube"), and the iframe's `allow`. The server and the browser both read this one file. `providers.cases.json` holds the links both must agree on, each with what it gives or `null`. The player's address is built from the link alone, so nothing asks a provider anything. Bandcamp has no public way to look a link up, so its player's id rides in the link's fragment, written once from Bandcamp's own embed code: `https://artist.bandcamp.com/album/slug#bandcamp-album=1234567`.

**No routes, tables, settings or permissions.** Anyone who may edit a page's or a post's text may embed in it.

**CSP** (`__init__.py`), all in the consent category `media`, so none of it loads before a visitor plays:
- `frame-src`: `https://www.youtube-nocookie.com`, `https://w.soundcloud.com`, `https://open.spotify.com`, `https://bandcamp.com`;
- `script-src`: `https://www.youtube.com`, the IFrame API the playlist player needs;
- `img-src`: `https://i.ytimg.com`, YouTube's thumbnails (§8, 1).

**The players in text** (the `prose.embed` slot): a paragraph that holds only a link that `providers.json` recognises becomes `<Embed>`. That's a figure: inside `<ConsentGate category="media">`, the facade until consent, then the provider's iframe. The writer's words sit under it as a link to the original, which still works if a player is refused, and is the backlink SoundCloud's and Spotify's terms ask for.
- **The facade:** the site's own frame in the player's shape, with the provider's name, the writer's words, a Play or Listen button ("Watch on YouTube" as the board says it), and the line "Plays from YouTube, which may set cookies." Its click grants `media` and starts the player. A bare link's words are the kind's own.
- **The iframe** is VybeSite's: lazy, `referrerpolicy="strict-origin-when-cross-origin"`, its sandbox (scripts, same origin, pop-ups, presentation; never forms, downloads or our page's navigation), the provider's `allow`, a title naming what it holds (WCAG H64), and never playing by itself (WCAG 1.4.2), except after the facade's click.
- The shape is a class (`--video` 16:9, `--short` 9:16, `--strip-<height>`), never a style, for the CSP.
- A link in a sentence, a link to another host, or a paragraph with an image stays as the server drew it. So does every link on a site without `embeds`, and the server copy, so crawlers see the link.

**The editor's Embed button** (the `editor.tools` slot): after the kit's buttons, in every `MarkdownEditor` (pages', blog's, and any later module's). It opens a dialog with one field, "Paste a link from YouTube, SoundCloud, Spotify or Bandcamp", and a second, "Words under the player (optional)". As the link is pasted, the dialog says what it found ("A playlist on YouTube"), or "We can't play that link. It will stay a plain link." For Bandcamp it asks for the embed code from Bandcamp's Share → Embed, as VybeSite's `EmbedPicker` does. Insert puts `[words](link)` in a paragraph of its own through the editor's `insert`, so Ctrl Z takes it back.

**`web/public.ts`** (decision 0057, `@/modules/embeds/public`):
- `recognise(link)`: the embed or `null`, for a site's own code.
- `<Embed link words>`: the player above, for a site's own pages.
- `<VideoPlaylist items autoplay? onPlay? ref>`: the YouTube playlist player of `videos-player.md`. `items` are `{url, title, poster?}`, any YouTube link or a bare id. It draws the board's layout: a 16:9 stage with its control bar, and a 380px list beside it that scrolls at the stage's height, stacking under 980px. It works the way the spec says:
  - The facade comes first, with the poster or thumbnail, the title and a big Play.
  - The IFrame API loads on the first Play, on `youtube-nocookie.com`.
  - At the end of a video, with Autoplay on, the next one plays and the highlight moves.
  - A row's click plays it; Prev and Next wrap; Autoplay is a switch (`aria-pressed`, on by default) that never restarts what's playing.
  - The current row has `aria-current="true"` and the moving equalizer while it plays, still under reduced motion.
  - `onPlay` and the handle's `pause()` are how `audio-player`'s one-thing-at-a-time store (step 2) will drive it, with no change here.

**`public.py`:** `recognise(link) -> Embed | None` and `words_for(embed, words)`, from the same file, for `campaigns`' emails. An email can't hold a player, so it shows a card with "Watch on YouTube" or "Listen on Spotify".

**The kernel's addition** (decision 0060, in this PR): two web slots in SPEC 8's table, read by the kit through a context that `mount` fills. The kit reads no slots itself, so it still works alone.
- `editor.tools`: `{id, lazy, permission?}` parts given `{editor: MarkdownTools}`. The kernel can fill it with entries of its own, as well as the modules that are on. `MarkdownEditor` draws, in order: its own buttons, the page's `tools`, the kernel's entries, then the modules' entries. **Blog's AI PR (decision 0058) registers its writing help here as a kernel entry**, so the AI PR needs no change to `MarkdownEditor.tsx` (the main lane, 2026-11-22).
- `prose.embed`: `{claims(href): boolean, lazy}`. Once `Prose` has drawn the server's HTML, each paragraph that holds only one link an entry claims gives way to that entry's part. That part is given `{href, words}` and drawn in place through a portal.

## 3. Data

None. The links live in the pages' and posts' own text. The migration ID `embeds_0001` goes back unused.

## 4. Files

- **`modules/embeds/`:**
  - `module.json`, `MODULE.md`, `CHANGELOG.md`;
  - `providers.json` and `providers.cases.json`;
  - backend: `__init__.py` (its `CSP`), `providers.py` and `public.py`;
  - web: `module.web.ts`, `public.ts`, `providers.ts`, `Embed.tsx`, `EmbedButton.tsx`, `VideoPlaylist.tsx`, `youtube.ts` (the IFrame API's loader) and `embeds.css`;
  - tests: `tests/backend`, `tests/web` and `tests/e2e`.
- **The kernel:**
  - `kernel/web/src/slots/types.ts` and the slots' tests;
  - a kit context in `kernel/web/src/ui/`;
  - `MarkdownEditor.tsx`, `Prose.tsx` and their tests;
  - `app/mount.tsx`.
  The main lane agreed on 2026-11-22 that these files are this PR's while it's open. Media's round 2 (#126) touches none of them. If blog's AI PR is ready first, the main lane asks before touching them;
  - SPEC 8's slot table and its change log;
  - decision 0060.

## 5. Conventions this follows

- SPEC 4 to 8, 11 and 15, and hook 6 in `hooks.md`.
- `mechframe-module-extractor`, `module-contract-lint`, and the brand check on what's lifted.
- `contact` and `pages` as the pattern for the layout, and decision 0057 for `public.ts`.

## 6. Non-goals

- **Other providers** (Vimeo, TikTok, Apple Music, Mixcloud) or oEmbed lookups. A provider is one more entry in `providers.json`, its host in `CSP`, and its cases.
- **A switch for each provider.** The CSP is per module, so each host is allowed while `embeds` is on.
- **The Videos list itself.** It's `featured`'s slot `videos`, edited in Admin › Homepage › Players (step 2). Fetching a video's title for it is `featured`'s job too.
- **One thing playing at a time** waits for `audio-player` (step 2). The players in text can't be paused from outside without each provider's API.
- **Embeds in messages** (`community`), and the media library's own audio and video (`media`).

## 7. Acceptance

**Providers:**
- Every case in `providers.cases.json` gives the same answer in pytest and in Vitest. The cases cover each kind, `youtu.be`, `m.`, `music.`, `/shorts/`, `/live/` and a bare id, tracking parameters dropped, SoundCloud's non-profile paths refused, Bandcamp's fragment and embed code, and a lookalike host refused.
- Every player address's host is in `CSP`.
- `CSP` holds those hosts only while the module is on, each in `media`.

**Text:**
- With `embeds` on, a lone recognised link is a facade. Its click grants `media` and draws the iframe with its sandbox, `allow`, title and `loading="lazy"`. With `media` already granted, or CONSENT_MODE `off`, it's the iframe at once, never playing by itself.
- A link in a sentence, an unknown host, or a paragraph with an image stays a link. With `embeds` off, every link stays a link.
- The server copy is unchanged.

**The editor:**
- The Embed button is in pages' and blog's editors with no change to either.
- A kernel entry in `editor.tools` draws before the modules' entries, and an entry with a `permission` shows only to people who hold it.
- It inserts `[words](link)` in a paragraph of its own, and Ctrl Z takes it back.
- An unplayable link says so, and Bandcamp's embed code becomes its link.

**The playlist** (the IFrame API stubbed in the web tests):
- Facade first. A row plays. The end of a video moves to the next with Autoplay on, and stays with it off.
- Prev and Next wrap. Autoplay never restarts the current video.
- `aria-current`, `onPlay` and `pause()` behave as §2 says. The layout stacks under 980px.

**The rest:**
- Both themes, axe clean.
- `validate_schemas`, `module-contract-lint` and the brand check pass.
- `mechframe add embeds`, then `mechframe check`, pass on a new site, alone and with `pages` and `blog`.

## 8. For the owner, and the main lane

1. **YouTube's thumbnails before a visitor plays:** none before `media` is granted (the owner, 2026-11-22, as recommended). Until then, the poster if one is set, or the site's own frame with the title. Once a visitor has played anything, the thumbnails show. Fetching them sooner would tell Google the visitor's address before any consent.
2. **The main lane's answer (Dev 34, 2026-11-22):** both kernel changes go in this PR, with `main` merged first. `editor.tools` takes kernel entries too, for the AI. Decision 0060 is embeds'. The main lane holds 0058 (the AI) and 0061 (the account's name field), and migrations `kernel_0016` and `kernel_0017`. `campaigns` takes 0062 and up.

## Changes after approval

2026-11-22, in the build:
- **The list's two copies:** `mechframe add` copies a module's `backend/<id>/` and `web/` and nothing at its root. So `providers.json` lives in `backend/embeds/` with its twin in `web/`, which a test holds equal, as VybeSite's two were. The cases live in `tests/providers.cases.json`.
- **The facade's button** is Play for a video and Listen for audio, named with the words ("Play: The spring tour").
- **The playlist stops after its last video,** with Autoplay on. Prev and Next still wrap.
- **The editor's dialog has no form of its own**, since the editor may sit inside a page's form. Enter in either field inserts.
- **`Prose` keeps its HTML object the same for the same text.** React sets the HTML again whenever that object is a new one, which took the players out (found by the kit's test).
- **`lazyPart` takes a part given props** (`LazyOf<Props>`), for the two text slots.
