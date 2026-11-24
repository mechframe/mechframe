# Host variables: the guidebook

Every variable a site built with MechFrame reads from its host, and what each module
needs, so a site can go live on Railway or another host without guessing. On Railway
they're the web service's **Variables**; elsewhere, the host's environment variables.
Locally, the site's `.env` holds the kernel's (copy `.env.example`). `.env` feeds only
the kernel's settings: a variable marked **Environment only** (each module's own, and
the server's) is read from the process's environment, so for a local run export it in
the shell before starting the app (`$env:NAME = "value"` in PowerShell). On a host
every variable is in the environment, so there it makes no difference.

> Made by `python -m tools.host_variables` from the kernel's settings
> (`kernel/backend/kernel/config.py`), each module's `module.json` and the site
> template's `.railway/railway.ts`. Don't edit it by hand: change those and run the
> tool. `tests/test_host_variables.py` fails while it's stale, and when the code reads
> a variable this page doesn't list.

**Never commit a value.** Secrets are typed into the host by the site's owner, never
written into `.env.example`, `railway.ts` or chat.

## What "Needed" means

| Needed | Meaning |
| --- | --- |
| Required | The site won't start without it outside `DEBUG`, or can't reach its database. |
| Recommended | It starts without it, but works badly: set it. |
| For mail, For storage, For the AI, For error reports | Needed only for that feature; each group says which go together. |
| Optional | A behaviour with a sensible default. |
| Tuning | A default to change only with a reason. |
| The host gives it | Railway (and most hosts) set it; you don't. |
| Secret | Typed into the host only, never committed or pasted into chat. |
| Environment only | Read from the process's environment, never `.env`: export it for a local run. |

## Putting a site on Railway, step by step

1. **Make the site and add its modules:** `mechframe new <dir> --name "<site name>"`, then
   `mechframe add <id> --site <dir>` for each module. Each `add` lists the module's
   variables in the site's `.env.example` and `.railway/railway.ts`.
2. **Apply Railway as code** from the site's folder: `npm ci`, `railway init --name <project>`
   (or `railway link`), `railway config plan`, then `railway config apply`. This makes the
   `web` service and its `postgres`, and sets every variable marked "Set" or "Railway's
   Postgres" below. A variable on `web` that `railway.ts` doesn't list is deleted by the
   next apply: add new ones to the file first. The site's `README.md` ("Deploying") has
   the rest, Windows included.
3. **Connect `web` to the site's repo** (Settings → Source) and type the three it can't
   start without into its Variables: `SITE_URL`, `SECRET_KEY` and `ENCRYPTION_KEYS`.
4. **Turn on each feature the site uses:** mail, storage, the AI and error reports. Each
   group below says which variables go together; one set in part stops the start and
   names what's missing.
5. **Type each module's own variables** (its section below).
6. **Deploy.** Migrations run before the new deploy takes traffic, and Railway checks
   `/api/kernel/health`. Then make the first owner in the service's shell (`railway ssh`,
   then `python -m app.owner <email>`), and fill each module's admin settings.

## On another host

The same variables, with what Railway did for you done by hand:

- **`DATABASE_URL`:** your Postgres 16+, with a role that owns the site's database.
- **`PORT`:** most hosts give it; otherwise the server listens on 8000.
- **`CLIENT_IP_HEADER` and `FORWARDED_ALLOW_IPS`:** the header your edge writes the
  visitor's address into, and the addresses that edge connects from (`*` only when the
  edge is the only way in).
- **Migrations before traffic:** run `python -m app.migrations upgrade` before each new
  version starts, and stop the deploy if it fails.
- **The health check:** `/api/kernel/health`.

## The kernel's variables

### The site itself

