# Changelog: embeds

## 0.1.2

- `EmbedFrame` in `public.ts`: a provider's iframe alone, the sandbox, title and shape `Embed` gives it, for a page that draws its own facade, such as a site's Listen for Bandcamp's own player. It draws nothing until `media` is granted, and nothing for a link that isn't a player (`dev plans/contracts/bandcamp-player.md`, decision 0075).
- `from_bandcamp_code` in `public.py`: the server's twin of the web's `fromBandcampCode`, both held to the new `bandcamp_codes` in `tests/providers.cases.json`, so `discography` keeps a Bandcamp player from the code an admin pasted.

## 0.1.1

- The playlist's "Prev" button reads "Previous". Its name, "Previous video", now starts with its words, as WCAG 2.5.3 asks and axe checks (`label-content-name-mismatch`). audio-player's end-to-end check covers the playlist again.

## 0.1.0

- First version: YouTube, SoundCloud, Spotify and Bandcamp players from a pasted link, in every `Prose` through `prose.embed`, behind the site's own facade until `media` is granted; the editor's Embed button in every `MarkdownEditor` through `editor.tools` (decision 0060); `Embed`, `VideoPlaylist`, `recognise`, `wordsFor` and `youtubeId` in `public.ts`, and `recognise` and `words_for` in `public.py` (`dev plans/contracts/embeds.md`, approved 2026-11-22).
