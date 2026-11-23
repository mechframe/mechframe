# Changelog: blog

## 0.1.2

- The editor hands its Title, Summary (300) and search fields to the kernel's Write with AI (decision 0058), so its Titles, Summary and Search words fill them; Draft and Rewrite work in the body. `blog.public`'s dates are ISO text, as `kernel.answers.When` says (MODULE.md, "Extension points").

## 0.1.1

- Its public surface, for a site whose own Blog and Post pages replace blog's: `web/public.ts` (`usePosts`, `usePost`, `useCategories`, `isMoved`, `pathOf`, `day` and the answers' types, as `@/modules/blog/public`) and `blog.public` (`posts`, `newest`, `post`, `categories`, `path`) for its server copy, each the API's answer. blog's own pages read through the same hooks (MODULE.md, "Extension points").

## 0.1.0

- First version: posts in Markdown with a slug under /blog, moves that never chain, one category from the kernel's `blog_category` terms, a cover from the media library, an author, up to three related posts, the board with its Categories card and the editor, the server copy, `blog.post.published` once a post, and the lifecycle, taxonomy, search, seed, privacy and dashboard hooks (`dev plans/contracts/blog.md`).
