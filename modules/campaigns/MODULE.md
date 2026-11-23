# campaigns

The site's newsletter and release announcements. The contract is `dev plans/contracts/campaigns.md`.

## What it does

**People ask for the news** from a sign-up form on a page (`NewsletterSignup`), or from the contact form's "Send me news and releases too" (`contact.news.requested`). A new or unconfirmed address is `pending` and gets a confirmation email; nothing else is mailed to it until its link is clicked (double opt-in). The answer to a sign-up is the same whatever the address's state, so nobody learns who's subscribed. A pending address asked again within 10 minutes isn't sent a second confirmation, so a form can't flood someone's inbox. A sign-up the bot check holds (hook 5) is kept as pending and sent nothing; the prune takes it after 30 days. A sign-up joins the signed-in person's account only when it's their own verified address.

**The site's people write an email** in Admin › Content › Newsletter: Subject, Preview text, Kind (Newsletter or Release announcement) and the body in Markdown, with Preview. They send themselves a test, marked [Test] and counted nowhere, then Send now or Schedule it. A save someone else got to first asks which to keep, field by field. Once it's sent, the email is read-only: "Sent to n people, <when>".

**A post's email:** when a writer publishes a post with "Email it to subscribers" (`blog.post.published`), its title, summary and link go to the subscribers at once, an email like any other; it signs nobody up.

**A send fixes its audience** as it starts: one row per address subscribed and not set aside, unique per email and address, so a job run twice sends nobody twice. The job `campaigns.send` runs each minute and queues a sixtieth of `send_per_hour` (at least one), counted over the last minute and never past `send_per_hour` in the hour, so Send now's extra run never doubles the pace and a setting under 60 holds. A copy whose token no key opens goes unsent, and nobody else waits on it. Before each copy it asks again: still subscribed, not set aside. Each copy carries the person's own unsubscribe link and RFC 8058's one-click headers, through the kernel's mail queue (decision 0062). Nothing sends without the postal address (CAN-SPAM), and an email too long once rendered for the mailer is refused at Send. One run at a time holds the pace (an advisory lock).

**An address that bounces, complains or unsubscribes is set aside** for good: never emailed again, and the row is never deleted, even when the person is erased. Bounces reach the site one of two ways:
- **By SMTP** (the default, decision 0033): the job `campaigns.bounces` reads the bounce mailbox over IMAP every 15 minutes while its variables are set. It asks the server for messages whose Content-Type is `multipart/report`, peeks at each one's header, opens only bounce reports (RFC 3464) and spam reports (RFC 5965), and moves each to a folder of read ones. Nothing else is opened, marked read or moved.
- **By Resend**, only where the host blocks SMTP: its signed webhook.

Either way, VybeSite's classifier decides: a permanent failure about the recipient's address (`5.1.x`) or a spam report sets it aside; a soft bounce, a block about the sender or the message (`x.7.x`, `5.1.7`, `5.1.8`, the words blocked, spam, policy, reputation…) and anything unclear don't. Only the newsletter's own addresses are set aside: a bounce about a sign-in link or a notice is left alone. A report from the mailbox counts only when it returns that address's own copy, its unsubscribe token in the returned copy's List-Unsubscribe header or in a link in its returned body, since anyone can mail the mailbox a forged one. Resend's webhook is signed, and its word stands for an address queued a newsletter copy with the subject its event names: its events carry the subject, not the headers. A Resend bounce with no status code is unclear, and sets nobody aside.

## Use when / avoid when

