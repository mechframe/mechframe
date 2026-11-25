---
feature: Social posting, the `social` module (decision 0067; `blog.md` §8, 4 and 7, answered 2026-11-22 and 2026-11-24)
status: approved
approved: 2026-11-24, as recommended ("Approve as recommended"): §8's five answers
plan: `dev plans/done/2026-11-24-next-session-m4j-social.md` §4, 1 and 2; the fourth of blog's PRs (`blog.md` §8, 1), before step 1 is closed
pr: — (read from GitHub just before the push)
---

# Contract: social posting

## 1. Goal

From a published post's editor, someone who may share sends it to the site's social channels through Buffer. They pick the channels, edit one text, and choose when: Buffer's queue, now, a set time, or a draft in Buffer. The card then shows how each channel's post stands, and one still waiting in Buffer can be taken back.

Any module with public pages can offer the same card for its own content (discography's releases next, products later), with no code of social's and none of its own beyond one line. The owner chose a module any module shares through (`blog.md` §8, 7).

The Buffer token is `BUFFER_ACCESS_TOKEN` on the host, or one an admin saves in Settings, sealed. A saved token wins, and a Check lists the channels it reaches, as `kernel.ai`'s key does (decision 0058).

## 2. Interfaces

**How a module shares, with no import either way.** Social stays optional for blog, so neither module lists the other in `requires.modules` (SPEC 7). The kernel carries the hand-off:
- **The back end:** the item is named by its content type and id, `{type: "blog.post", id}`. The kernel resolves its link preview, so social never reads blog's rows.
- **The web:** a new props slot, `content.share`, which social fills. Blog's editor draws it with the kit's `<ShareParts>`.

**The kernel's additions** (decision 0067; SPEC 6, 8 and 9):
- `server_copy.preview(db, content_type, content_id) -> Preview | None`, with `Preview(url, title, description, image)`. It works in three steps:
  - the type's search `Source.document` gives the path, so the item must be public;
  - the server copy's `page()` at that path gives the title, description and image, as the page's own head tags name them;
  - the image falls back to the site's social card (`kernel.site`), and to None without one.
  - It answers None for a type that isn't searched, an item that isn't public, or a path that answers `Moved`. `url` is absolute, from `SITE_URL`.
- **The slot** `content.share: {id, lazy: LazyOf<SharePartProps>, permission?}[]`, with `SharePartProps = {type: string; id: string; live: boolean; adminPath: string}`. It's a props slot like the text slots, drawn only by the kit (decision 0060's rule).
- **`<ShareParts type id live />`** in the kit draws each part in its own error boundary and hands it the current admin path. It draws nothing while no part is there: social off, or the person without `social.post.send`.

**Social's routes**, under `/api/social/admin`. Every answer is an `Answer`, and every error a problem with a `social.*` code:

| Route | Access | What |
|---|---|---|
| `GET /state` | `kernel.settings.manage` | `TokenState {source: "saved" \| "host" \| "none", unreadable, channels: [Channel], listed_at}`. Never the token |
| `POST /channels` | `social.post.send` | Asks Buffer with the token in use and stores what it lists → `{channels, listed_at}`. Settings' Check and the card's Refresh both call it |
| `GET /shares?type=&id=` | `social.post.send` | `ShareView {ready, live, card: Preview \| null, text, channels, history: [Share]}`, from the database alone (no Buffer call) |
| `POST /shares` | `social.post.send`, `SOCIAL_RATE_LIMIT` | `ShareSend {type, id, admin_path, channel_ids (1 to 10), text (1 to 5,000), when: "queue" \| "now" \| "at" \| "draft", due_at?, again}` → `ShareSent {results, history}` |
| `POST /shares/refresh` | `social.post.send` | `{type, id}`: asks Buffer how each queued post and draft stands → `{history}` |
| `DELETE /shares/{share_id}` | `social.post.send` | Takes a queued post or draft back out of Buffer → `{history}` |

