# reactions

Fire, Love and Mind blown under any module's live things: a count of each, and your own pressed. The contract is `dev plans/contracts/reactions.md`; the decision is 0068.

## What it does

**A signed-in member with a verified address** presses a reaction under a thing, and everyone reading sees how many people pressed each. Pressing it again takes it back. Signed out, the counts show and pressing one goes to sign-in, then back. An unverified member is told to verify their address first, and a member timed out by moderation can't add one until it ends (they can still take one back).

**Any module's things can take reactions,** with no code of reactions' and none of the other module's beyond two pieces:
- an item-references source for its things (`refs.py`, hook 11), which says whether each is there and live;
- one line on its public page: the kernel's `<ReactionParts type="<module>.<entity>" id />`, where the row goes.

Neither module imports the other. Reactions names the thing by its content type and id and asks `kernel.refs` whether it's live; the kernel's `content.reactions` slot carries the row. With reactions off, the page draws nothing there. Blog's posts are the first (`blog.post`, blog 0.1.8).

**The palette** is the reactions offered, in the row's order: `fire`, `love` and `mind_blown` by default, the three the Post board draws, each with its board icon. A site may drop or reorder them through the settings section `reactions` (`PUT /api/kernel/admin/settings/reactions`, under `kernel.settings.manage`); 0.1.0 has no screen for it. A reaction taken out of the palette isn't counted or offered, its rows are kept, and a person can still take theirs back.

**Each person has at most one of each** on a thing: two presses at once make one row.

## Use when / avoid when

Use it when readers should react to posts, tracks or artwork with one press, and when several kinds of content need the same row. Avoid it when readers should say something in words (use comments), and on a site whose readers have no accounts.

## What it adds

- **Routes**, under `/api/reactions`:
  - `GET ?type=&id=` (`id` 1 to 50 times), public: `{palette: [{key, label}], items: [{id, counts, mine}]}`. Only the things live now, in the order asked; a count for each key in the palette, 0 included; `mine` is the reader's own, empty signed out. `Cache-Control: no-store`.
  - `PUT /{type}/{id}/{key}`, a member who may post now (`moderation.can_post`) with a verified address: adds theirs → `{id, counts, mine}`.
  - `DELETE /{type}/{id}/{key}`, a member: takes theirs back → `{id, counts, mine}`. Taking back one that isn't there is fine.
  - **Refusals:** 404 `reactions.unknown_type` (no module on gives the type), 404 `reactions.not_found` (gone or not live), 422 `reactions.unknown_key` (on `PUT`, outside the palette; on `DELETE`, not built in), 403 `reactions.email_unverified`; the kernel's 401, 403 `kernel.timed_out` and 429.
  - Adding and taking back share one budget, `REACTIONS_RATE_LIMIT` (60 a minute by default), per account.
- **Slot:** `content.reactions`, the row (`ReactionRow`).
- **Table:** `reactions_reaction`, migration `reactions_0001` on the branch `reactions`, one row for each person's reaction to a thing, unique by thing, person and key.
- **Job:** `reactions.sweep`, Sundays at 03:40 UTC: the reactions of things that are gone are deleted. A thing that's only hidden keeps them, and a type whose module is off is skipped.
- **Hooks:** export and erase (a person's reactions listed; erase deletes them, and the counts go down).
- **Settings:** the section `reactions`, its one field `palette`.
- **Variables:** `REACTIONS_RATE_LIMIT` (`docs/HOST-VARIABLES.md`).

## Settings and env vars

- **The settings section `reactions`:** `palette`, the reactions offered in the row's order, built-in keys only (`fire`, `love`, `mind_blown`), each once; all three by default. Saved through the kernel's `PUT /api/kernel/admin/settings/reactions` under `kernel.settings.manage`, with no screen of its own in 0.1.0.
- **`REACTIONS_RATE_LIMIT`** (optional): how many reactions one account may add or take back, as count/period; `60/1m` by default (`docs/HOST-VARIABLES.md`).

## Install notes

`mechframe add reactions`, then `mechframe upgrade kernel` if the site's kernel predates the `content.reactions` slot. It requires no module. A thing takes reactions once its module gives it through `refs.py` and its public page draws `<ReactionParts type id />`: blog 0.1.8's posts do. Nothing is drawn until then, and nothing needs a key, a host or a third-party account.

## Extension points

- A module's things take reactions once it gives them through `refs.py` and its page draws `<ReactionParts type id />` from `@/kernel`.
- `public.py` holds nothing in 0.1.0.

## Known limits

- No custom emojis, no emoji picker, no list of who reacted, no guests, and no live counts: the row reads again when the page does (the contract's §6).
- The counts aren't in the page's server copy.

## Its tests

`tests/backend` holds the rules on the database against a made-up refs source, the race of two presses and the sweep; `tests/contract` every route over HTTP, with blog's posts as the things; `tests/web` the row; `tests/e2e` a member pressing Fire on a live post in the browser.

## Source and license

VybeMindz's `backend/app/routers/messages.py` (`add_reaction`, `remove_reaction`, `_build_reactions`) and `models/__init__.py` (`Reaction`), commit `7315225`, reshaped: any module's thing named by type and id in place of a message, a palette in place of any emoji, the kernel's checks in place of the channel's. What's kept: one row each per person, thing and reaction, a duplicate press a no-op. Its encrypted channels' blind index and its custom emojis aren't lifted. The icons are VM Website's Post board's. The owner's code, proprietary.
