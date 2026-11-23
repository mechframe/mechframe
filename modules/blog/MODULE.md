# blog

Dated posts: news, stories, poems, write-ups. The contract is `dev plans/contracts/blog.md`.

## What it does

A writer drafts a post in Markdown: a title, an address under `/blog`, a one-line summary for its card, a category, an author, a cover from the media library, up to three related posts and its words for search results and sharing. It stays a draft until it's published, now or at a time to come, and a live post's save changes the site at once: there's no working copy. A post left without an address takes one from its title (`Don't stop` is `/blog/dont-stop`, numbered when another post has it). A live post given a new address leaves the old one sending visitors to it (a 301), and a post moved twice sends both old addresses to where it is now, never along a chain. The address a post holds is its own, live or not: a post that takes an address ends any move there.

A post sits in one category, a term of the kernel's `blog_category` (hook 2): a writer chooses among them, and staff holding `kernel.taxonomy.manage` add, rename and delete them on the board's Categories card. Its cover is the media library's image: placing it records the post as the image's use, so the library won't delete it while it's placed, and choosing another lets the old one go. Its related posts are live posts in the order the writer chose; one unpublished later is shown nowhere and dropped at the post's next save. Readers see the author's display name, never an address.

The body is made HTML on the server (`kernel.markdown.render`) on every read and drawn with the kit's `Prose`; the server's copy says the same words to crawlers that run no JavaScript, with the cover as `og:image` and a `BlogPosting` JSON-LD.

The After publishing switches are stored for the modules that act on them: Allow comments for `comments`, and Post it in Community and Email it to subscribers sent with `blog.post.published` for `community` and `campaigns`. That event goes out once a post, the first time it goes live, whether at once or on its schedule. Those two switches are fixed from then on, so the event says what the writer chose (a save that changes one answers 422 `blog.announced`); Allow comments can change any time.

## Use when / avoid when

Use it for dated writing with an author, a category and a cover, drafted and scheduled ahead, whose address may change while old links keep working. Avoid it for fixed pages like About: that's `pages`. Avoid it for threads people start and answer: that's `community`. Avoid it for writing that's mailed rather than read on the site: that's `campaigns`.

## What it adds

- **Routes**, under `/api/blog`:
  - `GET /posts?category=&cursor=` (public): `{items, next_cursor}`, the live posts newest first, 12 a page, each its card (title, slug, summary, cover, category, author, `published_at`, `reading_minutes`);
  - `GET /posts/{slug}` (public): the live post, its card with `html`, `updated_at`, the search words filled in from the title and the summary when left empty, `related` and `allow_comments`; `{moved}` for an address a live post left; 404 `blog.post_not_found` otherwise;
  - `GET /categories` (public): `{items}`, each category with its live posts;
  - `GET /admin/posts?q=&status=&cursor=` (`{items, next_cursor, needs_cover}`, 50 a page, newest edit first), `POST /admin/posts` (409 `blog.slug_taken`), `GET` and `PATCH /admin/posts/{id}` (with `version`; 409 `blog.changed` with the post as it is now), `POST /admin/preview`, `GET /admin/categories` and `GET /admin/authors`: `blog.post.write`;
  - `POST /admin/posts/{id}/publish` (`{at?}`, a time with its zone to schedule it), `POST /admin/posts/{id}/unpublish`, `DELETE /admin/posts/{id}`: `blog.post.publish`;
  - 422 `blog.category_not_found`, `blog.cover_not_found`, `blog.author_not_allowed`, `blog.related_refused` and `blog.announced` for a field that can't be kept.
- **Public pages:** `/blog`, the latest post first and larger, the rest as cards, filtered by category; `/blog/:slug`, the post. The server copy answers both, and lists every live post in the sitemap and `llms.txt`.
- **Menus:** Blog in `nav.public`.
- **The admin pages:** `/admin/blog`, the board (the note for a scheduled post with no cover, Search posts, All, Live, Scheduled and Drafts, the table, Categories), and `/admin/blog/:id` (`new` for a new post), the editor: Title, the kit's `MarkdownEditor`, Publish, Details (Category, Author, Address, Summary, Cover image through media's `ImagePicker`), Related posts, Search and sharing (`SearchFields`) and After publishing. Under Content in the sidebar.
- **Tables:** `blog_post`, `blog_slug_move` and `blog_post_related` (migration `blog_0001`, after the kernel's `kernel_0014` and media's `media_0001`; its downgrade takes the posts' terms, search documents and covers' uses with it).
- **Permissions:**
  - `blog.post.write` (list, write, save, preview) and `blog.post.publish` (publish, schedule, unpublish, delete);
  - both go to admin and editor, granted in the migration; an owner holds every permission. A site that wants writers who can't publish gives a role of its own `blog.post.write` alone.
- **Events:** emits `blog.post.published` (`{post_id, slug, title, path, post_to_community, email_subscribers}`), heard from the kernel's `kernel.content.published`.
- **Hooks:**
  - lifecycle: `blog.post`, drafted, scheduled and published;
  - taxonomy: `blog_category`, flat, one term a post;
  - search: each live post by its title, summary and body; a live post's save indexes it again;
  - seed: News, Poetry and Rap battles, a live post in each, one scheduled a week out with no cover and one draft;
  - export and erase: the posts a person wrote, listed; on erase, the posts kept as the site's and their author forgotten;
  - dashboard: "A scheduled post has no cover image" (`blog.post.write`), its Add a cover opening the post.

## Settings and env vars

None.

## Install notes

`mechframe add media` first, then `mechframe add blog`, then the migrations. Its web binding imports media's `ImagePicker` and `Picture` as `@/modules/media/public` (decision 0057): a site made before that takes the alias with `mechframe upgrade kernel`. A site that draws its own header places `SlotOutlet name="nav.public"` in it for the Blog link.

## Extension points

`blog.post.published`, for a module that posts or mails a new post.

**Its public surface** (0.1.1), for a site whose own Blog and Post pages replace blog's at `/blog` and `/blog/:slug` (the same rank, which `server_copy.build` allows) and draw blog's posts:

- **Web, `@/modules/blog/public`** (decision 0057): `usePosts({ category })` (an infinite query, 12 a page), `usePost(slug)` (a `LivePost`, or a `PostMoved` that `isMoved` tells apart; any other slug a 404 `blog.post_not_found`) and `useCategories()`; the types `PostCard`, `PostCards`, `PostCover`, `LivePost`, `PostMoved`, `BlogCategory` and `BlogCategoryCount`; and `pathOf(slug)` and `day(at)`.
- **Backend, `blog.public`**, for the site's server copy: `posts(db, category=, cursor=, limit=)`, `newest(db)`, `post(db, slug)` (a `LivePost`, a `PostMoved` or None) and `categories(db)`, each the API's answer for the same read, and `path(slug)`. Their dates (`published_at`, `updated_at`) are ISO 8601 text with the zone (`kernel.answers.When`), as the API answers them, never `datetime`: parse one with `datetime.fromisoformat`. A post's title in search results, left empty, is "{title} · {site name}", as the kernel titles its own pages.

## Known limits

- One category a post: no tags, series or categories under categories.
- No comments, reactions, community posts or newsletter sends here: the switches wait for those modules.
- No embeds in a body (`embeds`, M5): an image in the body is Markdown's `![alt](address)`.
- No AI writing help or generated covers yet: they're the blog's next PRs (`dev plans/contracts/blog.md` §8).
- No revision history, and no redirect from a deleted post.

## Source and license

Lifted from VybeSite at `f659d7c`: `backend/app/models/blog.py` (the post and its related posts), `backend/app/services/blog_service.py` (the slug from a title, an apostrophe dropped), `backend/app/services/related_posts.py` (the related posts' rules) and `backend/app/routers/blog_admin.py` and `blog_public.py`. The owner's code, proprietary. VybeSite keeps a post's address once it's published; this blog lets it move and leaves a 301, as `pages` does.