**A send's checks,** before anything leaves, each with its sentence:
- `social.no_token` 503;
- `social.not_live` 409 (no preview);
- `social.channel_unusable` 422 (disconnected or locked in Buffer, or a network that takes no link posts, §8, 4);
- `social.text_too_long` 422, against each network's own limit: X 280, Bluesky 300, Threads 500, Mastodon 500, LinkedIn 3,000, Facebook 5,000;
- `social.time_passed` 422 (`at` under a minute ahead);
- `social.shared_before` 409, naming the channels and dates, until `again`;
- `social.address_not_answering` 409. The post's own address must answer 200 as itself, so a domain still on an old site never gets linked. A Buffer draft skips this check.

The item's row isn't social's to lock, so a transaction-scoped advisory lock on `(type, id)` holds the check and the records together, and two presses can't both pass.

**The send itself.** It runs in the request, as `kernel.ai`'s calls do, since the person waits for the answer.
- Each channel's share is stored as `sending` and committed before its call. The chosen channels' calls go at once, each with 15 seconds.
- Buffer's answer gives `queued`, `draft`, `sent` or `failed`. `refused` means Buffer took nothing.
- `unknown` means the request went out and no answer came back: "This may or may not have gone. Check the channel's queue in Buffer before posting it again." It counts as shared, so nothing is posted twice by mistake.
- **What's posted:** the text, with the link added at its end unless it's there already. LinkedIn instead gets the link as a card, sent whole: the preview's title, description and image. Every other network reads the page's own head tags for its preview.
- **The text starts** as the preview's title, a blank line, then its description.

**The token** lives in social's settings section `social`, as the field `buffer_token: SecretStr | None`. It's sealed, never answered, and never kept in a version (SPEC 7).
- The token in use is the saved one, else `BUFFER_ACCESS_TOKEN`. A saved token that can't be opened is reported, never swapped for the host's.
- A host value that couldn't be a token counts as none: blank, spaces, the example's placeholder, under 20 or over 400 characters.
- `kernel.settings.changed` for `social` clears the stored channels, so a new token is checked before anything is shared.
- The token is opened only in `service.py`, just before a call, and every message is scrubbed of it.

**The web:** social's `module.web.ts` fills two slots:
- `content.share`, with `SharePanel`: the "Share" card;
- `admin.settings.section`, with `SocialSettings`: "Social" on Settings › Site. It holds the token field, where it comes from, Check the token, and the channels with their problems.

**Blog 0.1.5:** `AdminPost.tsx` draws `<ShareParts type="blog.post" id live />` as a "Share" card after "After publishing" (§8, 3).

**Hooks:**
- export and erase: the shares a person sent; erase clears `sent_by_id` and `sent_by_name` and keeps the shares as the site's;
- dashboard: `ATTENTION` lists a share `failed` or `unknown` in the last 14 days, for `social.post.send`, linking to its `admin_path`; `SETUP` has "Connect Buffer", done once a token lists a channel;
- no seed rows: a share is a real post.

## 3. Data

Branch `social`, migration `social_0001_shares.py` (`social_0001`), `depends_on` `kernel_0016`.

| Table | Column | Type | Null | Default / FK / index |
|---|---|---|---|---|
| `social_channel` | `id` | `String(100)` | no | PK: Buffer's channel id |
| | `name`, `descriptor` | `String(300)` | no | `''` |
| | `service` | `String(40)` | no | Buffer's `service` (`linkedin`, `twitter`, …) |
| | `avatar` | `String(600)` | no | `''` |
| | `organization_id` | `String(100)` | no | `''` |
| | `disconnected`, `locked`, `queue_paused` | `Boolean` | no | `false` |
| | `position` | `Integer` | no | Buffer's order |
| | `listed_at` | `timestamptz` | no | the list is replaced whole on each check |
| | `settings_version` | `Integer` | no | `0`: the section `social`'s version it was checked at |
| `social_share` | `id` | `UUID` | no | PK |
| | `content_type` | `String(64)` | no | index `(content_type, content_id, created_at)` |
| | `content_id` | `UUID` | no | no FK: another module's row (SPEC 10) |
| | `admin_path` | `String(300)` | no | a path under `/admin` |
| | `channel_id` | `String(100)` | no | no FK: the list is replaced |
| | `channel_name` | `String(300)` | no | as it was named then |
| | `service` | `String(40)` | no | |
| | `text` | `Text` | no | CHECK ≤ 5,000 |
| | `link` | `String(600)` | no | |
| | `mode` | `String(8)` | no | CHECK in `queue`, `now`, `at`, `draft` |
| | `due_at`, `sent_at` | `timestamptz` | yes | |
| | `state` | `String(10)` | no | CHECK in `sending`, `queued`, `draft`, `sent`, `failed`, `refused`, `unknown`, `removed` |
| | `buffer_post_id` | `String(100)` | yes | |
| | `error` | `Text` | no | `''` |
| | `external_link` | `String(600)` | yes | the post's address on the network |
| | `sent_by_id` | `UUID` | yes | → `auth_user` `ON DELETE SET NULL` |
| | `sent_by_name` | `String(300)` | no | `''` |
| | `created_at`, `updated_at` | `timestamptz` | no | `now()` |

