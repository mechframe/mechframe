---
feature: The blog module, posts with their editor, categories, covers and AI writing help (Vibrant Mindz step 1; M4's second job)
status: approved for the first PR, the blog itself (the owner's go-ahead, 2026-11-22); §8's 6 and 7 still to ask, before the AI PR and social posting
plan: `docs/plans/vibrant-mindz-backend/extraction/blog.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M4); the canvas's AdminBlog and AdminPost boards (`C:\DEV\VM Website\design\site\AdminBlog.dc.html`, `AdminPost.dc.html`) and the site's Blog and Post boards (`Blog.dc.html`, `Post.dc.html`)
approved: 2026-11-22 for the first PR ("blog's first PR, the blog itself, to its contract"); answered the same day: the order of PRs, where AI help lives, what a cover is, two extras, and who writes (§8)
pr: four, after `pages`: the blog (#123, with decision 0057), then the kernel's AI writing help (decision 0058), then generated covers, then social posting (§8)
---

# Contract: `blog`

## 1. Goal

News, poems and rap battle write-ups for Vibrant Mindz, written in the kernel's Markdown editor (decision 0055), filed under categories, given a cover from the media library, drafted, scheduled and published, and read at `/blog` and `/blog/<slug>`. The owner wants the whole blog system from the start: the editor, AI-assisted writing and generated covers (2026-11-21). Lifted from VybeSite (`routers/blog_admin.py`, `blog_public.py`, `models/blog.py`, `services/blog_service.py`, `post_checks.py`, `related_posts.py`; the AI side `routers/ai.py`, `services/anthropic_service.py`, `writing_constitution.py`, `writing_styles.py`), reshaped to the kernel's hooks.

## 2. Interfaces

**Permissions:** `blog.post.write` (owner, admin, editor) to write, save and preview; `blog.post.publish` (owner, admin, editor) to publish, schedule, unpublish and delete. Granted in `blog_0001`.

**HTTP** (`/api/blog`, behind `require_module("blog")`; codes `blog.*`): public `GET /posts?category=&cursor=` (live, newest first, a page of 12) and `GET /posts/{slug}` (`{title, slug, html, summary, cover, category, author, published_at, updated_at}`, or `{moved}` for an old slug); admin `GET /admin/posts?q=&status=` (the board's All, Live, Scheduled, Drafts), `POST /admin/posts`, `GET` and `PATCH /admin/posts/{id}` (`version`, 409 `blog.changed`), `POST /admin/preview`, `POST /admin/posts/{id}/publish` `{at?}`, `/unpublish`, `DELETE`. A live post's Save changes it at once, as a page's (pages §8, 3).

**Categories** are the kernel's taxonomy (hook 2): the vocabulary `blog.category`, one term a post, seeded News, Poetry and Rap battles, edited in the board's Categories card through the kernel's term routes.

**Covers** through `media` (`requires: media`): `public.ts`'s `ImagePicker` and `Picture`; `public.py`'s `use` and `release` record the post as the image's use.

**Public pages:** `routes.public` `["/blog", "/blog/:slug"]`; `server_copy.py` answers each with `BlogPosting` JSON-LD, the cover as `og:image`, a moved slug as a 301; the sitemap and `llms.txt` list live posts.

**Admin pages** (`nav.admin` under Content): `/admin/blog` (the board: the scheduled-without-a-cover card, Search posts, the four filters, the table, Categories) and `/admin/blog/:id` (the AdminPost board: the editor, Publish, Details with Category, Author, Address, Summary and Cover, Search and sharing, After publishing).

**After publishing** (the board's three switches): Allow comments is stored for `comments` (step 3); Post it in Community and Email it to subscribers emit `blog.post.published` with the post's choices, for `community` (step 4) and `campaigns` (M5) to act on. Until those modules are on, the switches say what they wait for.

**Related posts** (the owner wants them now; VybeSite's `related_posts.py`): up to three live posts a writer picks, in order, under a post's body; `blog_post_related` (`post_id`, `related_id`, `position`, each `ON DELETE CASCADE`, not itself); a related post unpublished later is shown nowhere and dropped at the post's next save.

**Hooks:** lifecycle (`blog.post`), taxonomy (`blog.category`), search (`blog.post`), seed (one post a category, one scheduled, one draft), export and erase (a person's posts listed; erase keeps the posts as the site's and clears the author), dashboard (`ATTENTION`: a scheduled post with no cover).

## 3. Data

`blog_post`: `id`, `version`, `title` (≤ 200), `slug` unique (CHECK, ≤ 80), `summary` (≤ 300), `body` Markdown (≤ 100,000), `cover_id` (media's image id, no foreign key across modules), `author_id` → `auth_user` `ON DELETE SET NULL`, `search_title`, `search_description`, `allow_comments`, `post_to_community`, `email_subscribers`, the lifecycle's columns, `created_at`, `updated_at`. `blog_slug_move` (VybeSite has none; pages' moves, for a changed slug). Branch `blog`, `blog_0001`, `depends_on` `kernel_0013` (taxonomy).

## 4. Files

`modules/blog/` as `media` lays out, `requires` `media ^0.1`. The AI part's files depend on §8, 2.

## 5. Conventions this follows

SPEC 4 to 11 and 16; the extractor and `module-contract-lint`; the kit; the hooks as `hooks.md` defines them; pages' contract for the editor, the live save and moves.

## 6. Non-goals

- Comments, reactions, community posts and newsletter sends themselves: their modules (steps 3 and 4, M5).
- The claims list checks from VybeSite (the owner, 2026-11-22: later).
- Embeds in a post's body: `embeds` (M5) adds the editor's Embed button and the players.
- Several categories a post, tags, series.

## 7. Acceptance

- Contract tests for every route's access, a stale `version` 409, a scheduled post going live, a moved slug's 301, a draft's 404; the server copy's `BlogPosting`; categories through the kernel's taxonomy; a cover's use recorded and released.
- Migration round trip; the seed twice the same; export and erase; the attention item.
- Web: both admin boards and the Blog and Post pages in both themes, axe clean.
- `validate_schemas`, `module-contract-lint`, the brand check, `mechframe add blog` then `mechframe check`.

## 8. The owner's answers, and what's still to ask

Answered 2026-11-22:

1. **The order of PRs:** three, as recommended (the blog, then AI writing help, then generated covers), all before step 1 is called done; social posting (5) makes a fourth.
2. **Where AI writing help lives:** the kernel, as recommended: `ai.client()` (SPEC 6), Settings → Writing (VybeSite's writing constitution and writing styles), and the editor's AI buttons for every module's `MarkdownEditor` (draft, titles, summary, search words, rewrite), through its `tools`. A decision record with that PR.
3. **What a generated cover is:** VybeSite's, as recommended: Claude draws an SVG cover from the post (the brand's colours, a wordmark if ticked), cleaned, then made a PNG on the server and stored in the media library as any image, with alt text.
4. **VybeSite's extras now:** related posts and social posting; the claims list checks later.
5. **Who writes** (answered 2026-11-22, as recommended): "Anyone with blog writing permissions should be able to write and publish." `blog.post.write` and `blog.post.publish` both go to owner, admin and editor, the Author field naming any of them; a site that wants authors who can't publish adds a custom role with only `blog.post.write`.
6. **The Anthropic key** (answered 2026-11-22, not as recommended: "Host variable or Settings"): `ANTHROPIC_API_KEY` in the host's variables, typed by the owner, or one an admin saves in Settings → AI, encrypted, as VybeSite does; nothing AI shows without one. The AI PR's contract (`dev plans/contracts/kernel-ai.md`) says which wins when both are there.

7. **Social posting's home and key** (answered 2026-11-24): a `social` module any module can share through (blog first, then releases and products), as recommended. Its Buffer token, not as recommended: "Host or Settings", as the AI's key is: a token saved in Settings, sealed, wins over the host's variable, with a Check. VybeSite posts through Buffer, its key saved in Settings → Company channels. Creating the Buffer account is the owner's. Its own contract comes first, after the footer's shift (the owner, 2026-11-24: the shift goes next, after covers).

## 9. Changes as it was built (#123)

- **The vocabulary's key is `blog_category`,** not `blog.category`: a key is lowercase letters, digits and underscores (hook 2). A writer chooses an existing term; only staff holding `kernel.taxonomy.manage` make them, on the board's Categories card through the kernel's term routes. The seed makes News, Poetry and Rap battles; a site starts with none.
- **Three more routes:** `GET /categories` (public: each category with its live posts, the Blog board's filters), `GET /admin/categories` (each with all its posts, the Categories card) and `GET /admin/authors` (the Author field: every active owner, and everyone whose role holds `blog.post.write`).
- **The answers,** each a typed object (`tests/test_openapi.py`): the lists are `{items, next_cursor}` and take `limit`, the admin's adding `needs_cover`, the soonest scheduled post with no cover, for the board's note. A live post also answers `reading_minutes` (the boards' "n min read"), its search words filled in, `related` and `allow_comments`; `{moved}` is the post's path, `/blog/<slug>`.
- **A slug left out is made from the title,** VybeSite's way (an apostrophe dropped), numbered when another post has it. A live post's slug may change and leaves a move, as a page's does; VybeSite kept a published post's address fixed.
- **Readers see an author's display name only,** never an address: `author` is null when they have none. Staff see the address in its place.
- **`blog.post.published` goes once a post,** the first time it goes live: blog hears the kernel's `kernel.content.published` for its type, so a scheduled post going live counts too, and `announced_at` keeps it to once. Its payload is `{post_id, slug, title, path, post_to_community, email_subscribers}` (v1; v2 adds `summary`, blog 0.1.3), and those two switches can't change once the post has gone live (422 `blog.announced`), so a late delivery says what the writer chose (CodeRabbit on #123). Allow comments, a live setting, isn't in it.
- **The board's Comments column** waits for `comments` (step 3).
- **A module's web reaches another's `public.ts` as `@/modules/<id>/public`** (decision 0057, SPEC 7): blog's is the first, for media's `ImagePicker` and `Picture`. The kernel's AI writing help is decision 0058.
- **From the reviews on #123:** a new post sent with `author_id: null` names no one (Codex); every page of the kernel's terms is read, and a category deleted as a post is saved isn't made again; the downgrade takes the posts' terms, search documents and covers' uses (`depends_on` `kernel_0014` and `media_0001`); and the editor leaves an untyped address to the server, keeps what's typed while a save is on its way, and shows a publish that landed (CodeRabbit).
- **The e2e server runs with storage off,** so its post has no cover: covers are held by the contract suite (media's fake S3) and the web tests.
- **Its public surface** (blog 0.1.1, #128; asked by VM Website Dev 09 through Dev 32, placed before the AI PR by the owner, 2026-11-22): `web/public.ts` gives a site's own Blog and Post pages `usePosts`, `usePost`, `useCategories`, `isMoved`, `pathOf`, `day` and the answers' types, and blog's own pages read through the same hooks (`web/reads.ts`); `blog.public` gives a site's server copy `posts`, `newest`, `post`, `categories` and `path`, each the API's answer as its Pydantic model. The categories' public read is one function, `service.live_categories`, for the route and `blog.public` both.
- **Blog 0.1.3** (#143; the handoff of 2026-11-23, M4h):
  - `blog.post.published` is version 2, adding the post's `summary` ("" when it has none) for campaigns' email, which reads it when it's there. `events.Payload` refuses fields it doesn't declare, so a listener's strict view of v1 would refuse the field: that makes it a new payload version, minor by SPEC 13, not an edit to v1. `python -m tools.event_schemas` writes v2's schema and removes v1's.
  - The editor's three crossed-save gaps pages closed in 0.1.1 (CodeRabbit on #138): a conflict-free retry carries the person's fields into the next check (`save(…, carried)`); so does the save after a conflict's choice, less the fields given to the other person; and both set `formNow.current = next` before they go. Three tests, each seen failing first, hold the retry's carried fields, the choice's carried fields and the retry's `formNow`. The choice's `formNow` line has none that can fail: React draws a click's update before the save's answer comes back, so jsdom never reads the old form there. It's kept as pages has it.
- **Blog 0.1.4, generated covers** (#147, decision 0065; their own contract, `dev plans/contracts/blog-covers.md`, answers §8, 3): Draw a cover in the Cover image block, Claude's SVG cleaned by the kernel's new `kernel.svg` and kept as a 2400 × 1260 PNG in the media library. Its routes are `GET /admin/covers`, `POST /admin/covers/draw` and `POST /admin/covers`.
