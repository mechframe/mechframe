# pages

The site's fixed pages: About, Credits, Privacy, Terms, a press kit. The contract is `dev plans/contracts/pages.md`.

## What it does

An editor writes a page in Markdown, with a title, an address and its words for search results and sharing, and keeps it as a draft until it's published, now or at a time to come. A live page's save changes the site at once: there's no working copy. Each page can sit in the header's menu, the footer's, both or neither, in an order the editors choose. A live page given a new address leaves the old one sending visitors to it (a 301), and a page moved twice sends both old addresses to where it is now, never along a chain. The address a page holds is its own, live or not: a page that takes an address ends any move there. An address is one segment of lowercase letters, digits and single hyphens, and never one the kernel, the site's own pages or another module answers, whether that module is on or not. The body is made HTML on the server (`kernel.markdown.render`) on every read and drawn with the kit's `Prose`; the server's copy says the same words to crawlers that run no JavaScript.

## Use when / avoid when

Use it for pages the site's people write and change themselves, chosen page by page for the menus, whose addresses may change while old links keep working. Avoid it for dated news or stories with an author: that's `blog`. Avoid it for pages laid out from designed sections: VybeSite's builder comes as pages' next version. Avoid it for a page drawn from the site's own code that never changes: that's the site's own pages (`app/site/`).

## What it adds

- **Routes**, under `/api/pages`:
  - `GET /page?address=/about` (public): the live page, `{title, address, html, search_title, search_description, updated_at}`, the search words filled in from the title and the body when left empty; `{moved}` for an address a live page left; 404 `pages.page_not_found` otherwise;
  - `GET /menu?place=header` or `footer` (public): `{items}`, the live pages in that menu, in order;
  - `GET /admin/pages` (`{items}`, every page, not paged), `POST /admin/pages` (409 `pages.address_taken`, naming who answers the address), `GET` and `PATCH /admin/pages/{id}` (with `version`; 409 `pages.changed` with the page as it is now), `POST /admin/preview`: `pages.page.write`;
  - `POST /admin/pages/{id}/publish` (`{at?}`, a time with its zone to schedule it), `POST /admin/pages/{id}/unpublish`, `DELETE /admin/pages/{id}`: `pages.page.publish`.
- **Public pages:** `/:address`, the least fixed pattern there is, so any other module's or the site's page wins its address. The server copy answers each live page with its head, its words under one `h1`, a `WebPage` JSON-LD, and lists it in the sitemap and `llms.txt`.
- **Menus:** `nav.public` and `nav.footer`, loaded from `GET /menu` (decision 0056). A site with its own header and footer places them with `SlotOutlet name="nav.public"` and `SlotOutlet name="nav.footer"`.
- **The admin pages:** `/admin/pages`, the list with New page, and `/admin/pages/:id` (`new` for a new page), the editor: Title, the kit's `MarkdownEditor` (Write and Preview), Publish, Details (Address, Menu, Place in the menu) and Search and sharing (`SearchFields`). Under Content in the sidebar.
- **Tables:** `pages_page` and `pages_move` (migration `pages_0001`).
- **Permissions:**
  - `pages.page.write` (list, write, save, preview) and `pages.page.publish` (publish, schedule, unpublish, delete);
  - both go to admin and editor, granted in the migration; an owner holds every permission.
- **Hooks:**
  - lifecycle: `pages.page`, drafted, scheduled and published;
  - search: each live page by its title and its body's words; a live page's save indexes it again;
  - seed: About and Credits live in the footer, and a Press kit draft;
  - export and erase: the pages a person changed last, listed; on erase, who changed them forgotten;
  - dashboard: "There's no privacy page yet" while no page at `/privacy` is live (`pages.page.write`), its Write it opening the draft there or a new page with a few headings to fill.

## Settings and env vars

None.

## Install notes

`mechframe add pages`, then the migrations. It needs nothing beyond the kernel: python-markdown and nh3 are in its pinned requirements. A site that draws its own footer adds `<SlotOutlet name="nav.footer" />` to it, or the footer's menu doesn't show.

## Extension points

**Its page read** (0.1.1), for a site whose own page answers `/:address` (the same rank as pages', which the site's route takes) and draws pages' live page in its own look:

- **Web, `@/modules/pages/public`** (decision 0057): `usePage(address)`, the address with its slash or without it as a route's parameter gives it. It answers a `LivePage` (`{title, address, html, search_title, search_description, updated_at}`), or a `PageMoved` (`{moved}`) that `isMoved` tells apart; any other address is a 404 `pages.page_not_found`. pages' own `PublicPage` reads through the same hook.
- **The server copy stays pages' own:** the site's page draws the same words in the same order (an `h1`, then the body), so the site adds nothing for `/:address`. There's no backend read for a site's server copy yet.

A page's title in search results, left empty, is "{title} · {site name}", as the kernel titles its own pages.

## Known limits

- An address is one segment: no `/about/team`.
- No working copy of a live page, no revision history, and no redirect from a deleted page.
- No embeds in a body (`embeds`, M5) and no media picker in the editor: an image is Markdown's `![alt](address)`, an address `media`'s Copy link gives.
- One place in the menus for both: a page in the header and the footer has the same place in each.

## Source and license

Lifted from VybeSite at `9ce7e0a`: `backend/app/models/page.py` (the address rule, the moves, the search words and who changed a page last), `backend/app/services/pages_service.py` and `backend/app/routers/site_pages.py`. The owner's code, proprietary. VybeSite's pages are built from sections; these are Markdown until its builder is ported.
