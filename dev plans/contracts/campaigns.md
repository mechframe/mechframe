---
feature: The campaigns module, the site's newsletter and release announcements (Vibrant Mindz step 1; M5's third job)
status: approved; §8 answered by the owner on 2026-11-22
plan: `docs/plans/vibrant-mindz-backend/extraction/campaigns.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M5); the canvas's AdminNewsletter board (`C:\DEV\VM Website\design\site\AdminNewsletter.dc.html`), the newsletter sections on Music, Blog and Videos, Contact's news box and AdminPost's "Email it to subscribers"
approved: 2026-11-22, by the owner, after a summary ("Fuller and then approved")
pr: one, after `embeds`' (#127), numbered at push time
---

# Contract: `campaigns`

## 1. Goal

People ask for the site's news: from a newsletter form on a page, from the contact form's "Send me news and releases too", or when a writer publishes a post with "Email it to subscribers". The site's people write an email in Markdown in Admin › Content › Newsletter, send themselves a test, and send it now or at a set time. Every subscriber gets their own copy, with a one-click unsubscribe. An address that bounces, complains or unsubscribes is set aside and never emailed again.

Lifted from VybeSite's campaigns, kept to what the board draws and what delivery and the law need:
- `campaign_service` for the audience and the batched sends;
- `suppression_service` for the send gate;
- `bounce_classifier`;
- `render_service`'s footer and unsubscribe headers;
- `tracking.py`'s unsubscribe confirm page.

VybeSite's opens and clicks, A/B subjects, holdouts, tags, imports, seed inboxes, sign-off and reply handling stay behind (§6). VybeSite has no sign-up form and no confirmation email; this module adds both (§8, 2).

## 2. Interfaces

**Permissions:**
- `campaigns.email.manage`: write, test, schedule and send emails, and see the counts;
- `campaigns.subscriber.manage`: see the Subscribers and Set aside tabs, and remove a subscriber.

Both go to owner and admin (§8, 4), granted in `campaigns_0001`.

**Settings** (the section `campaigns`):
- `signups_open`: a bool, true by default. It's the board's "Sign-ups open" pill; while it's off, the forms say sign-ups are closed.
- `postal_address`: ≤ 300 characters. US law (CAN-SPAM) puts a postal address in every newsletter; a P.O. box will do. Nothing sends until it's set, and the Newsletter page says so.
- `footer_note`: ≤ 300 characters, by default "You're getting this because you asked for news from ${site_name}."
- `send_per_hour`: how many newsletter messages may go out in an hour, 1 to 10,000, and 400 by default (the owner, 2026-11-23: under a Spacemail mailbox's 500 an hour, with room for the site's own mail). A trial mailbox (20 an hour) or a host with another limit sets its own.

They're edited in the Settings section "Newsletter".

**HTTP** (`/api/campaigns`, behind `require_module("campaigns")`; codes `campaigns.*`):

| Route | Access | Does |
| --- | --- | --- |
| `POST /subscribe` `{email, name?, source, bot}` | public, `rate_limit("5/1h")` | 202 `{received: true}` whatever the address's state, so nobody learns who's subscribed. A new or unconfirmed address is `pending` and gets the confirmation email (§8, 2). `source` is `form` or a site's own short name for its form (≤ 40). 422 field errors; 409 `campaigns.closed` while sign-ups are closed |
| `POST /confirm` `{token}` | public | The subscription confirmed: `subscribed`. 404 for a token it doesn't know |
| `GET /unsubscribe?token=` | public | `{email_hint, subscribed}`, changing nothing: link scanners open links |
| `POST /unsubscribe?token=` | public | Unsubscribes and sets the address aside. It takes the page's button and RFC 8058's one-click POST alike, and answers the same if it's done already |
| `GET /admin/emails?status=&cursor=` | email.manage | `{items: [{id, subject, kind, status, sent_to, when}], next_cursor, counts, scheduled, waiting}`: the Emails tab, the three stat cards and the attention card |
| `POST /admin/emails`, `GET`/`PATCH /admin/emails/{id}` | email.manage | A draft: `{kind, subject, preview, body, version}`. `kind` is `newsletter` or `release`; `subject` 1 to 150; `preview` ≤ 150; `body` Markdown ≤ 100,000. A save sends `version`; a crossed save is 409 with both versions, as blog's is |
| `POST /admin/emails/{id}/preview` `{body}` | email.manage | The email's HTML, as a subscriber gets it, for the editor's Preview |
| `POST /admin/emails/{id}/test` | email.manage | Sends it to the person asking, marked [Test], counted nowhere. `rate_limit("10/1h")` |
| `POST /admin/emails/{id}/send` `{at?}` | email.manage | Now, or `scheduled` for `at` in the site's time zone. 409 `campaigns.no_address` without the postal address; 409 `campaigns.nobody` with no subscriber. Audited `campaigns.email.sent` or `.scheduled` with the count |
| `POST /admin/emails/{id}/cancel` | email.manage | Back to a draft while it's `scheduled`; once it's sending, it stops queueing the rest. Audited |
| `DELETE /admin/emails/{id}` | email.manage | A draft only. 204, audited |
| `GET /admin/subscribers?status=&cursor=` | subscriber.manage | The Subscribers tab: `{items: [{id, email, name, source, status, since}], next_cursor, counts}` |
| `POST /admin/subscribers/{id}/set-aside` `{why, detail?}` | subscriber.manage | Sets an address aside by hand: an address that bounced where nothing reads bounces, or one a person asked to stop by other means. Audited |
| `DELETE /admin/subscribers/{id}` | subscriber.manage | Removes a person who asks to be forgotten, keeping a set-aside row so they're never emailed again. Audited with no address |
| `GET /admin/set-aside?cursor=` | subscriber.manage | The Set aside tab: `{items: [{email, why, since}], next_cursor}` |
| `POST /webhooks/resend` | Resend, signed | Only for a site that sends by Resend, because its host blocks SMTP: bounces and complaints. The signature is checked first and fails closed without the secret. A replayed delivery is refused. A permanent bounce or a complaint sets the address aside |

**Sending:**
- `send` fixes the audience: every `subscribed` address not set aside, one `campaigns_delivery` row each, unique per email and address, so a job that runs twice sends nobody twice.
- The job `campaigns.send` runs each minute and queues a sixtieth of `send_per_hour`, at least one. On a host with a limit, the pace keeps a send under it with room left for the site's own mail, since sign-in links and the contact form's notices go out through the same mailbox. For each recipient it checks again that they're still subscribed and not set aside, then hands the message to the kernel's mail queue with its own unsubscribe link and RFC 8058's headers.
- The email is `sent` once every row is queued. Its "Sent to" counts the rows queued.
- A scheduled email starts at its time: a scheduled job looks each minute for one that's due.
- **Bounces by SMTP** (§8, 5): the job `campaigns.bounces` reads the bounce mailbox every 15 minutes while its three variables are set. It takes each bounce report (RFC 3464) and spam report (RFC 5965), sets the address aside by VybeSite's classifier, and moves the message to a folder of read ones. On Spacemail, and most mailbox hosts, a bounce comes back to the sending mailbox itself, so the reader logs in to that same mailbox. It looks at headers only to find bounce and spam reports. It opens nothing else and marks nothing else read, so the mailbox's other mail stays as it was. A permanent recipient failure (`5.1.x` about the recipient) or a spam report sets the address aside; a soft bounce, and a block that's about the sender, don't. Without the variables, the Newsletter page says "Bounces aren't being read" under Set aside.

**The email:**
- The body is Markdown made HTML by `kernel.markdown.render`, with a plain-text part from `kernel.markdown.plain`, in a single-column frame with inline styles (§5).
- Under it come the footer note, the site's name, the postal address and "Unsubscribe".
- The preview text is the inbox's preheader.
- Links aren't rewritten and nothing tracks opens (§6).

**Events listened to:**
- `contact.news.requested` v1 `{message_id, email, name}`: that address becomes `pending` from the source `contact` and gets the confirmation email, unless it's subscribed or set aside already.
- `blog.post.published` v1, with `email_subscribers` true: an email of kind `newsletter` titled with the post's title, holding its summary and a link to its path, which sends at once (§8, 3).

Both are at least once: a second delivery changes nothing.

**Public pages:**
- `routes.public` `["/newsletter/confirm", "/newsletter/unsubscribe"]`: each says what its token is for, with one button (Confirm, Unsubscribe), then the done state. The server copy answers both `noindex`.
- `web/public.ts` exports `NewsletterSignup` (`{heading?, words?, source?, button?}`) for a site's own sections, as `@/modules/campaigns/public`: Music's "New music in your inbox", Blog's and Videos'. It draws the kit's `<BotFields />` and one field, "Email", then the sent state: "Check your inbox" and a line saying a confirmation is on its way.
- `useNewsletterOn()` tells a site's other forms, such as contact's box, whether sign-ups are open.

**Admin page:** `/admin/campaigns`, under Content as Newsletter (`nav.admin`), follows the board:
- the intro line and New email;
- the attention card "n addresses bounced and were set aside" with See them;
- the cards Subscribed, Scheduled and Set aside;
- the tabs Emails, Subscribers and Set aside, with the board's columns and pills.

**The editor,** `/admin/campaigns/new` and `/admin/campaigns/:id`, isn't drawn. It's built in the board's language, as blog's editor is: Subject, Preview text, Kind, the kit's `MarkdownEditor` with Preview, Send a test to me, then Send now or Schedule, with a date and time. Once it's sent, the email is read-only with "Sent to n people, <when>".

**Hooks:**
- bot check: `campaigns.subscribe`;
- export and erase: a person's subscription, by address or account; erasing it leaves a set-aside row;
- seed: subscribers in each state, a draft, a scheduled and a sent email, and a set-aside address, all `@example.com`;
- dashboard `ATTENTION` `campaigns.set_aside`, while an address bounced in the last 7 days, and `campaigns.no_address` while the postal address is missing and someone is subscribed.

There's no lifecycle, taxonomy or search: emails aren't public pages.

**The kernel's addition** (decision 0062, in this PR): `email.queue_message(db, to, subject, text, html=None, headers=None)` joins the kernel's public surface (SPEC 6). It's the message as already rendered, with only RFC 8058's two headers allowed, as `kernel.notifications` uses it today.

## 3. Data

**`campaigns_subscriber`:**
- `id`, `email` (≤ 254) and `email_normal` (unique), and `name` (≤ 200, null);
- `source` (≤ 40) and `status`: `pending`, `subscribed` or `unsubscribed`;
- `token_hash`: the sha256 of a random token, which names the subscription in the confirm and unsubscribe links;
- `confirm_sent_at`, `confirmed_at`, `unsubscribed_at` and `created_at`;
- `user_id` → `auth_user` `ON DELETE SET NULL`.

A `pending` row that isn't confirmed within 30 days is deleted by the daily `campaigns.prune`.

**`campaigns_set_aside`:** `email_normal` (the key), `why` (`bounced`, `complained` or `unsubscribed`), `detail` (≤ 300) and `since`. It's never deleted, so a set-aside address is never emailed again.

**`campaigns_email`:**
- `id`, `version`, `kind`, `subject`, `preview` and `body`;
- `status`: `draft`, `scheduled`, `sending` or `sent`;
- `send_at`, `started_at`, `sent_at` and `sent_to`;
- `post_id` (null; blog's post, with no foreign key across modules) and `created_by` → `auth_user` `ON DELETE SET NULL`;
- `created_at` and `updated_at`.

**`campaigns_delivery`:** `id`, `email_id` → `campaigns_email` `ON DELETE CASCADE`, `subscriber_id` → `campaigns_subscriber` `ON DELETE SET NULL`, `email_normal` (frozen at send), `queued_at`, and a unique (`email_id`, `email_normal`).

**`campaigns_webhook_seen`:** a delivery id and the time, kept 7 days, against replays.

The branch is `campaigns`, migration `campaigns_0001`, with `depends_on` `kernel_0002`.

## 4. Files

`modules/campaigns/`, laid out as `contact` is:
- **Backend:** `models`, `schemas`, `service`, `sending`, `render`, `bounces` (the mailbox reader and the classifier), `webhooks` (Resend's), `router`, `events`, `emails` (`campaigns.confirm` and the email's frame), `jobs`, `dashboard`, `privacy`, `seed` and `server_copy`.
- **Web:** `module.web.ts`, `public.ts`, `NewsletterSignup.tsx`, and the pages `AdminNewsletter`, `AdminEmail`, `ConfirmPage`, `UnsubscribePage` and `NewsletterSettings`.
- **Tests:** `tests/backend`, `contract`, `web` and `e2e`.

The kernel's addition is `email.queue_message` in SPEC 6's table, its test, and decision 0062.

## 5. Conventions this follows

- SPEC 4 to 11 and 15, and `hooks.md` for the bot check, export and erase, seed and dashboard.
- `mechframe-module-extractor`, `module-contract-lint`, and the brand check on what's lifted.
- `contact` as the pattern for a public form, the Inbox's list and tabs, and the Settings section; `blog` for the editor and its crossed saves.
- The email's frame: one column at 600px, inline styles, the site's colours written as values at render time (an email can't read CSS variables), and dark mode left to the mail app. It's built with the `email-template-system` skill and checked in the main mail apps' widths.

## 6. Non-goals

- **Opens, clicks, link rewriting and tracking pixels.** The board draws none, and they need a consent the site doesn't ask for.
- **Segments, tags, A/B subjects, holdouts, CSV import, seed inboxes, sign-off and replies.** These are VybeSite's, and later if asked.
- **A separate sender:** the From is the site's `MAIL_FROM`. A Reply-To and a sending address of its own come later.
- **Players in an email.** A lone YouTube or Spotify link stays a link. A "Watch on YouTube" card through `embeds.public` comes once campaigns may list `embeds` in `requires.modules`.
- **The account sign-up's "Send me news and releases" box.** It needs the kernel's sign-up to carry it: a kernel PR of its own, after this one.
- **Release announcements made by `discography`** when a release goes out (step 2). The kind is here, written by hand until then.

## 7. Acceptance

**Contract tests:**
- Every route's access, and 404 while the module is off.
- Subscribe answers the same 202 for a new, a pending, a subscribed and a set-aside address. Only new and pending ones get a confirmation, and a set-aside one never does.
- Confirm and unsubscribe work by token. GET changes nothing; POST is done once, and a second POST answers the same. The one-click body is taken.
- A send's audience is the subscribed addresses not set aside. A job run twice sends nobody twice. Each message carries the address's own unsubscribe link and both RFC 8058 headers.
- An address set aside or unsubscribed mid-send is skipped. A scheduled email starts at its time, and cancel stops it. A test goes only to the person asking.
- No postal address is 409 before anything is queued.
- A webhook with a bad or missing signature is refused, and a replay too. A permanent bounce and a complaint set the address aside; a soft bounce doesn't.
- The bounce reader, against a fake mailbox: each of the classifier's cases from real bounce and spam reports, a message read once, nothing done without its variables, and a mailbox that can't be reached leaving the rest of the job's work alone.

**Events:**
- `contact.news.requested` makes a pending subscriber and its confirmation, once.
- `blog.post.published` with `email_subscribers` sends the post's email once; without it, nothing.

**The rest:**
- The prune keeps 30 days of pending subscribers.
- The migration's round trip, the seed twice the same, export and erase by address and by account, and both attention items.
- **Web:** the Newsletter page (each tab, the cards, the attention card, empty tabs), the editor (draft, test, schedule, sent), `NewsletterSignup` (open, sent, closed, field error), and the confirm and unsubscribe pages, in both themes and axe clean.
- `validate_schemas`, `module-contract-lint` and the brand check pass. `mechframe add campaigns`, then `mechframe check`, passes on a new site.

## 8. The owner's answers

Answered 2026-11-22:

1. **The sending service:** the site's own mailer, by SMTP, with Resend only where the host blocks SMTP (the owner: "I don't want to use resend unless SMTP isn't an option"), as decision 0033 has it for all the site's mail. It's not a separate newsletter account.
2. **Confirming a sign-up:** a confirmation email first (double opt-in) for the newsletter form and the contact box, with "Check your inbox" after the form. A person isn't mailed until they click it. (Agreed, as recommended.)
3. **"Email it to subscribers" on a post:** the post's email (its title, summary and link) goes out as soon as the post goes live. (Agreed.)
4. **Who may send to the list:** owner and admin, for both permissions. (Agreed.)
5. **How bounces reach the site by SMTP:** the module reads the bounce mailbox over IMAP, in this PR. The site sends by Spaceship's Spacemail, a mailbox host, so its bounces come back as bounce reports to the sending mailbox (the owner, 2026-11-22). The reader is on once the owner puts the mailbox's login in the host's variables (`CAMPAIGNS_BOUNCE_IMAP_HOST`, `_USERNAME`, `_PASSWORD`). Until then, Set aside holds unsubscribes and addresses set aside by hand, and the Newsletter page says bounces aren't being read. A site that has to send by Resend uses its webhook instead.
6. **The send pace:** Spacemail has no sending limit (the owner, 2026-11-22), so `send_per_hour` defaults to 6,000, 100 a minute. **Changed 2026-11-23:** Spaceship documents 500 an hour for a paid mailbox (20 on a trial), so the owner chose 400. It stays a setting for a host that has a limit.

For later, not a choice:

- The newsletter's postal address (a P.O. box works) goes in Settings → Newsletter before the first send. It's an item for the content intake.

## Changes after approval

- 2026-11-23, in the build (side lane M6):
  - **The token is kept twice:** `token_hash` to look a link up by, and `token_sealed` (`crypto.seal`) so each newsletter can carry the person's own unsubscribe link. A hash alone can't be turned back into the link a send needs.
  - **`GET /signup` `{open}`** is added, public: `useNewsletterOn()` reads whether Settings has sign-ups open.
  - **The text part is the Markdown as written,** its site links made absolute (VybeSite's choice). `kernel.markdown.plain` runs every block onto one line and drops each link's address, which a text part needs.
  - **The email's colours are campaigns' own neutral palette**, written as values. The backend doesn't know the site's theme: a theme-aware frame waits for the kernel to give the backend the theme's values.
  - **A post's email holds its title and link, and its summary once blog's payload carries one.** `blog.post.published` v1 has no summary, and campaigns may not read blog's tables. Without the postal address or a subscriber, the post's email waits as a draft for someone to send.
  - **Only the newsletter's own addresses are set aside** by a bounce or a complaint: one about a sign-in link or a notice is left alone.
  - **The mailbox's folder is a fourth, optional variable,** `CAMPAIGNS_BOUNCE_IMAP_FOLDER` ("Newsletter bounces" by default), for a server that wants folders under the inbox. Resend's secret is `CAMPAIGNS_RESEND_WEBHOOK_SECRET`.
  - **A pending address asked again within 10 minutes gets no second confirmation,** so a form can't flood someone's inbox; a sign-up the bot check holds is kept pending and sent nothing.
  - **A replayed webhook is 409 `campaigns.replayed`;** a bad or missing signature, or no secret, is 401 `campaigns.bad_signature`.
  - **Cancel while sending** stops the rest and leaves the email `sent` to those it reached.
  - **A send's rows go 30 days after they're queued** (the daily prune), and erasing a person takes their address out of every send's rows; the email keeps its count.
  - **The answers' schema names are the module's own** (`CampaignEmail`, `CampaignEmailChange` and the rest): a bare `EmailChange` renamed the kernel's in its committed OpenAPI.
  - **The harness's `/api/_test/mail?full=1`** answers each message's HTML and headers too, so the contract suite checks RFC 8058's pair over HTTP alone.
  - **NewsletterSignup's states are checked in the web tests,** not a browser: no harness page draws it.
- 2026-11-23, Codex on #134:
  - **A sign-up joins the signed-in person's account only for their own verified address,** so their export never holds someone else's subscription.
  - **One send run at a time** (a transaction's advisory lock): Send now's run and the minute's can't each spend the same allowance. A run that finds it held leaves the work to the other.
  - **An email too long once rendered is 422 `campaigns.too_long`** at Send and at a scheduled email's save, under the mailer's 256 KiB a part. One that gets past it anyway (a footer changed since) stops, so it never holds the sends behind it.
- 2026-11-23, CodeRabbit on #134:
  - **A report from the bounce mailbox sets an address aside only when it returns that address's own copy:** the unsubscribe token in the returned message's List-Unsubscribe (or a link in its body). Anyone can mail the mailbox, so a forged report sets nobody aside. Resend's webhook is signed, and its word stands only for an address queued a newsletter copy with the subject its event names, since its events carry the subject and not the headers: a bounce of a sign-in link or a notice to a subscriber sets nobody aside.
  - **A Resend bounce with no status code is unclear:** General can be a policy block, and NoEmail says only that the address couldn't be read back. Every doubt sets nobody aside.
  - **The hour holds:** a run queues no more than `send_per_hour` less what went in the last hour, so a setting under 60 isn't raised to one a minute.
  - **Tokens are resealed with the newest key each night** (the prune), so the key before can leave a night after a new one goes in front. A pending sign-up whose token no key opens gets a new one when it asks again, after the usual ten minutes.
  - **The bounce path holds the subscriber's row before it sets them aside,** as the send run does, so neither overtakes the other.
  - **A token no key opens skips that copy alone;** a report the reader can't parse moves to the read folder anyway; the reader's limit counts only bounce and spam reports.
  - **The webhook refuses malformed headers with 401,** never a 500: a timestamp of a few ASCII digits, signatures compared as bytes.
  - **NewsletterSignup's done state says "if"**: an address already on the list gets the same answer and no second confirmation.
  - **An erase keeps a send's queued rows, the address replaced,** so the hour still counts them; the person's unsent rows go.
  - **A run stamps its copies as it ends,** so one that took longer than a minute still counts them in the minute they leave in.
  - **Subjects and preview lines refuse what the kernel mailer refuses** (Unicode's Cc, Zl and Zp, C1 controls among them). A copy the mailer refuses anyway stops its email, never the sends behind it; a test it refuses is 422 `campaigns.unsendable`.
  - **A run takes each sending email before its rows, as Cancel does, and holds each recipient's row while their copy is decided:** an email Cancel holds is left to it, an unsubscribe under way waits for the run, and a recipient held elsewhere waits, kept, for the next run.
  - **One route serves the editor, `/admin/campaigns/:id`, `new` among them:** a new email's editor stays drawn as its address changes on the first save, so a Send after it, and what it's refused, end in that editor. Editing a field puts away only that field's error.
  - **The send pace defaults to 400 an hour** (the owner, 2026-11-23): Spaceship's knowledge base and terms give a paid Spacemail mailbox 500 an hour (20 on a trial) across its aliases, where §8 6 had none; 400 leaves room for the site's own mail through the same mailbox.
