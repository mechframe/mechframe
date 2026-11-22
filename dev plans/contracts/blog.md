---
feature: The blog module, posts with their editor, categories, covers and AI writing help (Vibrant Mindz step 1; M4's second job)
status: draft (the owner's answers to four questions in §8; three smaller ones still to ask)
plan: `docs/plans/vibrant-mindz-backend/extraction/blog.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M4); the canvas's AdminBlog and AdminPost boards (`C:\DEV\VM Website\design\site\AdminBlog.dc.html`, `AdminPost.dc.html`) and the site's Blog and Post boards (`Blog.dc.html`, `Post.dc.html`)
approved: not yet; answered 2026-11-22: the order of PRs, where AI help lives, what a cover is, and two extras (§8)
pr: four, after `pages`: the blog, then the kernel's AI writing help, then generated covers, then social posting (§8); numbers predicted at push time
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

Still to ask, each with its recommendation:

5. **The Anthropic key** (before the AI PR): `ANTHROPIC_API_KEY` in the host's variables only, typed by the owner, as every other key here; nothing AI shows without it. VybeSite also lets an admin save one in Settings → AI, encrypted.
6. **Social posting's home and key** (before its PR): VybeSite posts through Buffer, its key saved in Settings → Company channels. Recommended: a `social` module any module can share through (blog first, then releases and products), its Buffer token in the host's variables; the other way is inside blog. Creating the Buffer account is the owner's.
7. **Who writes** (before the blog PR): anyone holding `blog.post.write` (owner, admin, editor), the Author field naming any of them; a site that wants authors who can't publish adds a custom role with only that permission.