Every site sets these. Outside `DEBUG`, the site refuses to start while `SITE_URL`, `SECRET_KEY` or `ENCRYPTION_KEYS` is missing, short or a placeholder, and says which.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `SITE_URL` | Required | `http://localhost:8000` | You type it | The site's own address, such as `https://www.example.org`: links in mail, the sitemap and the same-origin check use it. Outside `DEBUG` it must be https and not a placeholder or local address. |
| `SECRET_KEY` | Required · Secret | blank | You type it | Signs links in mail and other signed values: at least 43 random characters. Make one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Changing it voids every link already sent. |
| `ENCRYPTION_KEYS` | Required · Secret | blank | You type it | Fernet keys, comma-separated, newest first: stored secrets (provider keys, authenticator secrets, newsletter links) are sealed with the first and opened with any. Make one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. To rotate, put a new key in front and keep the old one behind it: what the old key sealed opens only while it's listed, so removing it makes that unreadable. |
| `DATABASE_URL` | Required · Secret | a local database (development only) | Railway's Postgres | The Postgres 16+ database, as `postgresql://user:password@host:port/name`. On Railway it's a reference to the `postgres` service beside the site. |
| `SITE_NAME` | Recommended | `MechFrame site` | Set by `mechframe new` | The site's name, in titles, mail and the admin. `mechframe new` writes it into `railway.ts`. |
| `DEBUG` | Optional | `false` | Set: `false` | `true` only for local development: it skips the start's safety checks and loosens same-origin rules. Never `true` on a live host. |
| `MODULES` | Optional | `*` | Set: `*` | The modules this deploy may use, comma-separated, or `*` for every module the site has. A name the site doesn't have stops the start, so a typo never leaves a module off silently. The admin can still switch any of them off at runtime. |
| `WEB_DIST` | Optional | blank | Set by the Dockerfile | The built web app's folder, whose `index.html` every public address answers with. The site's Dockerfile sets it (`/app/web/dist`); blank serves the kernel's minimal page with no scripts. |

### Behind the host's edge

How the site sits behind Railway's proxy (or another host's), and what it tells browsers and search engines.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `CLIENT_IP_HEADER` | Recommended | blank | Set: `X-Real-IP` | The one header the host's edge writes the visitor's address into: `X-Real-IP` on Railway, `Fly-Client-IP` on Fly.io, `CF-Connecting-IP` behind Cloudflare. Blank, every visitor counts as the edge's address, so they all share one rate limit (the start warns). Blank for local runs with no proxy. |
| `CORS_ORIGINS` | Optional | blank | Only if you change it | Other sites allowed to call this one's API from a browser, comma-separated. Blank for none, which suits a site whose web app it serves itself. |
| `HSTS_MAX_AGE` | Optional | `0` | Only if you change it | Strict-Transport-Security's max-age, in seconds. `0` sends none. Set `31536000` once the domain is settled and every part of it is on https. |
| `ROBOTS_NOINDEX` | Optional | `false` | Only if you change it | `true` on a copy no search engine should list, such as staging. Never on the live site. |
| `MAX_BODY_BYTES` | Tuning | `1048576` | Only if you change it | The largest request body accepted, in bytes; larger is 413. Uploads go to storage and aren't held to it. At least 1024. |
| `PORT` | The host gives it · Environment only | `8000` | Railway gives it | The port the site listens on. Railway and most hosts give it; the Dockerfile falls back to `8000`. |
| `FORWARDED_ALLOW_IPS` | Recommended · Environment only | `127.0.0.1` | Set: `*` | Whose `X-Forwarded-*` headers the server trusts, for the request's scheme and the visitor's address. `*` on Railway, whose edge has no fixed addresses and is the only way in; the edge's addresses on a host where they're known; `127.0.0.1` locally. |

### Accounts and passwords

Who may make an account, and how hard each password is hashed.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `SIGN_UP_MODE` | Optional | `closed` | Only if you change it | Who may make an account: `open`, `invite` or `closed`. It's only the first value: once the site is up, Admin → Settings holds it. One of `open`, `invite` or `closed`. |
| `ARGON2_MEMORY_KIB` | Tuning | `65536` | Only if you change it | The memory each password hash uses, in KiB; never below OWASP's 19 MiB. Raise it where the host has memory to spare. At least 19456. |
| `ARGON2_TIME_COST` | Tuning | `3` | Only if you change it | Passes over that memory for each hash. At least 2. |
| `ARGON2_LANES` | Tuning | `4` | Only if you change it | Lanes (parallelism) in each hash. At least 1. |
| `ARGON2_CONCURRENCY` | Tuning | `4` | Only if you change it | How many hashes run at once; each holds `ARGON2_MEMORY_KIB` while it runs. At least 1. |

