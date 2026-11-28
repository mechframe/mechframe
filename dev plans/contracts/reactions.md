---
feature: Reactions, the `reactions` module (decision 0068; module plan §2, §8 and §9; step 3's first)
status: approved
approved: 2026-11-28, as recommended ("Approve as recommended"): §8's five answers
plan: `dev plans/2026-11-28-next-session-m4n-reactions.md` §4, 1 and 2
pr: — (read from GitHub just before the push)
---

# Contract: reactions

## 1. Goal

A signed-in member with a verified address presses Fire, Love or Mind blown under a blog post, and anyone reading the post sees how many people pressed each. Pressing again takes it back. That's the row the Post board draws after the post's body.

Any module can put the same row under its own things, with no code of reactions' and none of its own beyond one line on its page and an item-references source (hook 11) for its things. Comments come next and reuse it for each comment. Community's port comes later and may widen it (§6).

## 2. Interfaces

**How a module takes reactions, with no import either way.** Blog stays usable without reactions, so neither lists the other in `requires.modules` (SPEC 7). The kernel carries the hand-off, as it does for social (decision 0067):
- **The back end:** a reaction names its thing by type and id, `{type: "blog.post", id}`, and reactions asks `kernel.refs.find` whether it's there and live. It never reads blog's rows.
- **The web:** a new props slot, `content.reactions`, which reactions fills. Blog's post page draws it with the kit's `<ReactionParts>`.

**The kernel's additions** (decision 0068; SPEC 8):
- **The slot** `content.reactions: {id, lazy: LazyOf<ReactionPartProps>}[]`, with `ReactionPartProps = {type: string; id: string}`. It's a props slot like `content.share`, drawn only by the kit, and joins `GIVEN_SLOTS`.
- **`<ReactionParts type id />`** in `kernel/web/src/slots/`, beside `ShareParts`, draws each part in its own error boundary. It draws nothing while no part is there, as with reactions off.

**Reactions' routes**, under `/api/reactions`. Every answer is an `Answer`, and every error a problem with a `reactions.*` code:

| Route | Access | What |
|---|---|---|
| `GET /?type=&id=` (`id` given 1 to 50 times) | `public`, with `optional_user` | `Reactions {palette: [ReactionChoice {key, label}], items: [Counted]}`; `Cache-Control: no-store`, since `mine` is the reader's |
| `PUT /{type}/{id}/{key}` | `moderation.can_post`, a verified address, `REACTIONS_RATE_LIMIT` | Adds the person's reaction; pressing twice adds one → `Counted` |
| `DELETE /{type}/{id}/{key}` | `current_user`, `REACTIONS_RATE_LIMIT` | Takes it back; taking back one that isn't there is fine → `Counted` |

- `Counted {id, counts: {key: int}, mine: [key]}`: a count for each key in the palette, 0 included, and the reader's own keys (empty when signed out). `GET` answers only the things live now; an id gone or hidden is left out.
- **The refusals:**
  - `reactions.unknown_type` 404: no module that's on gives that type (`refs.UnknownType`);
  - `reactions.not_found` 404: the thing is gone or not live (`find` leaves it out, or answers `live: false`);
  - `reactions.unknown_key` 422: on `PUT`, a key not in the palette; on `DELETE`, a key that isn't built in. A key taken out of the palette can still be taken back;
  - `reactions.email_unverified` 403: "Verify your email address first." (the kernel's `auth.email_unverified` words);
  - from the kernel: 401 signed out, 403 `kernel.timed_out` on `PUT` while a time-out runs, and 429 past the limit;
  - the request's own check: 422 for more than 50 ids, or none.
- **The limit:** `REACTIONS_RATE_LIMIT`, by default `60/1m`, per account. `PUT` and `DELETE` share one budget (scope `reactions.write`).
- **Two presses at once** make one row: `INSERT … ON CONFLICT (target_type, target_id, user_id, key) DO NOTHING`, on a full unique constraint, never a partial index.

**The service,** `backend/reactions/service.py`, the routes thin over it:
- `async def counted(db: AsyncSession, type: str, ids: Sequence[uuid.UUID], user: User | None) -> dict[str, Any]`: the whole `Reactions` answer, the palette and the items;
- `async def react(db: AsyncSession, user: User, type: str, id: uuid.UUID, key: str) -> Counted`;
- `async def unreact(db: AsyncSession, user: User, type: str, id: uuid.UUID, key: str) -> Counted`.
- `public.py` holds nothing in 0.1.0. Comments' contract decides whether it asks through the routes or through `public.py`.

**The palette:**
- **Built in** (`schemas.py`'s `BUILT_IN`): `fire` "Fire", `love` "Love", `mind_blown` "Mind blown", the three the Post board draws, with its icons lifted into `web/icons.tsx` under the same keys. A test holds the two lists equal.
- **The setting:** `Settings.palette: list[str]`, by default `["fire", "love", "mind_blown"]`. Each must be built in, with no repeats, 1 to 3 of them. Its order is the row's order. It's saved through the kernel's `PUT /api/kernel/admin/settings/reactions`, under `kernel.settings.manage`, with no screen of its own in 0.1.0 (§8, 5).

**The web:** reactions' `module.web.ts` fills `content.reactions` with `ReactionRow`:
- **The row:** `role="group"`, `aria-label="Reactions"`. One button per palette key: its icon, its count and its label hidden but read, with `aria-pressed`. Each is a pill at least 48px high. Pressed, it gets the accent ring and the accent at 14% behind it, from tokens (`--mf-color-accent`, `--mf-color-border-strong`, the board's `#2A3457`, and `--mf-radius-pill`).
- **Pressing** updates the count at once and puts it back if the server refuses, with the refusal's sentence in a toast.
- **Signed out,** the counts show, and pressing one goes to `/sign-in?next=<this page's path>`. An unverified member gets the sentence and a link to `/account`.
- **The data:** one `GET` per row through the generated client and TanStack Query, under the client's own key for `GET /api/reactions` with the thing's type and id (`["get", "/api/reactions", {params: {query: {type, id: [id]}}}]`).

**Blog 0.1.8:**
- **`backend/blog/refs.py`:** `Posts(refs.Source)`, `type = "blog.post"`, `label = "Posts"`, copied from discography's pattern.
  - `find`: drafts too; `live` while `lifecycle.visible`; `path` `/blog/<slug>` while live; `image` the cover's small size; `line` its date and category.
  - `pick`: newest first, `q` matched in the title.
  - This also lets a featured slot take posts: the slot's admin lists "Posts" among its types.
- **`LivePost`** gains `id: uuid.UUID`.
- **`web/pages/Post.tsx`** draws `<ReactionParts type="blog.post" id={post.id} />` after `<Prose>` and before "Related posts", where the board draws the row.

**Jobs:** `reactions.sweep`, weekly (`40 3 * * 0`). For each type with reactions whose module is on, it asks `refs.find` 200 ids at a time and deletes the rows of things that are gone. A thing that's only hidden keeps its reactions. A type that's off, or no longer given, is skipped, so switching a module off never loses its reactions.

**Hooks:**
- **Export and erase:** a person's reactions, as type, id, key and when. Erase deletes them, and the counts go down.
- **No others:**
  - no seed rows: they'd need another module's things, and seeds are ordered only by `requires` (then by id), which reactions has with none;
  - nothing to search, report or consent to;
  - no dashboard items;
  - no `CSP`;
  - no server copy: the counts aren't in the page's copy (§6).

## 3. Data

Branch `reactions`, migration `reactions_0001_reactions.py` (`reactions_0001`), `depends_on` `kernel_0002`, as featured's.

| Table | Column | Type | Null | Default / FK / index |
|---|---|---|---|---|
| `reactions_reaction` | `id` | `UUID` | no | PK |
| | `target_type` | `String(80)` | no | `refs.MAX_TYPE`; CHECK matches `refs.TYPE` |
| | `target_id` | `UUID` | no | no FK: another module's row (SPEC 10) |
| | `user_id` | `UUID` | no | → `auth_user` `ON DELETE CASCADE`; index |
| | `key` | `String(32)` | no | CHECK `^[a-z][a-z0-9_]*$` |
| | `created_at` | `timestamptz` | no | `now()` |
| | | | | UNIQUE `(target_type, target_id, user_id, key)`, which also serves the counts' `(target_type, target_id)` reads |

No row-level security: each route checks the person and the thing itself. One person's rows are theirs alone: `DELETE` matches `user_id` = the caller, never another's.

## 4. Files

- **New:**
  - `modules/reactions/`, laid out as `social`: `module.json` at 0.1.0, status `experimental`, with `env` `REACTIONS_RATE_LIMIT`, the setting `palette`, the job `sweep`, the slot `content.reactions`, `data_hooks`, no permissions, no events, and no `requires.modules`;
  - `backend/reactions/` with `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`, `jobs.py`, `privacy.py` and an empty `public.py`; `migrations/`; `tests/` (`backend/`, `contract/`, `web/`); and `web/` with `module.web.ts`, `ReactionRow.tsx`, `icons.tsx`, `reactions.css` and `schema.ts`;
  - `docs/decisions/0068-reactions.md`.
- **Changed:**
  - `kernel/web/src/slots/types.ts` and `modules.ts` (`content.reactions`), and `ReactionParts.tsx` beside `ShareParts.tsx`;
  - blog: `refs.py` (new), `schemas.py` (`LivePost.id`), `web/pages/Post.tsx`, `module.json` (0.1.8, its kernel range), `MODULE.md` and `CHANGELOG.md`;
  - `SPEC.md` (6's `signInFor`, 8's slot table and its paragraph, and the change log);
  - the generated files: `catalog.json`, `docs/HOST-VARIABLES.md`, the OpenAPI specs, `schema.ts` and `docs/progress.json`.
- **The source,** read only: VybeMindz's `backend/app/routers/messages.py` (`add_reaction`, `remove_reaction`, `_build_reactions`) and `models/__init__.py` (`Reaction`). What's lifted: the unique row per person, thing and reaction, and a duplicate press as a no-op. The icons come from VM Website's `design/site/Post.dc.html`. VybeMindz isn't VybeSite, so no brand check applies. It's run anyway before the push, as on every PR that lifts code.

## 5. Conventions this follows

- `CLAUDE.md` (Rules; Two lanes);
- SPEC 7's "Between modules" and Settings, SPEC 8's slots, SPEC 10, 14.7 (verification before public content, time-outs);
- `dev plans/contracts/social.md` and decision 0067 for a module any module uses through a props slot;
- decision 0072 and discography's `refs.py` for item references;
- `social` for a module's layout;
- skills `mechframe-module-extractor`, `module-contract-lint` and `alembic-multi-module-migrations`;
- the memory note "New module: hidden tests".

## 6. Non-goals

- **Custom emojis,** VybeMindz's uploaded `:name:` images (§8, 1).
- **Any emoji from a picker,** and reactions inside a message's words. Both are community's, at its port.
- **A list of who reacted.** Counts and your own only (§8, 4).
- **Guests reacting** (§8, 2).
- **Live counts** over WebSockets: the row reads again when the page does.
- **Notifications or events** when someone reacts.
- **The counts in the page's server copy or structured data.**
- **A reactions switch per post,** like blog's `allow_comments`.
- **Staff removing someone's reactions.** A suspension or an erase covers abuse.
- **Discography's, portfolio's and comments' rows:** each is its own PR, one `ReactionParts` line and a refs source each.
- **End-to-end encrypted reactions** (VybeMindz's blind index), which only an encrypted channel needs.

## 7. Acceptance

- `modules/reactions/tests/backend/`:
  - **The routes:**
    - each route's access: signed out, unverified, timed out, a member;
    - each of §2's refusals;
    - `PUT` twice makes one row, and two `PUT`s at once make one (separate sessions, the memory note "Race tests that really race");
    - `DELETE` of a reaction that isn't there answers the counts;
    - one person can't take back another's;
    - a draft refuses with `reactions.not_found`, and `GET` leaves it out;
    - counts cover the palette only, 0 included, and `mine` is the reader's own;
    - 50 ids answer, 51 refuse;
    - the limit answers 429.
  - **The palette:** a key outside it refuses on `PUT` but can be taken back on `DELETE`, and `BUILT_IN` matches `icons.tsx`.
  - **The sweep:** a gone thing's rows go, a hidden thing's stay, and a type that's off is skipped.
  - **The rest:** the migration's round trip, and export and erase.
- `modules/reactions/tests/contract/`: the routes over HTTP alone, without importing reactions' Python.
- Blog: `tests/backend/test_refs.py` (`find` with a draft, a live post and a gone id; `pick` with `q`), and `LivePost.id`.
- Web:
  - **`ReactionRow`:** signed out, unverified, pressed and not, a refusal putting the count back, the order the palette gives;
  - **`ReactionParts`:** draws nothing with reactions off;
  - **`Post`:** draws the row only with reactions on;
  - both themes, axe clean.
- **E2e** `reactions.spec.ts`: a member presses Fire on a live post and sees 1, pressed; signed out, the count shows and pressing goes to sign-in.
- `validate_schemas`, `module-contract-lint`, the brand check, and `mechframe add reactions` then `mechframe check`.
- **Live:** nothing is deployed. VM Website's board check of the Post page's row, once it lands.

## 8. The owner's answers (2026-11-28, each as recommended)

1. **Custom emojis:** VybeMindz lets admins upload images used as `:name:` reactions. No board draws them, and nothing on the site needs them before community. Leave them for community's port? *Recommended:* yes.
2. **Who may react:** signed-in members with a verified address, with time-outs holding, as SPEC 14.7 asks before public content? Guests can't: a guest's reaction can't be held to one each. *Recommended:* yes.
3. **Which things take reactions:** any live thing another module gives through item references (hook 11), so blog 0.1.8 gives its posts? That also lets a featured slot hold posts. *Recommended:* yes.
4. **Who reacted:** counts and your own only, since names on a public page are personal data? Community can add a members-only list later. *Recommended:* yes.
5. **The palette:** the board's three as a setting, saved through the kernel's settings route with no screen in 0.1.0, so another site can drop or reorder them? A screen waits until a board draws one. *Recommended:* yes.

## Changes after approval

- **2026-11-28, as built:**
  - **The palette's answer** is `ReactionChoice`, not `Choice`: the kernel's notifications have a `Choice`, and the two would share one name in the site's OpenAPI.
  - **Each button's name** is its `aria-label`, "Fire, 3": a hidden label inside the button ran into the count ("Fire3"). The visible count is in the name (WCAG 2.5.3).
  - **The query key** is the generated client's own for `GET /api/reactions` with the thing's type and id, not `["reactions", type, id]`, so the row's updates land where its read is kept.
  - **The kernel's `signInFor(path)`** joins its web surface (SPEC 6), so the row sends a signed-out reader to sign in and back as `RequireAuth` does.
  - **Refusal order on `PUT`:** an unverified address first, then the type and the thing, then the key.
  - **No `docs/TESTING.md`** exists to change: each module's tests are in its `MODULE.md`, "Its tests".
  - **Comments on the Post board** draw a heart and a count under each comment: comments' contract takes that up.
  - **A row's writes go one after the other** (Codex on #170): two presses before the first answer could each answer a count that missed the other, and the last to arrive cleared a saved reaction. Each waits for the one before it, and an answer is drawn only when no press is queued after it.
  - **From CodeRabbit and cubic on #170:**
    - an unverified member can still take their own back; only adding asks for a verified address;
    - a press while who's signed in isn't known yet does nothing, rather than going to sign-in;
    - a read that fails again hides the row, though TanStack Query keeps the last answer;
    - the counts and the reader's own come from one statement, so one snapshot;
    - `ReactionParts` keys each part by the thing too, so another thing gets a fresh part.
    - each write, its answer and its putting back are the presser's: none goes out or lands once someone else is signed in, or no one, or the row has gone, asked from the query cache at that moment through the kernel's newly exported `SESSION_KEY`; a write dropped leaves the row to be read again.
  - **A read on its way is stopped** when a press is drawn and before a saved answer is drawn (CodeRabbit on #170), so a read begun before the press never draws over it.
  - **The module's line** (`summary`, which Settings › Modules draws under its switch) is "Reactions on posts, comments and messages", the AdminSettings board's words (VM Website Dev 27, the owner's word, 2026-11-28).
