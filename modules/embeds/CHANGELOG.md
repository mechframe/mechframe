# Changelog: embeds

## 0.1.1

- The playlist's "Prev" button reads "Previous". Its name, "Previous video", now starts with its words, as WCAG 2.5.3 asks and axe checks (`label-content-name-mismatch`). audio-player's end-to-end check covers the playlist again.

## 0.1.0

- First version: YouTube, SoundCloud, Spotify and Bandcamp players from a pasted link, in every `Prose` through `prose.embed`, behind the site's own facade until `media` is granted; the editor's Embed button in every `MarkdownEditor` through `editor.tools` (decision 0060); `Embed`, `VideoPlaylist`, `recognise`, `wordsFor` and `youtubeId` in `public.ts`, and `recognise` and `words_for` in `public.py` (`dev plans/contracts/embeds.md`, approved 2026-11-22).