### Mail

Nothing set sends nothing (sign-in links and notices are only logged). Set in part, the site refuses to start. SMTP comes first: with `SMTP_HOST` set, mail goes through any provider's SMTP. Only on a host that blocks outbound SMTP, such as Railway's Hobby plan, leave `SMTP_HOST` blank and set `RESEND_API_KEY`.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `MAIL_FROM` | For mail | blank | You type it | The one bare address every mail comes from, such as `hello@example.org`: no name or angle brackets. Required once SMTP or Resend is set. |
| `MAIL_FROM_NAME` | Optional | blank | Only if you change it | The name shown beside `MAIL_FROM`; `SITE_NAME` while blank. |
| `SMTP_HOST` | For mail | blank | You type it | The mail provider's SMTP server. Setting it chooses SMTP. |
| `SMTP_PORT` | For mail | `587` | You type it | `465` for implicit TLS, `587` (or any other) for STARTTLS. 1 to 65535. |
| `SMTP_USERNAME` | For mail | blank | You type it | The SMTP login, usually the sending mailbox. Set with `SMTP_PASSWORD` or neither. |
| `SMTP_PASSWORD` | For mail · Secret | blank | You type it | The SMTP login's password. |
| `RESEND_API_KEY` | For mail · Secret | blank | You type it | Resend's API key, only on a host that blocks outbound SMTP, with `SMTP_HOST` blank. With both set, SMTP wins. |

### Storage

An S3-compatible store, Cloudflare R2 on a live site. All blank: storage is off, and media's uploads answer 503. Set in part, the site refuses to start: the four private ones go together, and the public pair together.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `STORAGE_ENDPOINT_URL` | For storage | blank | You type it | The store's endpoint: on R2, `https://<account>.r2.cloudflarestorage.com` (a bucket pasted onto it is dropped). |
| `STORAGE_ACCESS_KEY_ID` | For storage | blank | You type it | The access key's ID (R2: an API token's S3 access key ID). |
| `STORAGE_SECRET_ACCESS_KEY` | For storage · Secret | blank | You type it | The access key's secret. |
| `STORAGE_BUCKET` | For storage | blank | You type it | The private bucket: its files are reached only through signed links. |
| `STORAGE_PUBLIC_BUCKET` | For storage | blank | You type it | The public bucket, served to anyone at `STORAGE_PUBLIC_URL`: media's images and discography's stream files live here. Never the same bucket as `STORAGE_BUCKET`. Set with `STORAGE_PUBLIC_URL` or neither. |
| `STORAGE_PUBLIC_URL` | For storage | blank | You type it | The public bucket's address (R2: its custom domain), https outside `DEBUG`. While it's set, the pages' `media-src` allows it, so a stream file plays (decision 0070). |
| `STORAGE_REGION` | Tuning | `auto` | Only if you change it | The store's region; R2 takes `auto`. |
| `STORAGE_MAX_BYTES` | Tuning | `2147483648` | Only if you change it | The largest file the kernel stores, in bytes. At least 1. |

### Background jobs

The jobs worker sends mail, publishes what's scheduled and runs each module's jobs. By default it runs inside the web process: one service.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `JOBS_IN_WEB` | Optional | `true` | Set: `true` | `true` runs the worker inside the web process. A site that runs its own worker service (`python -m app.worker`, for heavy jobs) sets `false` on the web service. |
| `JOBS_CONCURRENCY` | Tuning | `4` | Only if you change it | How many jobs one worker runs at once. 1 to 32. |
| `JOBS_POLL_SECONDS` | Tuning | `1.0` | Only if you change it | How often a worker looks for due jobs. 0.1 to 60. |
| `JOBS_DRAIN_SECONDS` | Tuning | `20.0` | Only if you change it | On a redeploy, how long running jobs get to finish before they're left to their leases and run again later. 0 to 600. |

