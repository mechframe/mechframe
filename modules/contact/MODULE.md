# contact

The site's contact form, and the Inbox where its people read each message. The contract is `dev plans/contracts/contact.md`.

## What it does

A visitor writes from `/contact`: their name, their email, what it's about (a topic from Settings), the message, and, while `campaigns` is on, "Send me news and releases too". The form carries the kernel's bot check (hook 5), and the sender is thanked the same way whether the message passed or was held, so a bot learns nothing.

**A message that passes is `new`.** Everyone who may read the Inbox gets a notice in the site and by email (each can turn the email off), naming the topic and the sender and linking to the message (decision 0059's `notify_holders`). The message itself stays on the site. When the sender asked for news, `contact.news.requested` goes to `campaigns`.

**A message is held as `spam`, with its reason, when** the bot check holds it (its trap, a fill faster than a person types, no proof at all) or the site's word and link filters do (`kernel.moderation`). Nobody is told, and nothing is dropped.

**In the Inbox,** under Content, the site's people:
- see "n new messages are waiting" while any is new: a warning once the oldest has waited 2 days, and the Dashboard shows the same;
- work through the tabs All, New, Replied, Archived and Spam, with a new message on a first topic before the rest;
- open a message beside the list;
- reply from their own email (`mailto:`), then Mark as replied, Archive, move it to Spam or let it out with Not spam (which tells people then, once), or Delete it for a sender who asks to be forgotten;
- export a tab as a CSV.

## Use when / avoid when

Use it when visitors should reach the site's people without an account, each message saying what it's about. Avoid it for members talking to each other or to staff in threads (a chat or community module), for tickets with owners, notes and replies sent from the site (a help desk), and for a form that only takes an address for news (`campaigns`' sign-up).

## What it adds

- **Routes**, under `/api/contact`:
  - **Public:**
    - `GET /form`: `{intro, topics}`.
    - `POST /messages`: `{name, email, topic, message, wants_news, bot}`. It answers 202 `{received: true}`, passed or held; 422 with field errors (`body.email`, `body.topic` ...); and 429 `kernel.rate_limited` after 5 an hour from one address.
  - **With `contact.message.manage`:**
    - `GET /admin/messages?status=&cursor=&limit=`: a page of a tab, 50 by default and 100 at most, with every tab's count and the waiting item.
    - `GET /admin/messages/{id}`.
    - `POST /admin/messages/{id}/status`: `{status}`, audited.
    - `DELETE /admin/messages/{id}`: audited.
    - `GET /admin/messages/export?status=`: every message in a tab, audited. The Inbox makes the CSV from it.
- **The public page:** `/contact`, the heading, Settings' intro and the form. The server copy answers it with a `ContactPage` JSON-LD and lists it in the sitemap. A site's own `/contact` route wins it.
- **For a site's own page:** `ContactForm` (`{onSent?}`), from `@/modules/contact/public` (decision 0057).
- **Menus and pages:**
  - Contact in `nav.footer`.
  - Inbox in `nav.admin` under Content: `/admin/contact` and `/admin/contact/:id`.
  - The Settings section "Contact form" (`admin.settings.section`).
- **The table:** `contact_message`, migration `contact_0001`, on the branch `contact`.
- **The permission:** `contact.message.manage`, granted to admin in the migration. An owner holds every permission.
- **The notice:** `contact.message_received` (both, by default).
- **The event:** `contact.news.requested` v1 `{message_id, email, name}`.
- **The job:** `contact.prune`, daily at 03:20 UTC. Spam goes after 30 days, every other message 2 years after its last change.
- **Hooks:**
  - bot check, `contact.message`;
  - export and erase: a person's messages by address (in any case) or by account, listed, then deleted;
  - seed: a message in each tab and one the filters held, telling nobody;
  - dashboard: `contact.waiting`.

## Settings and env vars

- `intro`: the line under the Contact page's heading, and the page's description.
- `topics`: 1 to 12 of `{key, label, first}`, in the form's order. The defaults are A question, Working together (first), Press and Something else. A message keeps the label it was sent with.

No env vars.

## Install notes

`mechframe add contact`, then the migrations. It needs nothing beyond the kernel. A site whose own footer is drawn by itself places `<SlotOutlet name="nav.footer" />` to show Contact there. A site builds its own Contact page around `ContactForm` when it wants more on the page than the form.

## Extension points

`contact.news.requested`, for a newsletter module to ask the address to confirm. The bot check's provider is the kernel's (a module's `BOT_PROVIDER`, such as Turnstile later).

## Known limits

- No reply from inside the site, no assignment, notes or read and unread: a message is new until it's replied to or archived.
- No attachments, and no Company or Phone fields.
- A topic's label is kept per message, but its key isn't checked against Settings once the message is in.

## Source and license

Lifted from VybeSite at `f659d7c`:
- `backend/app/routers/contact_form.py` (the form's route, its limit of 5 an hour, the same answer for a held message, Not spam);
- `backend/app/schemas/contact_form.py`;
- `backend/app/services/contact_filter.py` (now the kernel's bot check, hook 5);
- `backend/app/services/contact_alerts.py` (now a notice to the Inbox's readers, decision 0059);
- `frontend/src/pages/admin/ContactInbox.tsx` and `frontend/src/site/components/ContactForm.tsx`.

Reshaped to the canvas's Contact and AdminInbox boards. The owner's code, proprietary.
