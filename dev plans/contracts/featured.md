---
feature: The featured module, the homepage's players as staff choose them: named slots holding an ordered, schedulable list of another module's items or of YouTube links, read by the site's pages, with Admin › Homepage › Players and the Dashboard's "Now in the spotlight" (Vibrant Mindz step 2, the third of three; the side lane's M11)
status: approved
approved: 2026-11-25 (the owner: "Approve as recommended", the eight answers in §8 as recommended)
plan: `docs/plans/vibrant-mindz-backend/backend-plan.md` (§2, 1) and `players-admin.md`; VM Website's boards `design/site/AdminPlayers.dc.html` (Players), `AdminDashboard.dc.html` (the card and the Needs-you item), `Main.dc.html` (the Spotlight bar, the hero's Play, the Releases deck, the Videos player) and `Videos.dc.html`
pr: three, in order (§8, 1): the hook, then featured 0.1.0, then discography 0.1.2; decisions 0072 (the hook) and 0073 (featured); migration `featured_0001`
---

# Contract: `featured`

## 1. Goal

Staff choose what the homepage features on Admin › Homepage › Players, without a deploy. Each player has a tab: the Spotlight's tracks, the Releases deck's albums and the Videos player's YouTube links. Each tab holds a list in order, and any item can be given a start and an end date. A save puts the list live at once. The site's pages read only what's live this minute. The Dashboard says what's in the spotlight, and warns two days before a slot would go empty. featured never decides how a page draws its items: a page reads a slot and draws it.

## 2. Interfaces

### The hook, item references (hook 11, its own PR; decision 0072; §8, 1)

A ninth row in SPEC 7's "Hooks every module can fill". A module whose things another module may point at (pick, list, show as removed) fills it. The module that points never imports it. Built with the skill `mechframe-hook-designer`, as hooks 1 to 8 were.

```python
# a module's refs.py
REFS: tuple[refs.Source, ...]

# kernel.refs
@dataclass(frozen=True)
class Ref:
    id: uuid.UUID
    title: str            # "Catalyst (full album)"
    line: str             # "Catalyst, petro and J Tone"; for an album "2026, petro and J Tone, 1 track"
    image: str | None     # a small picture's address (a cover), or None
    path: str | None      # its page while it's on the site, else None
    live: bool            # on the site now
class Source(ABC):
    type: ClassVar[str]   # "<module>.<type>", such as "discography.track"
    label: ClassVar[str]  # "Tracks"
    async def find(self, db: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Ref]   # drafts too; an id left out is gone
    async def pick(self, db: AsyncSession, q: str | None, *, cursor: str | None, limit: int) -> RefPage  # drafts too, newest edit first
RefPage = TypedDict("RefPage", {"items": list[Ref], "next_cursor": str | None})

async def types(db: AsyncSession) -> dict[str, str]  # each module on's types, by type: its label
async def find(db, type: str, ids) -> dict[uuid.UUID, Ref]
async def pick(db, type: str, q: str | None, *, cursor: str | None, limit: int = 20) -> RefPage   # limit at most 50
class UnknownType(LookupError)                      # a type no module on gives
```