### The AI's writing help

Write with AI in every editor. A key an admin saves in Settings → AI wins over the host's; with neither, no AI shows.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | For the AI · Secret | blank | You type it | The Anthropic API key Write with AI uses, from the Anthropic console. Blank keeps the AI off until an admin saves a key in Settings → AI, which wins over this one. |
| `ANTHROPIC_MODEL` | Optional | `claude-opus-5-5` | Only if you change it | The model every writing task asks for, until an admin saves one in Settings → AI. |
| `AI_RATE_LIMIT` | Optional | `20/1h` | Only if you change it | The AI calls one person may make, every button sharing it: a count, then a period (`s`, `m`, `h` or `d`). |

### Search, consent and the audit log

How site search reads words, what waits for a visitor's consent, and how long the audit log keeps its entries.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `SEARCH_LANGUAGE` | Optional | `english` | Only if you change it | The language site search reads words in (`simple` stems nothing). After changing it, run the job `kernel.search_reindex` once. One of 29 values, such as `arabic`, `armenian`, `basque`, `catalan` or `danish`. |
| `CONSENT_MODE` | Optional | `ask` | Only if you change it | `ask` holds a script or player a module puts in a category other than `necessary` (analytics, marketing, media) until the visitor allows it; `off` loads everything at once, for a site with nothing to ask. One of `ask` or `off`. |
| `AUDIT_KEEP_DAYS` | Optional | `365` | Only if you change it | Days an audit-log entry is kept before the nightly prune removes it. At least 30. |

### Rate limits

Every form and sign-in is rate-limited per visitor, by the address `CLIENT_IP_HEADER` names.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `RATE_LIMIT_ENABLED` | Tuning | `true` | Only if you change it | `false` turns every rate limit off: for tests, never a live site. |
| `RATE_LIMIT_STORAGE` | Tuning | `memory://` | Only if you change it | Where the counts live: `memory://` for one process; a `redis://` address once the site runs more than one. |

### Errors and logs

Error reports go to Sentry once `SENTRY_DSN` is set; logs go to the host's log view.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `SENTRY_DSN` | For error reports | blank | You type it | Sentry's DSN for the project that collects this site's errors. Blank sends none. |
| `SENTRY_ENVIRONMENT` | Optional | blank | Only if you change it | The environment Sentry files errors under; `production` while blank. |
| `LOG_FORMAT` | Optional | `json` | Set: `json` | `json` for the host's log view, `text` for reading locally. One of `json` or `text`. |
| `LOG_LEVEL` | Optional | `INFO` | Only if you change it | The least severe level logged. One of `DEBUG`, `INFO`, `WARNING` or `ERROR`. |
| `RAILWAY_GIT_COMMIT_SHA` | The host gives it · Environment only | none | Railway gives it | The deployed commit, which Railway gives each deploy: Sentry files errors under it as the release. |

### Database and process tuning

The kernel's defaults suit a small site on one service. Change these only with a reason.

| Variable | Needed | Default | On Railway | What it's for |
| --- | --- | --- | --- | --- |
| `DB_POOL_SIZE` | Tuning | `5` | Only if you change it | Database connections each process keeps open. At least 1. |
| `DB_MAX_OVERFLOW` | Tuning | `10` | Only if you change it | Extra connections a busy process may open beyond the pool. |
| `MODULES_CACHE_SECONDS` | Tuning | `5.0` | Only if you change it | How long each process trusts the list of modules switched off in the admin; `0` reads it on every request. 0 to 60. |

## The modules' variables

Each module's own host variables, from its `module.json`, and the settings its admin page holds. A planned module's are as its scaffold has them so far; they grow as it's built.

### `blog` 0.1.3 (experimental)

Dated posts in Markdown, with categories, a cover from the media library, scheduling and related posts.

