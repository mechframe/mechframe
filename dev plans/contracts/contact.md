---
feature: The contact module, the site's contact form and the admin's Inbox (Vibrant Mindz step 1; M5's first job)
status: approved
plan: `docs/plans/vibrant-mindz-backend/extraction/contact.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M5); the site's Contact board and the canvas's AdminInbox board (`C:\DEV\VM Website\design\site\Contact.dc.html`, `AdminInbox.dc.html`); `C:\DEV\VM Website\design\specs\site-pages.md` (Contact's row)
approved: 2026-11-22, all four of §8 as recommended (the owner: "Yes, as recommended")
pr: one, after `blog`'s first (#123 predicted), numbered at push time
---

# Contract: `contact`

## 1. Goal

A visitor writes to the site from `/contact`: name, email, what it's about (a booking, press, a commission...), the message, and "Send me news and releases too". The site's people read each message in Admin › Content › Inbox, reply from their own email, and mark it replied, archive it or set it aside as spam. A bot's message never reaches them. Lifted from VybeSite (`routers/contact_form.py`, `schemas/contact_form.py`, `services/contact_filter.py`, `services/contact_alerts.py`, `pages/admin/ContactInbox.tsx`, `site/components/ContactForm.tsx`), reshaped to the board and the kernel's hooks. VybeSite's `contact_service.py` is the mailing list, not this: it comes with `campaigns`.

## 2. Interfaces

**Permission:** `contact.message.manage` (owner, admin; §8, 2) to read, mark, archive, delete and export messages. Granted in `contact_0001`.

**Settings** (`schemas.py`'s `Settings`, the section `contact`): `intro` (≤ 300, "Send a message and we'll reply by email.") and `topics`, 1 to 12 of `{key, label, first}`: `key` a slug ≤ 40, `label` ≤ 80, `first` a bool. The defaults are A question, Working together (`first`), Press and Something else. They're edited in the Settings section "Contact form" (`admin.settings.section`): the intro, then each topic's label, order and First switch, added and removed. A message keeps the label it was sent with, so renaming or removing a topic changes no old message.

**HTTP** (`/api/contact`, behind `require_module("contact")`; codes `contact.*`):

| Route | Access | Does |
| --- | --- | --- |
| `GET /form` | public | `{intro, topics: [{key, label}]}` |
| `POST /messages` `{name, email, topic, message, wants_news, bot}` | public, `rate_limit("5/1h")` (VybeSite's) | 202 `{received: true}`, the same for a message held as spam. 422 with field errors: `name` 1 to 200, `email` one address as sign-up checks it (`email.is_address`, ≤ 254), `topic` one of the settings' keys, `message` 1 to 5,000. 429 `kernel.rate_limited` |
| `GET /admin/messages?status=&cursor=` | manage | `{items: [{id, name, topic_label, first_line, status, first, received_at}], next_cursor, counts: {new, replied, archived, spam}, waiting}`. `status` is `all` (the default: everything but spam), `new`, `replied`, `archived` or `spam`. A new message on a `first` topic comes first, then newest first, 50 a page. `waiting` is the attention item below, or null |
| `GET /admin/messages/{id}` | manage | `{id, name, email, topic_label, message, wants_news, status, held_reason, received_at, status_at}` |
| `POST /admin/messages/{id}/status` `{status}` | manage | To `replied`, `archived`, `spam` or `new` (the Spam tab's Not spam). Audited `contact.message.status`, with no address in its details |
| `DELETE /admin/messages/{id}` | manage | 204, audited `contact.message.deleted` (§8, 3) |
| `GET /admin/messages.csv?status=` | manage | The tab as a CSV download. A cell starting `=`, `+`, `-` or `@` gets a leading `'`. Audited `contact.messages.exported` with the count |

**What happens to a message,** in the route's transaction: `bot.verify(request, body.bot, form="contact.message", db=db)` (hook 5), then `moderation.screen(db, name + message)`, the site's word and link filters. Either holding it stores it as `spam` with the reason (`honeypot`, `too_fast`, `not_from_form`, `provider_error`, `term`, `domain`, `links`), and nobody is told. A message that passes is `new`, and everyone holding `contact.message.manage` gets the notice `contact.message_received` (§8, 1). Not spam later sends that notice then, which VybeSite never did, and never twice (`notified_at`).

**Newsletter sign-up:** a message with `wants_news` that passes, or is let out of spam, emits `contact.news_requested` v1 `{message_id, email, name}` for `campaigns` (M5) to act on. The form draws the box only while `campaigns` is on (`useModuleEnabled`). The Inbox shows "Wants the newsletter" either way.

**Public page:** `routes.public` `["/contact"]`, drawn as the board: the heading, the intro, the form, field errors under their fields, and the sent state ("Message sent", "Thanks for writing. We'll reply by email.", Send another). The form draws the kit's `<BotFields />` (SPEC 8). `server_copy.py` answers `/contact` with `ContactPage` JSON-LD and the intro as its description. `nav.footer` gets Contact. `web/public.ts` exports `ContactForm` (`{onSent?}`), so a site can build its own Contact page around it as `@/modules/contact/public` (decision 0057). Vibrant Mindz will, for its Bookings, Commissions and Follow cards. A site's own route wins the tie with `/contact` (SPEC 8).

**Admin page:** `/admin/contact` and `/admin/contact/:id`, under Content as Inbox (`nav.admin`). It follows the board: the intro line, Export, the waiting card, the five tabs with their counts, the list, and the open message beside it (alone on a phone, with Back). The open message has Reply by email (`mailto:` with "Re: <topic>"), Mark as replied, Archive, Spam (or Not spam), Delete, and the board's note "Replies go from your own email, so the conversation carries on there."

**Hooks:** bot check (`contact.message`); export and erase (`privacy.py`: a person's messages found by address or account; erase deletes them); seed (one message in each status and one held, `@example.com` senders, fixed ids); dashboard `ATTENTION` `contact.waiting`, while any message is new: "n new messages are waiting", the oldest's wait in its why, Open the first. It's `info`, then `warning` once the oldest has waited 2 days. No lifecycle, taxonomy, search or consent: messages aren't public.

**The kernel's addition** (decision 0059, in this PR; §8, 1): `notifications.notify_holders(db, permission, key, context, *, link=None) -> list[uuid.UUID]`. It gives the notice to every active account holding `permission`, by the owner's role or a role that grants it, each once and as that person chose for `key`, and answers the people it reached. Comments, campaigns and the shop will need it too.

## 3. Data

`contact_message`:
- `id` uuid
- `received_at` timestamptz
- `name` varchar(200)
- `email` varchar(254), trimmed, with an index on `lower(email)` so export and erase find it case-blind
- `topic` varchar(40) and `topic_label` varchar(80)
- `message` text, with a CHECK of 5,000 or fewer
- `wants_news` bool
- `status` varchar(16), with a CHECK: `new`, `replied`, `archived` or `spam`
- `held_reason` varchar(40), null
- `status_at` timestamptz
- `notified_at` timestamptz, null
- `user_id` → `auth_user` `ON DELETE SET NULL`, null: the sender, if signed in

There's an index on (`status`, `received_at`). The branch is `contact`, migration `contact_0001`, with `depends_on` `kernel_0015`. The job `contact.prune` runs daily and keeps §8, 3's retention.

## 4. Files

`modules/contact/`, laid out as `pages` is:
- **Backend:** `models`, `schemas`, `service`, `router`, `events`, `emails`, `jobs`, `dashboard`, `privacy`, `seed` and `server_copy`.
- **Web:** `module.web.ts`, `public.ts`, `ContactForm.tsx`, and the pages `ContactPage`, `AdminInbox` and `ContactSettings`.
- **Tests:** `tests/backend`, `contract`, `web` and `e2e`.

Also `schema/events/contact.news_requested.v1.schema.json`. The kernel's addition is `kernel/backend/kernel/notifications.py`, its tests, and SPEC 6's row.

## 5. Conventions this follows

- SPEC 4 to 11 and 15.
- `hooks.md` for the bot check, export and erase, seed and dashboard.
- `mechframe-module-extractor` and `module-contract-lint`, and the brand check on what's lifted.
- `pages` as the pattern for the server copy, the registries fixture and the admin page.

## 6. Non-goals

- Replying from inside the site. VybeSite has it, but the board replies from your own email.
- Assigning a message to someone, notes, read and unread, or sending a topic to particular people.
- Attachments, and VybeSite's Company and Phone fields: neither is on the board.
- Sending news itself: that's `campaigns`.
- A captcha. Turnstile comes later as a `BOT_PROVIDER` (hook 5).

## 7. Acceptance

**Contract tests:**
- Every route's access, and 404 while the module is off.
- The field errors, and a topic the settings don't have.
- The same 202 for a message that passes and one held: by the trap, too fast, or a held word.
- The sixth message in an hour gets 429.
- Each status change is audited. Not spam tells people once. Delete works.
- The CSV escapes formula cells.

**Notices and events:**
- Each holder gets the notice. Someone without the permission gets none, and so does a held message.
- The kernel's `notify_holders` reaches the owner's role and a granting role, each person once, and skips other roles and suspended accounts.
- `news_requested` goes only for `wants_news` and a message that wasn't held, or on its release.

**The rest:**
- The prune keeps §8, 3's periods.
- The migration's round trip, the seed twice the same, export and erase by address and by account, and the waiting item.
- **Web:** `/contact` (empty, with field errors, sent, and Send another) and the Inbox (each tab, a message open, an empty tab), in both themes and axe clean. `ContactForm` works through `@/modules/contact/public`.
- `validate_schemas`, `module-contract-lint` and the brand check pass. `mechframe add contact`, then `mechframe check`, passes on a new site.

## 8. The owner's answers

Answered 2026-11-22, all four as recommended:

1. **Who is told about a new message:** everyone who may read the Inbox, by a notice in the site and by email (each can turn the email off), naming the topic and the sender; the message stays on the site. Through the kernel's `notify_holders` (decision 0059). Not VybeSite's one address.
2. **Who may read the Inbox:** owner and admin (`contact.message.manage`), since every message holds someone's address. Not editors.
3. **How long messages are kept:** spam is deleted after 30 days, every other message 2 years after its last change (`contact.prune`, daily), and the Inbox has a Delete button, not drawn on the board, for a sender who asks to be forgotten.
4. **Vibrant Mindz's topics:** the board's five, Booking a show, Press and interviews, Commissioning artwork, Licensing a beat and Something else, with Booking a show and Commissioning artwork marked First. They're the site's to set in Settings → Contact form (or its own seed); the module's defaults stay generic.

## Changes after approval

- 2026-11-22, in the build:
  - **The event is `contact.news.requested`** (`schema/events/contact.news.requested.v1.schema.json`). An event's name is `<id>.<entity>.<action>`, the manifest schema's pattern, and `contact.news_requested` isn't.
  - **Export is `GET /admin/messages/export?status=`.** It answers the tab's messages as JSON (`InboxExport`), and the Inbox makes the CSV in the browser, a formula cell given its leading `'` there. Every API answer is a typed object (`tests/test_openapi.py`).
  - **`email_normal`, a column, is indexed** in place of an index on `lower(email)`, as `auth_user` keeps its address. The models-against-migrations check can't compare an expression index.
  - `contact_0001` depends on `kernel_0002`, the auth tables it needs, as `pages_0001` does.
  - **The answers' schema names are the module's own** (`ContactForm`, `InboxPage`, `InboxMessage` and the rest). A second `Full` or `Listed` would rename pages' in its committed OpenAPI.
  - A topic Settings doesn't have is the field error `body.topic`, as the kernel keys a body's fields.
- 2026-11-22: `notify_holders` holds by role alone, and answers the people it reached rather than a count. Overrides are per resource (SPEC 14.8), and a notice about the site as a whole has none (decision 0059).