- **How the kernel finds them:** it reads `refs.py` as it reads `search.py`. A type that isn't `<the module's id>.<name>`, or a type two modules give, is refused at the start.
- **No HTTP route of the kernel's own:** a module that points answers through its own routes, under its own permission.

### featured 0.1.0 (requires the kernel and `embeds ^0.1`; decision 0073)

**A slot** has these fields:
- a `key` the site's code reads (a slug, 40 at most: `spotlight`);
- a `label` (its tab: "Spotlight");
- what it takes, `accepts`: types from `await refs.types(db)`, or `"youtube"` for links;
- for links, its `kinds` (`[{key, label}]`: Music video, Rap battle, Poetry);
- `on_dashboard`.

Slots are made on the Players page by an admin (§8, 2).

**A placement** is either an item (`{type, id}`) or a link (a YouTube video's address, its title and its kind). Each has optional `starts_at` and `ends_at`, and its place in the list.
- **It's live** while `starts_at <= now < ends_at`, an open end counting as always.
- **A live item is shown** only while its source says `live`. A gone item is never shown.
- **A placement whose module is off** (`refs.UnknownType`) is left out of the public read and shows `hidden` in the admin's. A save keeps it as it is.

**HTTP** (`/api/featured`, behind `require_module("featured")`):

- **The public read:** `GET /slots/{key}` → `LiveSlot {key, label, items: [LivePlacement]}`.
  - Each item is `LivePlacement {id, ref: {type, id, title, line, image, path} | null, link: {url, video_id, title, kind} | null}`.
  - It holds only what's live now, in order, with `Cache-Control: public, max-age=60`.
  - A key with no slot answers 404 `featured.slot_not_found`.
- **`featured.placement.manage`:**
  - `GET /admin/slots` → `{items: [AdminSlot]}`. Each has its fields, its `version` and the counts `{live, scheduled}`, in the order the slots were made.
  - `GET /admin/slots/{key}` → `FullSlot`: the slot, its `version`, and every placement (live, scheduled and ended).
    - Each placement is `AdminPlacement`: the ref with `live`, or `ref: null, removed: true`; or the link; plus `starts_at`, `ends_at` and its `state`.
    - `state` is one of `live`, `next` (the soonest to start), `scheduled`, `ended`, `hidden` (its item isn't on the site) or `removed`.
  - `PUT /admin/slots/{key}/placements` takes `{version, items: [{id?, ref?: {type, id}, link?: {url, title, kind?}, starts_at?, ends_at?}]}` → `FullSlot`. The whole list in one save:
    - 409 `featured.changed`, with the slot as it is now;
    - 422 `featured.not_accepted` (a type it doesn't take), `featured.not_found` (an id its source hasn't got), `featured.not_youtube`, `featured.no_title` (a link's title is 1 to 200 characters), `featured.unknown_kind`, `featured.bad_dates` (an end not after its start) and `featured.too_many` (100);
    - it emits `featured.placement.changed` v1 `{slot_key}`, and is audited as `featured.slot.saved` with the list.
  - `GET /admin/slots/{key}/pick?type=&q=&cursor=` → `RefPage` through `refs.pick`. 422 `featured.not_accepted` for a type the slot doesn't take.
  - `POST /admin/youtube` `{urls: [str]}` (20 at most) → `{items: [{url, video_id, title}], refused: [{url, reason}]}`.
    - Each link is read by `embeds.public.recognise` (a YouTube video), and its `title` is YouTube's while `oembed_titles` is on, else null.
    - `rate_limit("120/1h", key="account")`.
- **`featured.slot.manage`:**
  - `POST /admin/slots` `NewSlot {key, label, accepts, kinds?, on_dashboard?}` → 201 `FullSlot`. 409 `featured.key_taken`; 422 for a type no module gives.
  - `PATCH /admin/slots/{key}` `{version, label?, accepts?, kinds?, on_dashboard?}` → `FullSlot`. A type or a kind still used is refused: 409 `featured.in_use`.
  - `DELETE /admin/slots/{key}` → 204, with its placements.

**YouTube's titles:** `GET https://www.youtube.com/oembed?url=<the watch address>&format=json`.
- Only that address, so no address someone typed is fetched. The links are looked up at once over httpx, each with a 1 s timeout, so the route answers within about a second (SPEC 7).
- A failure leaves the title null, for staff to type.

