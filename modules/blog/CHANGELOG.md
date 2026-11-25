# Changelog: blog

## 0.1.5

- The post editor draws the kernel's `ShareParts` after After publishing (decision 0067): with `social` on, its Share card shares a live post to the site's channels through Buffer. Blog imports nothing of social, and draws nothing there without it.

## 0.1.4

- Generated covers (decision 0065, `dev plans/contracts/blog-covers.md`): Draw a cover in the editor's Cover image block, for someone holding `kernel.ai.write` and `media.image.upload` while a key works and media's storage is on. Claude draws an SVG from the post as it stands, in Editorial, Signal, Minimal or Custom, in the site's colours and with its name in the corner if asked; the kernel cleans it to an allowlist (`kernel.svg`), and Use this cover keeps it in the media library as a 2400 × 1260 PNG with its alt text (`media.public.store`), placed as the post's cover. `GET /admin/covers` says whether storage is on, `POST /admin/covers/draw` draws (one call against the AI's budget, its one repair try included), answering the SVG and a preview the kernel rendered as the PNG will be, and `POST /admin/covers` keeps it (422 `blog.cover_refused`). It requires media `^0.1.4`. The task, its styles and the wordmark are VybeSite's, lifted from `services/anthropic_service.py` at `8be91df`.

## 0.1.3

- `blog.post.published` is version 2: it carries the post's `summary` ("" when it has none), so campaigns' email holds it. A payload refuses fields it doesn't declare, so the field is a new version (SPEC 11 and 13), and `schema/events/` holds `blog.post.published.v2.schema.json` in v1's place.
- The editor's crossed saves, closed as pages' were in 0.1.1 (#138): a retry, and the save after a conflict's choice, carry the fields known to be the person's, so a field typed back to its saved value is still asked about if that save meets another; and both read the form they send at once, so a second conflict never takes someone else's change for the person's and sends it back.

## 0.1.2

- The editor hands its Title, Summary (300) and search fields to the kernel's Write with AI (decision 0058), so its Titles, Summary and Search words fill them; Draft and Rewrite work in the body. `blog.public`'s dates are ISO text, as `kernel.answers.When` says (MODULE.md, "Extension points").

## 0.1.1

- Its public surface, for a site whose own Blog and Post pages replace blog's: `web/public.ts` (`usePosts`, `usePost`, `useCategories`, `isMoved`, `pathOf`, `day` and the answers' types, as `@/modules/blog/public`) and `blog.public` (`posts`, `newest`, `post`, `categories`, `path`) for its server copy, each the API's answer. blog's own pages read through the same hooks (MODULE.md, "Extension points").

## 0.1.0

- First version: posts in Markdown with a slug under /blog, moves that never chain, one category from the kernel's `blog_category` terms, a cover from the media library, an author, up to three related posts, the board with its Categories card and the editor, the server copy, `blog.post.published` once a post, and the lifecycle, taxonomy, search, seed, privacy and dashboard hooks (`dev plans/contracts/blog.md`).