No host variables of its own.

**From the kernel:** Covers come from media, so storage too; Write with AI needs `ANTHROPIC_API_KEY` or a key saved in Settings → AI.

### `campaigns` 0.1.0 (experimental)

The site's newsletter: sign-ups confirmed by email, emails sent with one-click unsubscribe, bounces set aside.

| Variable | Needed | On Railway | What it's for |
| --- | --- | --- | --- |
| `CAMPAIGNS_BOUNCE_IMAP_HOST` | Optional · Environment only | You type it (`mechframe add` lists it) | The bounce mailbox's IMAP host, such as mail.example.com or mail.example.com:993; with the next two, bounces are read every 15 minutes |
| `CAMPAIGNS_BOUNCE_IMAP_USERNAME` | Optional · Environment only | You type it (`mechframe add` lists it) | The bounce mailbox's login: on Spacemail and most mailbox hosts, the sending mailbox itself |
| `CAMPAIGNS_BOUNCE_IMAP_PASSWORD` | Optional · Secret · Environment only | You type it (`mechframe add` lists it) | The bounce mailbox's password, typed into the host's variables by the owner |
| `CAMPAIGNS_BOUNCE_IMAP_FOLDER` | Optional · Environment only | You type it (`mechframe add` lists it) | The folder a read report moves to; Newsletter bounces by default |
| `CAMPAIGNS_RESEND_WEBHOOK_SECRET` | Optional · Secret · Environment only | You type it (`mechframe add` lists it) | Only for a site that sends by Resend: the webhook's signing secret (whsec_...), for its bounces and complaints |

**From the kernel:** Every confirmation and newsletter goes by the kernel's mail (`MAIL_FROM` with `SMTP_HOST` or `RESEND_API_KEY`). Nothing sends until its postal address is set in Settings → Newsletter.

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `signups_open` | bool | `true` | Whether the newsletter takes sign-ups; while it's off, the forms say sign-ups are closed |
| `postal_address` | string | blank | The postal address every newsletter carries (US law; a P.O. box will do). Nothing sends until it's set |
| `footer_note` | string | `You're getting this because you asked for news from ${site_name}.` | The footer's first line; ${site_name} is the site's name |
| `send_per_hour` | int | `400` | How many newsletter copies may go out in an hour, 1 to 10,000: a sixtieth each minute. 400 by default, under a Spacemail mailbox's 500 with room for the site's own mail |

### `contact` 0.1.1 (experimental)

The site's contact form, and an Inbox where its people read each message, reply from their own email and set spam aside.

No host variables of its own.