**Backend, `featured.public`** (for a site's own code, and modules that list `featured` in `requires`):

```python
async def live(db: AsyncSession, key: str) -> LiveSlot | None   # what GET /slots/{key} answers
```

**Settings:** `oembed_titles` (bool, true), the scaffold's.

**Dashboard (hook 8):**
- **`ATTENTION`,** for each `on_dashboard` slot with something live, whose live items all end within two days, with nothing scheduled after:
  - "{title} leaves the {label} in 2 days";
  - "After {the last end, as "Nov 17"} the {label} is empty on the site unless something else is scheduled.";
  - "Schedule the next one", to `/admin/featured?slot={key}`, tone info, for `featured.placement.manage`.
- **`SETUP`:** "Put something in each homepage player", done once every slot has something live.

**Web:**
- **`/admin/featured`** (`featured.placement.manage`): Players under the sidebar's Homepage, as the board draws it.
  - The lead: "Choose what plays in the homepage's players, in what order, and when." Then "Open homepage", and a tab per slot with its count.
  - **The strip:** "Now playing: Catalyst (full album), until Nov 17" and "Up next: Gather Around on Nov 17", or "Nothing scheduled".
  - **The rows:** a drag grip, plus Move up and Move down for the keyboard; the picture; the title and line; the dates ("Nov 10 to Nov 17", "Starts Nov 17, 12:00 AM", "No end date", "Always"); the pill; and "Remove {title}".
    - Pills: "Live now", "Up next", "Scheduled", "Ended", "Not on the site" and "This item was removed".
    - A video row has its Kind menu, and shows YouTube's mark, not its thumbnail: nothing loads from YouTube in the admin.
  - **The tabs' words:** each tab says what the slot takes, as the board's three do. "Add track", "Add album" (a type's button is "Add" and its label, singular) and "Paste links".
  - **The save bar:** "2 changes not saved: Hook It Up added, Gather Around scheduled", with Discard and "Save and go live".
  - **What the board doesn't draw (§8, 7):**
    - the picker (search and Load more);
    - a row's dates dialog;
    - the Paste links dialog;
    - for an admin, "New slot" and a slot's settings.
- **`admin.dashboard.widget`,** per `on_dashboard` slot (`featured.placement.manage`):
  - "Now in the {label lower}", "Catalyst (full album)", "Live since Nov 10, with 2 more queued", the pill "Live" and the link "Players";
  - with nothing live: "Nothing", "The {label} is empty on the site", the pill "Not live".
- **`@/modules/featured/public`:** `useFeatured(key)`, the live slot through TanStack Query, and the types `LiveSlot` and `LivePlacement`. The site's homepage and Videos page draw their players from it.

**Events:** emits `featured.placement.changed` (v1 `{slot_key}`) on each save, a slot's change or its delete. No job: what's live is worked out at each read (§8, 3).

**Hooks:** dashboard, as above. featured's own seed makes nothing: a site's seed makes its slots.

### discography 0.1.2 (its own PR, once the hook and featured are in)

- **`refs.py`** gives two types:
  - `discography.release` ("Albums"): the line "2026, petro and J Tone, 15 tracks", the cover, and `live` while it's on the site with a track that plays;
  - `discography.track` ("Tracks"): the line "Catalyst, petro and J Tone", and `live` while its release is on the site and it plays.
  - `pick` finds by title, drafts included, newest edit first.
- **Reads by id, for a homepage:**
  - `GET /api/discography/releases?ids=` (50 at most, the live ones in the order given);
  - `GET /api/discography/tracks?ids=` → `{items: [TrackLine & {release: {title, slug, artist_line, cover, path}}]}`, the live, playable ones in the order given;
  - `useTracks(ids)`, and `useReleases({ ids })`.
  - A spotlight's queue is `tracks.map((each) => playerItem(each, each.release))`.

## 3. Data

Branch `featured`, `featured_0001`, `depends_on` `kernel_0002` as audio-player's does.

| Table | Columns |
|---|---|
| `featured_slot` | `key` (≤ 40, slug) PK, `label` (≤ 60), `accepts` (jsonb list of types or `"youtube"`), `kinds` (jsonb `[{key, label}]`, ≤ 12), `on_dashboard` (bool), `position` (int, its tab's place), `version` (int), `created_at`, `updated_at` |
| `featured_placement` | `id` (uuid) PK; `slot_key` FK `featured_slot.key` ON DELETE CASCADE; `position` (int), unique (`slot_key`, `position`) DEFERRABLE; either `ref_type` (≤ 80) and `ref_id` (uuid), or `url` (≤ 500), `video_id` (char 11), `title` (1 to 200) and `kind` (≤ 40, null), one or the other by CHECK; `starts_at` and `ends_at` (timestamptz, null), CHECK `ends_at > starts_at`; `created_at`, `updated_at`; index (`ref_type`, `ref_id`) |

- **No foreign key into another module** (SPEC 10): a gone item shows as removed, and a save leaves it out.
- **No personal data:** `data_hooks` stay false.

## 4. Files

- **The hook:**
  - `kernel/backend/kernel/refs.py` and its tests;
  - `kernel/__init__.py`'s exports;
  - the registry's build, beside `search.build`;
  - SPEC 7's hooks row; `module-contract-lint`'s hooks section; decision 0072;
  - the main lane hears of it first: a kernel change in the side lane.
- **`modules/_featured/` becomes `modules/featured/`,** its `module.json` and `MODULE.md` saying what's agreed here:
  - `backend/featured/`: `__init__` (`CSP` empty), `models`, `schemas`, `service`, `router`, `public`, `youtube` (the oEmbed call), `dashboard`, `events`. The scaffold's `jobs.py` and `server_copy.py` go, and its `module.json`'s job `announce_boundaries`: it has no job and no public pages. `requires` gains `embeds ^0.1`.
  - `web/`: `module.web.ts`, `api.ts`, `public.ts`, `pages/Players.tsx`, `components/` (the tab, the row, the picker, the dates and Paste links dialogs, the slot's settings), `widgets/SpotlightCard.tsx`, `featured.css`.
- **The harness:** an e2e page drawing a slot through `useFeatured`.
- **Generated again:** `catalog.json`, OpenAPI and `schema.ts`, host variables, `progress.json`.
- **discography 0.1.2:** `refs.py`, `router` and `service` (the reads by id), `web/reads.ts` and `public.ts`, tests, `CHANGELOG.md`.

## 5. Conventions this follows

- SPEC 6 to 8 and 10.
- The skills `mechframe-hook-designer` (the hook), `mechframe-module-extractor`, `alembic-multi-module-migrations` and `module-contract-lint`.
- discography's layout and admin boards.
- The kit's SaveConflict and unsaved-changes guard.
- The memories `race-tests-that-really-race` (two saves of one slot) and `react-render-time-sync-traps`.

## 6. Non-goals

- **How a page draws a slot:** the Spotlight bar, the deck and the Videos page are the site's code, built from `useFeatured` and audio-player's and embeds' parts.
- **The board's live preview** of the homepage on Players (§8, 4).
- **Posters, lengths and dates** for videos (§8, 5).
- **Restoring an earlier list:** the audit log keeps each save, but there's no restore button.
- **Reordering the tabs,** slots of slots, or a slot per page or per person.
- **Links other than YouTube's.**
- **A Videos page of featured's own:** `/videos` is the site's.
- **Plays or clicks counted per placement.**

## 7. Acceptance

- **The hook:**
  - `refs.find` and `pick` reach a module's source, and skip a module that's off;
  - a malformed or doubled type is refused at the start;
  - `UnknownType`;
  - its row in SPEC 7.
- **featured, backend:**
  - what's live at the edges of `starts_at` and `ends_at`, an open end included;
  - an item its source says isn't live, or gone, is left out of the public read, and shows `hidden` or `removed` in the admin's;
  - each 422 and the 409, a placement whose module is off, and two saves of one slot at once making one version (a real race, checked with a mutant);
  - the oEmbed call on a fake transport: only YouTube's address, a timeout, a failure leaving the title null;
  - `ATTENTION` two days out and not three, and `SETUP`.
- **HTTP:**
  - each route's access;
  - the public read's cache header and its 404;
  - `featured.slot.manage` held by an admin, not an editor.
- **Web (Vitest):**
  - the tabs, the strip and the pills;
  - drag and Move up/down;
  - the picker, the dates and Paste links dialogs;
  - the save bar's words, Discard and the conflict;
  - the card and its "Nothing";
  - `useFeatured`.
- **E2E:**
  - Players in both themes at 1440 and 390, axe clean;
  - a track added, scheduled and saved, shown on the harness page once it starts;
  - nothing loads from YouTube in the admin.
- **discography 0.1.2:**
  - the two sources' lines and `live`;
  - the reads by id, in the order given, drafts left out.
- **Gates:** `validate_schemas`, `module-contract-lint`, then on a fresh site `mechframe add` embeds, featured and discography, and `mechframe check`.

## 8. Open questions for the owner

1. **How featured reaches another module's items** (the picker, a row's title and picture, an item that's gone).
   - *Recommended:* a new hook, item references, as above. featured needs only the kernel and embeds, discography needs nothing of featured, and any module's things can be featured: shop's products, blog's posts, pages for a menu module later.
   - It costs three PRs (the hook, featured, discography 0.1.2), and the hook is a kernel change the main lane hears of first.
   - *The other ways:*
     - featured requires discography: one PR, but it can't feature anything else without a new version.
     - discography requires featured and hands it its types: two PRs, but every site with music must have featured.
2. **Where slots come from.**
   - *Recommended:* an admin makes them on Players ("New slot": key, label, what it takes, kinds), and the site's own seed makes them for a demo.
   - A seed never runs on the live site, so at launch you'd make Vibrant Mindz's three once: `spotlight` (tracks), `releases` (albums) and `videos` (YouTube links, three kinds). The site's README would list them.
   - *The other way:* the site declares its slots in its own code and they're made at start. Nothing to type, but it's a new kind of site file the kernel reads.
3. **What's live, and the board's "Queued".**
   - *Recommended:* every live item is in the player, in order: the Spotlight's previous and next move through all of them. A row is "Live now" while it's live, "Up next" for the soonest to start, "Scheduled" for later ones. The board's "Queued" isn't used, and "with 2 more queued" counts the live ones after the first and the scheduled ones.
   - Live is worked out at each read, so a release-day start shows within the read's minute of cache, with no job.
   - *The other way:* only the first live item plays, the rest queued behind it, each taking over when the one before ends.
4. **The live preview on Players.**
   - *Recommended:* left out. The homepage's players are the site's code, which featured can't draw. "Open homepage" opens the real one.
   - *The other way:* a new web slot the site fills with its own players, drawn beside the list.
5. **Videos.**
   - *Recommended:*
     - YouTube links only, read by embeds (so featured requires embeds);
     - titles from YouTube's oEmbed, editable;
     - kinds set per slot;
     - no poster, length or date: YouTube's thumbnail is the poster on the site, as the board's note says, and its Videos page leaves "[Length] · [Date]" out.
   - *The other way:* a poster from the media library (featured then requires media), and a typed length and date.
6. **The Dashboard.**
   - *Recommended:* each slot marked "Show on the Dashboard" gets the card and the two-day warning; the first slot made is marked.
   - *The other way:* only the first slot, with no setting.
7. **What's added beyond the boards.**
   - *Recommended:* all of it. The board draws the buttons but not what they open.
     - the picker: search, a type's filter where a slot takes two, Load more;
     - a row's dates dialog;
     - the Paste links dialog;
     - Move up and Move down beside the grip, for the keyboard;
     - the pills "Scheduled", "Ended", "Not on the site" and "This item was removed";
     - "New slot" and a slot's settings for an admin.
8. **The order of work.** *Recommended:* the hook first, then featured 0.1.0, then discography 0.1.2. Each one lands before the next starts, all in the side lane, with the main lane told before the kernel PR.

## Changes after approval

- **2026-11-25, the hook's PR (#153) and its reviews.** None changes what was approved; each says what §2 meant:
  - `types` takes the session, `await refs.types(db)`;
  - a placement whose module is off shows `hidden`;
  - YouTube's titles come back within about a second, each lookup's timeout 1 s;
  - the two-day warning needs something live;
  - a link's title is required (`featured.no_title`), and an end must be after its start;
  - §4 names the scaffold's job, which goes, and the requirement on embeds.

## Changes as built (the hook, `feat/hook-item-references`)

- **`types` takes the session,** `types(db)`, since which modules are on is read through it.
- **`pick`'s limit is 20 when none is given,** 1 to 50 when it is, and its words at most 200 characters (ValueError otherwise). Words that are only spaces count as none.
- **`find`'s answer is held to the ask:** a source that answers an id it wasn't asked for, or a `Ref` under another id, has that left out.
- **The registry's switches are given to `refs.install`** by `assemble`. Without them, as in a unit test, every source counts as on.

## Changes as built (featured 0.1.0, `feat/featured-0-1-0`)

None changes what was approved; each says what §2 meant, or adds what a screen needed.

- **The answers:**
  - `LiveSlot` holds the slot's `kinds` too, so a Videos page can name its filters; a link's `kind` is its key.
  - `AdminPlacement` holds `item: {type, id}` beside `ref`, so a placement that's `hidden` (its module off) or `removed` is still known: a save keeps a hidden one as it is, and leaves a removed one out.
  - `AdminSlot` holds `now: {title, starts_at, ends_at} | null`, the first thing live, for the strip and the Dashboard's card; `GET /admin/slots` answers `types` too, the types the modules on give, by label.
- **The refusals named:**
  - a slot's type no module on gives is 422 `featured.unknown_type`, on `POST` and `PATCH`; one the slot took already may stay while its module is off;
  - a new item whose module is off is 422 `featured.not_accepted`;
  - a placement listed twice, or an `id` that isn't the slot's, is 422 `kernel.invalid_request`.
- **A link is kept as its watch address,** `https://www.youtube.com/watch?v=<id>`, built from the id embeds read: what a link carried besides (a start time, a playlist) is dropped. `POST /admin/youtube` answers that address. Each lookup is given a second in all, not per step.
- **The Dashboard:** the item's key is `featured.ending_<key>`, the slot's key with each `-` made `_` (an item's name takes no hyphen); "in 2 days" counts whole days, at least one; its date is the server's, in UTC. Setup's step is done once there's a slot and each has something live.
- **The audit's list** is cut short to fit the kernel's 4 KiB, with `count` and `more`. It never holds a player's name, which may have an `@` the audit refuses as an address (Codex on #157): `featured.slot.created` keeps what it takes, its kinds' keys and `on_dashboard`, and `featured.slot.changed` says the label changed, not to what.
- **While a save is on its way** the list can't be changed, so its answer never drops an edit made meanwhile (Codex on #157).
- **Players:**
  - the board's word is "player", so "New slot" is "New player" and a slot's settings are "{label} settings";
  - a single save bar for the whole page, which saves every list changed, each in turn; a conflict asks theirs or mine through the kit's `SaveConflict`, the list as one field, and "Keep mine" saves at their version, a placement they removed added again as new;
  - the kit's `SaveBar` gains `what`, the words after its count (the main lane's OK);
  - the picker reads 20 a page.
- **The harness:** its probe notes give `probe.note` (hook 11), its test support has a fake YouTube (`harness.fake_youtube`, `/api/_test/youtube`), and `/featured.html?slot=<key>` draws a slot through `useFeatured`.

## Changes as built (discography 0.1.2, `feat/discography-0-1-2`)

None changes what was approved; each says what §2 meant.

- **The two sources' lines** leave out what a release hasn't got: a release with no year reads "petro and J Tone, 1 track". A release's count is of its tracks that play. The picture is the front cover's smallest copy.
- **The picker** searches the title alone (a track's own, not its release's), drafts too, newest edit first; its cursor is `<updated_at>~<id>`, and one that isn't is a ValueError, which featured answers 422.
- **The reads by id** take `ids` repeated (`?ids=a&ids=b`). `GET /releases?ids=` answers the releases on the site, as `GET /releases` does, with or without a track that plays (featured's `live` already asked for one), still filtered by `kind`, on one page; a `cursor` beside `ids` is 422. `GET /tracks?ids=` answers `TrackCard`s, each a `TrackLine` numbered among its release's tracks that play, with its `release`. `useReleases({ ids: [] })` and `useTracks([])` answer an empty list with no request: sent, an empty `ids` is no `ids` at all, and the newest releases (Codex on #159).
- **VM Website's parity ask** (the owner's split, "Side lane, after featured") rides in this PR: D1 (a group's label over its controls, no outline), D2 (the role as wide as its words), D3 (20 px under a page's note), D4 (a track row's buttons and the covers at 390), K2 (a track that can't play is a red note everywhere, Credits' note amber), K3's words ("Live", "Tracklist to come" amber), K6's card round each table, and K8 (Tracks' panel 340 px, Credits' Roles 280 px). D2's width is a credit row's alone (`.mf-music-credit--role`): the release's link rows and the Roles list keep their grid (cubic on #159).
