"""featured: the site's players as staff choose them (`dev plans/contracts/featured.md`).

Named slots, such as the homepage's Spotlight, each holding a list in order of
another module's items (through `kernel.refs`, decision 0072) or of YouTube
links (read by `embeds.public.recognise`), any of them given a start and an
end. A save puts the list live at once, and what's live is worked out at each
read: no job. The site's pages read a slot (`public.live`, the web's
`useFeatured`) and draw it themselves.

`CSP` is empty: YouTube's titles are asked for by the server, and the admin
shows YouTube's mark, never its thumbnails, so nothing loads from YouTube there.
"""

CSP: list[tuple[str, str] | tuple[str, str, str]] = []
