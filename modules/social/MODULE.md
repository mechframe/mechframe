# social

The site's published content shared to its social channels through Buffer. The contract is `dev plans/contracts/social.md`; the decision is 0067.

## What it does

**Someone who may share** (`social.post.send`, admin and editor) opens a published post's editor and finds the Share card under After publishing. They pick the channels Buffer reaches, edit one text (it starts as the title, a blank line and the description), and choose when it goes out: Buffer's queue for each channel, now, a set time at least a minute ahead, or a draft in Buffer to schedule there. The card then lists every share of the post with how it stands, Refresh asks Buffer again, and a post still queued or a draft can be taken back.

**Any module can offer the card** for its own content: its admin page draws the kernel's `<ShareParts type="<module>.<entity>" id live />`. Neither module imports the other. Social names the thing by its content type and id, and the kernel's `server_copy.preview` gives its link: the path from the type's search source, the description and picture from the page the server copy answers there, the site's social card when the page has none. A thing that isn't searched, isn't public, or whose module is off has no preview, and can't be shared.

**Before anything leaves,** a share is refused, in words:
- with no token (503 `social.no_token`), or a saved one that can't be opened (503 `social.token_unreadable`);
- for a thing that isn't public (409 `social.not_live`), or while Buffer's channels aren't listed (409 `social.channels_unlisted`);
- for a channel Buffer didn't list (422 `social.channel_unknown`), or one that can't take a link post (422 `social.channel_unusable`): disconnected or locked in Buffer, or a network that needs a picture or a video of its own (Instagram, TikTok, YouTube, Pinterest);
- for a text too long for a channel picked, the link included (422 `social.text_too_long`): X 280, Bluesky 300, Threads and Mastodon 500, LinkedIn 3,000, Facebook 5,000;
- for a set time that's passed (422 `social.time_passed`);
- for a channel the thing went to already, naming when, until the person says Share again (409 `social.shared_before`);
- while the thing's own address doesn't answer as its page (409 `social.address_not_answering`), so a domain still on an old site is never linked. A draft in Buffer skips this one.

**A share is stored before it's sent.** Each channel's share is committed as `sending` under a lock on the thing, so two presses can't both pass; then the chosen channels' calls go at once, 15 seconds each. Buffer's answer makes it `queued`, `draft`, `sent` (with its address on the network) or `failed`; `refused` is Buffer taking nothing. One whose request went out with no answer back is `unknown`, "may or may not have gone", and counts as shared, so nothing is posted twice by mistake. LinkedIn gets the link as a card, sent whole; every other network gets it at the end of the text and reads the page's head tags for its preview.

**The token** is `BUFFER_ACCESS_TOKEN` on the host, or one saved in Settings › Site's Social section, sealed, never shown again and never kept in a version; the saved one wins. A saved token that can't be opened (ENCRYPTION_KEYS changed) is reported, never swapped for the host's. Check the token asks Buffer which channels it reaches and keeps them, so opening a Share card costs no call to Buffer. A change to the token forgets the channels until they're checked again.

## Use when / avoid when

Use it when the site's people should post a new blog post (then a release or a product) to the site's LinkedIn, Facebook, X, Threads, Bluesky or Mastodon accounts through one Buffer account, choosing the words and the time themselves. Avoid it for posts that should go out by themselves on publishing, for posts that need a picture or video of their own, and for numbers read back from the networks.

## What it adds

- **Routes**, under `/api/social/admin`:
  - **With `kernel.settings.manage`:** `GET /state`: `{source: "saved" | "host" | "none", unreadable, channels, listed_at}`, never the token.
  - **With `social.post.send`:**
    - `POST /channels`: Buffer's list, kept in Buffer's order → `{channels, listed_at}`; 422 `social.token_refused`, 502 `social.buffer_failed`.
    - `GET /shares?type=&id=`: `{ready, source, unreadable, live, card, text, channels, listed_at, history}`, from the database alone.
    - `POST /shares` `{type, id, admin_path, channel_ids (1 to 10), text, when, due_at?, again}` → `{results, history}`, with the refusals above.
    - `POST /shares/refresh` `{type, id}` → `{history}`.
    - `DELETE /shares/{share_id}` → `{history}`; 409 `social.not_waiting` for one not queued or a draft.
  - A share and a channel check spend `SOCIAL_RATE_LIMIT` (30 an hour by default), under Buffer's own 100 requests every 15 minutes.
- **Slots:** `content.share` (the Share card, for `social.post.send`) and `admin.settings.section` (Social, for `kernel.settings.manage`).
- **Tables:** `social_channel` and `social_share`, migration `social_0001` on the branch `social`.
- **Event heard:** `kernel.settings.changed` for `social`: the channels are forgotten.
- **Hooks:** export and erase (a person's shares listed; erase clears who sent them and keeps the shares), Dashboard (`social.troubled`, a share failed or not confirmed in the last 14 days, linking to its admin page; the setup step Connect Buffer).
- **Settings:** the section `social`, its one field `buffer_token` (secret).
- **Variables:** `BUFFER_ACCESS_TOKEN` and `SOCIAL_RATE_LIMIT` (`docs/HOST-VARIABLES.md`).

## Its tests

No suite calls Buffer: `harness/fake_buffer.py` answers every request, the test app's included (`/api/_test/buffer` sets its trouble and reads what it made). `tests/backend` holds the client's faults and the race; `tests/contract` every route over HTTP; `tests/web` the card and the section; `tests/e2e` a post shared and taken back in the browser.

## From

VybeSite's `backend/app/services/buffer_service.py`, `routers/social.py`, `models/social.py` and `schemas/social.py` (commit `f659d7c`), reshaped: any module's content in place of blog posts, the token on the host or in Settings, the kernel's settings in place of its own table, the channels' calls at once. Its claims and AI-tells checks on the text aren't lifted (the owner, 2026-11-22: claims later).
