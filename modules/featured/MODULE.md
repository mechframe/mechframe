# featured

The site's players as staff choose them: named slots, such as the homepage's Spotlight, each holding a list in order of another module's items or of YouTube links, any of them given a start and an end. The contract is `dev plans/contracts/featured.md`; decision 0073 records the module, and decision 0072 the hook it points through.

## What it does

An admin makes a slot on Admin › Homepage › Players: its name (its tab), the key the site's code reads (`spotlight`), what it plays (the types the modules on give through `kernel.refs`, such as discography's tracks, and YouTube links), a video's kinds (Music video, Rap battle, Poetry) and whether the Dashboard shows it. Staff then fill each tab: Add track opens a picker over the site's things, drafts too, a page at a time; Paste links reads one or several YouTube links at once, titled from YouTube's oEmbed while `oembed_titles` is on. Each row can be dragged or moved with Move up and Move down, given dates, given a kind, or removed. "Save and go live" saves every changed list, each in one save, and the site shows it at once.

What's live is worked out at each read, with no job. A placement is live while `starts_at <= now < ends_at`, an open end counting as always; an item only while its own module says it's on the site. Every live thing plays, in order. Players shows each row as Live now, Up next (the soonest to start), Scheduled, Ended, Not on the site (a draft, or its module switched off) or This item was removed. A save keeps a placement whose module is off as it is, and leaves out one whose item is gone. Two saves of one slot at once make one version: the other is asked theirs or mine.

The site's pages read a slot with `useFeatured(key)` (or `featured.public.live` on the server) and draw it themselves: featured never decides how a player looks.

## Use when / avoid when

- Use when: the homepage or a page shows hand-picked items that staff reorder or schedule.
- Use when: staff need to swap featured content on a date without a deploy.
- Use when: a page plays a list of YouTube videos that staff choose.
- Avoid when: the list is simply the newest items; query the module that owns them instead.
- Avoid when: each item needs its own fields and pages; build it in its own module.

## What it adds

- **Routes**, under `/api/featured`:
  - public: `GET /slots/{key}` (`LiveSlot {key, label, kinds, items}`, each item a `ref` or a `link`, only what's live now; `Cache-Control: public, max-age=60`; 404 `featured.slot_not_found`);
  - `featured.placement.manage` (admins and editors): `GET /admin/slots` (`{items, types}`), `GET /admin/slots/{key}` (`FullSlot`, every placement with its state), `PUT /admin/slots/{key}/placements` (the whole list; 409 `featured.changed`; 422 `featured.not_accepted`, `not_found`, `not_youtube`, `no_title`, `unknown_kind`, `bad_dates`, `too_many`), `GET /admin/slots/{key}/pick?type=&q=&cursor=` and `POST /admin/youtube` (`{urls}`, 20 at most; 120 an hour an account);
  - `featured.slot.manage` (admins): `POST /admin/slots` (409 `featured.key_taken`, 422 `featured.unknown_type`), `PATCH /admin/slots/{key}` (409 `featured.in_use` for a type or kind still used) and `DELETE /admin/slots/{key}`.
- **Tables:** `featured_slot`, `featured_placement` (migration `featured_0001`, branch `featured`).
- **Web:** `/admin/featured` (Players, under the sidebar's Homepage) and the Dashboard's "Now in the {player}" card for each slot marked to show there.
- **Dashboard:** "Needs you" two days before a Dashboard slot goes empty ("{title} leaves the {label} in 2 days"), and the setup step "Put something in each homepage player".
- **Events:** emits `featured.placement.changed` (v1 `{slot_key}`) on each save, a slot's change and its delete; listens to nothing.
- **Permissions:** `featured.placement.manage`, `featured.slot.manage`.

## Settings and env vars

- `oembed_titles` (bool, default `true`): fill a pasted YouTube link's title from YouTube's oEmbed.

No env vars. YouTube's oEmbed is asked from the server only, about `https://www.youtube.com/watch?v=<id>` built from the link's id, with a second for each lookup.

## Install notes

`mechframe add featured` (it needs `embeds`). No slot is made by the migration: make them on Players, or in the site's seed for a demo. Vibrant Mindz's three are `spotlight` (tracks), `releases` (albums) and `videos` (YouTube links, three kinds), once discography 0.1.2 gives its types.

## Extension points

- Backend `public.py`: `async def live(db, key) -> LiveSlot | None`, what `GET /slots/{key}` answers.
- Web `public.ts`: `useFeatured(key)`, and the types `LiveSlot`, `LivePlacement`, `LinkShown` and `Kind`.
- A module whose things a slot may take gives them in its own `refs.py` (hook 11, decision 0072); featured never imports it.

## Known limits

- YouTube links only, with no poster, length or date: on the site YouTube's thumbnail is the poster, and Players shows YouTube's mark, so nothing loads from YouTube in the admin.
- No live preview of the homepage on Players: "Open homepage" opens the real one.
- No restore of an earlier list: the audit log keeps each save (`featured.slot.saved`), cut short past 4 KiB.
- The Dashboard's dates are the server's, in UTC; Players shows dates in the viewer's own time.

## Source and license

New code for MechFrame, proprietary (decision 0008).