Use it when people should ask for the site's news by email and the site's people send it themselves, now or at a set time, and when a new blog post should go to the subscribers. Avoid it for segmented, A/B-tested or tracked mail (a marketing platform), for a person hearing about something they did (the kernel's notifications), and for members talking to each other (a chat or community module).

## What it adds

- **Routes**, under `/api/campaigns`:
  - **Public:**
    - `GET /signup`: `{open}`, whether sign-ups are open (`useNewsletterOn()`).
    - `POST /subscribe` `{email, name?, source, bot}`: 202 `{received: true}`; 422 field errors; 409 `campaigns.closed`; 429 after 5 an hour from one address.
    - `POST /confirm` `{token}`: `{email_hint, subscribed}`; 404 `campaigns.unknown_link`.
    - `GET /unsubscribe?token=`: `{email_hint, subscribed}`, changing nothing.
    - `POST /unsubscribe?token=`: unsubscribes and sets aside; takes the page's button and RFC 8058's one-click POST alike; a second time answers the same.
    - `POST /webhooks/resend`: Resend's bounces and complaints, Svix-signed; 401 `campaigns.bad_signature` without the secret or with a bad signature; 409 `campaigns.replayed`.
  - **With `campaigns.email.manage`:** `GET /admin/emails?status=&cursor=&limit=` (the Emails tab, the cards, the attention card and what the page warns of), `POST /admin/emails`, `GET`/`PATCH /admin/emails/{id}` (`version`; 409 `campaigns.changed` with the email now, 409 `campaigns.sent` once it's sending), `POST /admin/emails/{id}/preview` `{body}`, `POST /admin/emails/{id}/test` (10 an hour), `POST /admin/emails/{id}/send` `{at?}` (409 `campaigns.no_address`, `campaigns.nobody`, `campaigns.not_draft`), `POST /admin/emails/{id}/cancel`, `DELETE /admin/emails/{id}` (a draft only).
  - **With `campaigns.subscriber.manage`:** `GET /admin/subscribers?status=&cursor=&limit=`, `POST /admin/subscribers/{id}/set-aside` `{why, detail?}`, `DELETE /admin/subscribers/{id}` (keeps the address set aside), `GET /admin/set-aside?cursor=&limit=`.
- **Public pages:** `/newsletter/confirm` and `/newsletter/unsubscribe`, each with one button; the server copy answers both `noindex`, and neither is in the sitemap.
- **For a site's own sections:** `NewsletterSignup` (`{heading?, words?, source?, button?}`), `useNewsletterOn()` and `useSubscribe()`, from `@/modules/campaigns/public` (decision 0057).
- **Menus and pages:** Newsletter in `nav.admin` under Content (`/admin/campaigns`, the editor at `/admin/campaigns/new` and `/admin/campaigns/:id`); the Settings section "Newsletter".
- **Tables:** `campaigns_subscriber`, `campaigns_set_aside`, `campaigns_email`, `campaigns_delivery` and `campaigns_webhook_seen`, migration `campaigns_0001` on the branch `campaigns`.
- **Permissions:** `campaigns.email.manage` and `campaigns.subscriber.manage`, granted to admin in the migration; an owner holds every permission.
- **Events heard:** `contact.news.requested` v1 and `blog.post.published` v1, each delivery taken once.
- **Jobs:** `campaigns.send` each minute, `campaigns.bounces` every 15 minutes, `campaigns.prune` daily at 03:40 UTC (unconfirmed sign-ups and a send's queued rows after 30 days; an email keeps its count; and every token sealed again with the newest of `ENCRYPTION_KEYS`, so the key before can leave the day after a new one goes in front).
- **The email template:** `campaigns.confirm`.
- **Hooks:** bot check `campaigns.subscribe`; export and erase by address or account, erasing the address from every send's rows and leaving a set-aside row; seed (subscribers in each state, two addresses set aside, a draft, a scheduled and a sent email, all `@example.com`); dashboard `campaigns.set_aside` and `campaigns.no_address`.

## Settings and env vars

- `signups_open` (true): while it's off, the forms say sign-ups are closed.
- `postal_address` (""): the postal address every newsletter carries, its lines kept; a P.O. box will do. Nothing sends until it's set.
- `footer_note`: the footer's first line, `${site_name}` filled in.
- `send_per_hour` (400): 1 to 10,000. A paid Spacemail mailbox sends at most 500 an hour (20 on a trial), the site's own mail included, so 400 leaves it room; a host with another limit sets its own.

Env vars, all optional, typed into the host's variables by the owner:
- `CAMPAIGNS_BOUNCE_IMAP_HOST` (`host` or `host:port`, 993 by default), `CAMPAIGNS_BOUNCE_IMAP_USERNAME`, `CAMPAIGNS_BOUNCE_IMAP_PASSWORD`: the bounce mailbox. On Spacemail and most mailbox hosts it's the sending mailbox itself. Without all three, the Set aside tab says bounces aren't being read.
- `CAMPAIGNS_BOUNCE_IMAP_FOLDER`: where a read report goes, "Newsletter bounces" by default (a server that wants folders under the inbox takes `INBOX.Newsletter bounces`).
- `CAMPAIGNS_RESEND_WEBHOOK_SECRET`: only for a site sending by Resend; the webhook's `whsec_…` secret.

## Install notes

`mechframe add campaigns`, then the migrations. It needs nothing beyond the kernel; contact's news box and blog's "Email it to subscribers" reach it by events. Put the postal address in Settings › Newsletter before the first send. A site draws `NewsletterSignup` in its own sections (Music's "New music in your inbox", Blog's, Videos'), giving each a `source` so the Subscribers tab says where people signed up.

## Extension points

- `NewsletterSignup`, `useNewsletterOn()` and `useSubscribe()` in `public.ts`.
- The kind `release`, for `discography` to make when a release goes out (later).

## Known limits

- **No opens, clicks, link rewriting or tracking pixels,** no segments, tags, A/B subjects, imports or replies (§6).
- **The From is the site's `MAIL_FROM`;** no Reply-To of its own.
- **The email's colours are campaigns' own neutral palette,** not the site's theme: the backend doesn't know the theme. A theme-aware frame waits for the kernel to give the theme's values to the backend.
- **A post's email holds its title and link;** its summary too once blog's `blog.post.published` payload carries one (v1 doesn't).
- **A bounce that isn't an RFC 3464 report** (some servers send plain text) isn't read; set the address aside by hand.
- **NewsletterSignup is checked in a browser only through its web tests:** no harness page draws it. Its first browser check is a site's own section.

## Source and license

Lifted from VybeSite at `f659d7c`, reshaped to the contract:
- `backend/app/services/bounce_classifier.py`: the rules, from Mailgun's events to RFC 3464 and 5965 reports and Resend's webhook;
- `backend/app/services/suppression_service.py`: one gate every send passes, addresses compared lowercased, nothing ever lifted;
- `backend/app/services/campaign_service.py`: the audience fixed once, and each recipient asked again before their turn;
- `backend/app/services/render_service.py`: the footer, the preheader and RFC 8058's headers;
- `backend/app/routers/tracking.py`: the unsubscribe page that changes nothing until its button is pressed.

Proprietary (VybeCode Software).