**From the kernel:** Its notices to the Inbox's readers go by mail too, so mail (`MAIL_FROM` with `SMTP_HOST` or `RESEND_API_KEY`).

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `intro` | string | `Send a message and we'll reply by email.` | The line under the Contact page's heading |
| `topics` | json | a list (see the module's MODULE.md) | What a message can be about, in the form's order; a first topic's new messages come first in the Inbox |

### `discography` 0.1.0 (experimental)

Albums, EPs and singles with tracks, credits and streaming links; tracks play from an upload or a SoundCloud link.

No host variables of its own.

**From the kernel:** Uploads need the site's storage (`STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY` and `STORAGE_BUCKET`, where masters go): until it's set, an upload answers 503 `discography.storage_off` and tracks play from SoundCloud links. Stream files go in `STORAGE_PUBLIC_BUCKET` at `STORAGE_PUBLIC_URL`: without that pair, a stream file can't be made and the track fails once its tries are used. Its job runs where the jobs worker does (`JOBS_IN_WEB`).

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `stream_bitrate_kbps` | int | `256` | The stream file's constant bitrate, from 128 to 320 |
| `show_explicit_badge` | bool | `true` | The Parental Advisory label on explicit releases and tracks |
| `show_lyrics` | bool | `true` | Lyrics on a track's page, for tracks that have them |

### `embeds` 0.1.0 (experimental)

YouTube, SoundCloud, Spotify and Bandcamp players from a pasted link, loaded only once a visitor plays.

No host variables of its own.

### `media` 0.1.3 (experimental)

Images uploaded once with alt text, cleaned of metadata, and placed by any module.

No host variables of its own.

**From the kernel:** Uploads need storage with its public pair, `STORAGE_PUBLIC_BUCKET` and `STORAGE_PUBLIC_URL`; until they're set, uploads answer 503 `media.storage_off`.

### `pages` 0.1.1 (experimental)

The site's fixed pages, About to Privacy, written in Markdown and placed in the header's and footer's menus.

No host variables of its own.

**From the kernel:** Write with AI needs `ANTHROPIC_API_KEY` or a key saved in Settings → AI.

### `audio-player` 0.1.0 (planned, not built yet)

One site-wide player with waveforms and a queue, where only one thing plays at a time across every player.

No host variables of its own.

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `autoplay_next` | bool | `true` | Move to the next item in a queue when one ends |
| `count_after_seconds` | int | `30` | Seconds of listening before a play counts |

### `comments` 0.1.0 (planned, not built yet)

Threaded discussions under any module's content, with reactions, mentions and approval for guests.

No host variables of its own.

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `guest_comments` | bool | `true` | Guests may comment; every guest comment waits for approval (owner answer Q4) |
| `edit_window_minutes` | int | `15` | Minutes a comment stays editable |
| `max_links` | int | `2` | Links allowed in one comment |

### `featured` 0.1.0 (planned, not built yet)

Named slots of ordered, schedulable placements, such as a homepage spotlight or featured products.

No host variables of its own.

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `oembed_titles` | bool | `true` | Fill a pasted YouTube link's title from YouTube's oEmbed |

### `licensing` 0.1.0 (planned, not built yet)

Sells usage rights to digital files, such as beat leases, with tiers, agreements and license checks.

No host variables of its own.

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `free_download_for_email` | bool | `false` | Offer a tagged free download in exchange for an email |
| `credit_line` | string | `prod. by Vibrant Mindz` | Credit printed on every agreement |

### `portfolio` 0.1.0 (planned, not built yet)

Artwork, design, animation and video pieces grouped by discipline, each optionally linked to a shop listing.

No host variables of its own.

Set in the site's admin (Admin → Settings), not on the host:

| Setting | Type | Default | What it's for |
| --- | --- | --- | --- |
| `pieces_per_page` | int | `24` | Pieces on each list page |

### `roster` 0.1.0 (planned, not built yet)

A profile per member of a collective, band or team, gathering their work from other modules.

No host variables of its own.

## Never on a live host

Read only by tests, local runs and the CLI. None of these belong in a live host's variables, `.env.example` or `railway.ts`, and `DEBUG` stays `false` there.

| Variable | What it's for |
| --- | --- |
| `MECHFRAME_ALLOW_SEED` | `1` for one run allows seeding demo rows (`mechframe seed`). Never in `.env`, `railway.ts` or a live host's variables. |
| `TEST_DATABASE_URL` | A Postgres role with CREATEDB that the test suites make throwaway databases with. |
| `HARNESS_TEST_SUPPORT` | `1` mounts the harness's test-only routes (its mail box and clock). Only the test runs set it. |
| `E2E_PORT` | The port the end-to-end tests' server uses. |
| `E2E_PYTHON` | The Python the end-to-end tests start it with. |
| `CI` | Set by CI: Playwright refuses a `test.only` there. |

## Every secret, in one list

Typed into the host by the site's owner, and rotated by typing a new value; for `ENCRYPTION_KEYS`, the new key goes in front and the old one stays behind it.

`ANTHROPIC_API_KEY`, `CAMPAIGNS_BOUNCE_IMAP_PASSWORD`, `CAMPAIGNS_RESEND_WEBHOOK_SECRET`, `DATABASE_URL`, `ENCRYPTION_KEYS`, `RESEND_API_KEY`, `SECRET_KEY`, `SMTP_PASSWORD`, `STORAGE_SECRET_ACCESS_KEY`.