A share is its item's history, not a log, so it's kept while social is installed. `mechframe remove social --drop-data` drops it.

## 4. Files

- **New:**
  - `modules/social/`, laid out as `campaigns`: `module.json` at 0.1.0, with `env` `BUFFER_ACCESS_TOKEN` and `SOCIAL_RATE_LIMIT` (default `30/1h`), the permission `social.post.send` (admin, editor), `events.listens` `kernel.settings.changed`, `data_hooks`, and no `requires.modules`;
  - `backend/social/` with `models.py`, `schemas.py`, `service.py` (Buffer's client, lifted), `router.py`, `events.py`, `privacy.py` and `dashboard.py`; `migrations/`; `tests/`; and `web/` with `module.web.ts`, `SharePanel.tsx`, `SocialSettings.tsx`, `social.css` and `schema.ts`;
  - `harness/fake_buffer.py`;
  - `docs/decisions/0067-social-posting.md`.
- **Changed:**
  - `kernel/backend/kernel/server_copy.py` (`preview`), `kernel/web/src/slots/types.ts` and `modules.ts` (`content.share`), and the kit's `ShareParts`;
  - `modules/blog/web/pages/AdminPost.tsx`, and blog's `module.json` (0.1.5, its kernel range);
  - `SPEC.md` (6, 8, 9 and the change log) and `docs/TESTING.md`;
  - the generated files: `catalog.json`, `docs/HOST-VARIABLES.md`, the OpenAPI specs, `schema.ts` and `docs/progress.json`.
- **The source,** read only: VybeSite's `backend/app/services/buffer_service.py`, `routers/social.py`, `models/social.py` and `schemas/social.py`. The lifted code passes its brand check.

## 5. Conventions this follows

- `CLAUDE.md` (Rules; Two lanes);
- SPEC 7's Settings and "Between modules", SPEC 8's slots, SPEC 10, SPEC 11;
- `kernel/backend/kernel/ai.py` for the token's order and its Check;
- `campaigns` for a module's layout and `admin.settings.section`;
- `harness/fake_anthropic.py` for the fake;
- skills `mechframe-module-extractor`, `module-contract-lint` and `alembic-multi-module-migrations`.

## 6. Non-goals

- Posting by itself when something publishes (§8, 1).
- A picture or video of its own (Instagram, TikTok, YouTube, Pinterest), a thread of several posts, or a different text for each channel.
- Each network's own API: Buffer only.
- VybeSite's claims and AI-tells checks on the text (claims later, the owner 2026-11-22).
- Likes, clicks or any numbers read back from Buffer.
- A page of every share across the site: the Dashboard's items cover what's wrong.
- The Buffer account and its token: the owner's.
- Discography's and products' Share cards: their own PRs, one `ShareParts` line each.

## 7. Acceptance

- `modules/social/tests/backend/`:
  - **The client** against the fake:
    - Buffer's `UNAUTHORIZED` is a refused token;
    - a 429 says the minutes from `Retry-After`;
    - a 5xx or a timeout after the request went out is `unknown`;
    - the token is in no message.
  - **The routes:**
    - every route's access;
    - each of §2's refusals;
    - a share is stored `sending` before its call (the fake reads the row);
    - two sends at once, one share;
    - `again`;
    - refresh maps Buffer's states, and a deleted one becomes `removed`;
    - only a queued post or a draft can be taken back.
  - **The token:**
    - saved wins over the host's;
    - an unreadable saved one is reported, not swapped;
    - the placeholder counts as none;
    - a change clears the channels.
  - **The rest:** the migration's round trip, export and erase, the attention item, and the setup step.
- `kernel/tests/test_server_copy.py`: `preview` for a live post, None for a draft, a moved path and a type that isn't searched, and the site's card when the page has no image.
- Web:
  - **`SharePanel`'s states:** no token, not live, a channel's problem, a text over a limit, the results, the history, take back.
  - **`SocialSettings`:** saved, host, none, unreadable, Check.
  - **`ShareParts`:** draws nothing with social off.
  - **`AdminPost`:** draws the card only with social on.
  - Every one of these in both themes, axe clean.
- **E2e** `social.spec.ts`, with the fake: share a live post to two channels, see both queued, take one back.
- `validate_schemas`, `module-contract-lint`, the brand check, and `mechframe add social` then `mechframe check`.
- **Live:** nothing is deployed. A real post waits for the owner's Buffer account and token.

## 8. The owner's answers (2026-11-24, each as recommended)

1. **When it posts:** only when a person presses Share on a live item, as VybeSite does? Or also "Share when it goes live", set up on a scheduled post? *Recommended:* by hand only in 0.1.0. A post scheduled for later is shared once it's live, or with Buffer's "at a time".
2. **Who may share:** `social.post.send` for admin and editor (the owner holds every permission), as VybeSite's editors and up? *Recommended:* yes.
3. **Where the Share card sits:** no board draws it. Should it go after "After publishing" on the AdminPost board, built from the kit's parts, with VM Website drawing it on the board afterwards and sending any differences as an ask? *Recommended:* yes.
4. **Which networks:** link posts to LinkedIn, Facebook, X, Threads, Bluesky and Mastodon. A channel on Instagram, TikTok, YouTube or Pinterest would be listed as "takes no link posts from here". *Recommended:* yes; pictures of their own wait for a later version.
5. **Saving the token:** through `kernel.settings.manage`, as every module's settings save now? The handoff's open question on module settings' permissions covers the rest. *Recommended:* yes, for now.

## Changes after approval

- **2026-11-24, as built:**
  - **The preview's title** is the thing's own, from its search document. The page's `<title>` adds the site's name ("Jazz at noon · MechFrame site"), which a post shouldn't start with. The description and image are still the page's.
  - **A refusal more than §2 names:** 409 `social.channels_unlisted`, while a token's channels aren't listed yet (a new token forgets the old one's). Also 422 `social.channel_unknown`, `social.text_needed` and `social.time_needed`, 503 `social.token_unreadable`, and 422 `social.buffer_refused` when Buffer won't take a request.
  - **The Share card draws no channel's picture:** the browser loads nothing from Buffer's hosts, so `CSP` stays empty. The avatar is kept in `social_channel`, unused.
  - **The setup step** Connect Buffer is for `kernel.settings.manage`, the token's own permission.
  - **Each channel list keeps the settings version it was checked at** (Codex on #152). Only a list checked at the current version is used, and the change's event deletes only older lists, so a late or second delivery never takes away a fresh check. The Share card also reads again when the post is published on its page, so it can be shared without a reload.
  - **From CodeRabbit on #152:**
    - `preview` answers only from the thing's own module, which must be on: another module's page at its path is never its preview.
    - A token holds only printable ASCII.
    - Buffer's `UNEXPECTED` on a post counts as unanswered.
    - A share's address matches someone's export and erase only when it names no account.
    - Channels are stamped with the settings version read before the token.
    - A share stuck `sending` for five minutes shows on the Dashboard, whose words now say what an admin can do.
    - The card counts in code points, drops Share again when the channels picked change, and keeps a token typed while another saves.
