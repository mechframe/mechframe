# Changelog: featured

## 0.1.0

- Built to `dev plans/contracts/featured.md` §2, "featured 0.1.0" (decision 0073): slots an admin makes on Players, each a list in order of other modules' items (through `kernel.refs`, hook 11) or YouTube links (read by `embeds.public.recognise`), with optional dates; live worked out at each read, with no job.
- `GET /api/featured/slots/{key}`, cached a minute, `featured.public.live` and the web's `useFeatured`.
- Players at `/admin/featured`: a tab per player, the strip, the rows with drag and Move up and down, the picker, the dates and Paste links dialogs, a player's settings for admins, and one save bar for every changed list, with theirs or mine on a conflict.
- The Dashboard's card for each player marked to show there, the two-day warning and a setup step.
- Requires `embeds ^0.1`. The scaffold's job `announce_boundaries` and its server copy are gone: nothing is announced, and featured has no public pages.
