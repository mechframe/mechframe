---
feature: The pages module, the site's fixed pages such as About and Credits (Vibrant Mindz step 1; M4's first job)
status: approved
plan: `docs/plans/vibrant-mindz-backend/extraction/pages.md`; `dev plans/2026-11-21-vibrant-mindz-push-plan.md` (M4); the canvas's AdminPages and AdminPost boards (`C:\DEV\VM Website\design\site\AdminPages.dc.html`, `AdminPost.dc.html`)
approved: 2026-11-21 (the owner's four answers in §8: 2 and 3 as recommended; 1 for now, with VybeSite's builder to follow; 4, header and footer)
pr: the kernel's editor first (decision 0055, #118), then `pages` (decision 0056, #121)
---

# Contract: `pages`

## 1. Goal

The fixed pages a site's people write themselves: About, Credits, Privacy, Terms. Each is a title, an address, a body written in Markdown and its search and sharing words, drafted and then published, and listed in the header's menu, the footer's or neither. The board says "Pages use the same editor as blog posts, with the same Search and sharing fields", so the editor is built once, in the kernel, for pages first and `blog` next. From VybeSite's pages (`models/page.py`, `services/pages_service.py`, `routers/site_pages.py`) this version keeps the address rule, the moves an address change leaves, the search words with their fallback and who changed a page last. **VybeSite's builder comes next** (the owner: "we will definitely be porting the VybeSite Builder, because that was really the whole point"), as pages' next version with a contract of its own; nothing here is in its way, since its pages need the same addresses, moves, lifecycle and menus.

## 2. Interfaces

**Permissions:** `pages.page.write` (owner, admin, editor) to list, write, save and preview; `pages.page.publish` (owner, admin, editor) to publish, schedule, unpublish and delete. Granted in `pages_0001`, as media's are.

**HTTP** (`/api/pages`, behind `require_module("pages")`; RFC 9457 codes `pages.*`):

| Route | Access | Does |
| --- | --- | --- |
| `GET /page?address=/about` | public | The live page: `{title, address, html, search_title, search_description, updated_at}`; 404, or `{moved: "/new"}` for an old address |
| `GET /menu?place=header` (or `footer`) | public | The live pages in that menu, in order: `{items: [{title, address}]}` |
| `GET /admin/pages` | `pages.page.write` | `{items}`: every page, newest edit first: title, address, status, menus, `updated_at`, `updated_by` |
| `POST /admin/pages` `{title, address, body, ...}` | `pages.page.write` | 201, a draft. 409 `pages.address_taken`, naming who answers the address |
| `GET /admin/pages/{id}` | `pages.page.write` | The page with its Markdown, its `version` and its moves |
| `PATCH /admin/pages/{id}` `{..., version}` | `pages.page.write` | Saves it; a live page changes on the site at once (§8, 3). 409 `pages.changed` on a stale `version`, with the page now |
| `POST /admin/preview` `{body}` | `pages.page.write` | The HTML the site would draw, unsaved words included |
| `POST /admin/pages/{id}/publish` `{at?}` | `pages.page.publish` | Publish now, or schedule (`kernel.lifecycle`) |
| `POST /admin/pages/{id}/unpublish` | `pages.page.publish` | Back to a draft; its address answers 404 |
| `DELETE /admin/pages/{id}` | `pages.page.publish` | 204; its moves go with it |

**An address** is one segment: lowercase letters, digits and single hyphens (`/about`, `/press-kit`), VybeSite's rule. The start's route table (`app.state.public_routes.resolve`) decides it: one that the kernel, the site's own pages or another module answers is refused (`/blog`, `/sign-in`), so a page can never be hidden behind another. **A move:** a live page given a new address leaves a 301 from the old one (`server_copy.Moved`), a live page at that address wins, and a move to a page that moves again is pointed at its end, so none chains.

**Public pages:** module.json's `routes.public` is `["/:address"]`; `server_copy.py`'s `PAGES` answers each live page (its title, search words, cleaned HTML, a `WebPage` JSON-LD) or a `Moved`, and lists them in the sitemap and `llms.txt`. The web's `/:address` route draws the page with the kit's `Prose`, or the 404 page.

**Menus** (decision 0056, in pages' PR; §8, 4): a link slot's entries may be loaded from a module's own API, `defineModule({ links: { "nav.public": load } })`, each loader run through TanStack Query while its module is on and its links put after the module's fixed ones, so `useSlot` and `SlotOutlet` give them unchanged; and a link slot for the footer, `nav.footer`. The frame's own header and footer draw both. pages loads `nav.public` from `GET /menu?place=header` and `nav.footer` from `?place=footer`. A site with its own header and footer (Vibrant Mindz) places them with `useSlot` or `SlotOutlet`: a note for VM Website.

**The kernel's editor** (decision 0055, its own PR first; §8, 2): `kernel.markdown.render(text) -> str`, Markdown made HTML on the server and cleaned by nh3 to VybeSite's body allowlist with no `h1` (SPEC 15, "User HTML"); the kit's `MarkdownEditor` (Write and Preview tabs, the board's B, I, H, quote and link buttons, preview through the module's route, and `tools`, buttons a module adds: `blog`'s writing help and image generation, `embeds`' Embed), `SearchFields` (title in search results and description, saying what they fall back to) and `Prose` (cleaned HTML drawn in the theme's type).

**Admin pages** (`nav.admin` under Content): `/admin/pages`, the board's list (Page and address, Status, Menu, Last edited, Edit; New page), and `/admin/pages/:id`, the post editor's frame with Details (Address; Menu: Header, Footer, both or Not in a menu; its place in the menu) and Search and sharing, and the Publish panel's Draft or Live, Publish now or Schedule, Update and Unpublish.

**Hooks:** lifecycle (`pages.page`: draft, scheduled, published); search (`pages.page`: title, the body's words); seed (About and Credits live in the footer, one draft); export and erase (`privacy.py`: the pages a person last changed, listed; erase clears `updated_by`); dashboard (`ATTENTION`: "There's no privacy page yet" while no page at `/privacy` is live, `pages.page.write`, its Write it opening a new page at that address with a few headings to fill). No taxonomy, bot check or consent.

## 3. Data

`pages_page`: `id` uuid, `version` int, `title` (≤ 120), `address` unique (≤ 60, CHECK the rule), `body` Markdown (≤ 100,000), `search_title` (≤ 70) and `search_description` (≤ 160), each null to fall back to the title and the body's opening words, `in_header` and `in_footer` booleans, `menu_order`, the lifecycle's columns and CHECK, `updated_by` → `auth_user` `ON DELETE SET NULL`, `created_at`, `updated_at`. `pages_move`: `address` primary key, `page_id` → `pages_page` `ON DELETE CASCADE`, `created_at`. Branch `pages`, `pages_0001`, `depends_on` `kernel_0002`, as media's does. The HTML isn't stored: `render` runs per read, and the server copy's reads are the API's own.

## 4. Files

`modules/pages/` as `modules/_template/` lays out: `backend/pages/` (`__init__`, `models`, `schemas`, `service`, `addresses`, `router`, `server_copy`, `lifecycle`, `search`, `privacy`, `dashboard`, `seed`), `migrations/`, `web/` (`module.web.ts`, `api.ts`, `pages/AdminPages.tsx`, `AdminPage.tsx`, `PublicPage.tsx`), `tests/` (`backend/`, `contract/`, `web/`, `e2e/`), `module.json`, `MODULE.md`, `CHANGELOG.md`, `openapi.json`. `catalog.json` regenerated. Kernel, decision 0055's PR: `kernel/backend/kernel/markdown.py`, the kit's three parts, `requirements.in`'s Markdown library, SPEC 6, 8 and 15. Kernel, in pages' PR: the slots' loaded links and `nav.footer` (`kernel/web/src/slots/`, the frame), SPEC 8.

## 5. Conventions this follows

SPEC 4 to 9 and 16; `skills/mechframe-module-extractor/SKILL.md` and `module-contract-lint`; the kit for every screen; the lifecycle, search, seed, privacy and dashboard hooks as `dev plans/contracts/hooks.md` defines them; media's row conflict (`media.changed`, its contract's changes after approval).

## 6. Non-goals

- **For now,** VybeSite's builder: sections and their designs, the theme's starter pages, the twelve-column layout, fonts and colours (`site_theme.py`, `site_layout.py`, `fonts/catalogue.json`). It's pages' next version (§1).
- A working copy of a live page, VybeSite's changes drawer (§8, 3).
- Menus nested in menus, and addresses of more than one segment.
- Embeds in a page's body (`embeds`, M5); the media library's picker in the editor (a body's image is Markdown's `![alt](address)`, an address `media`'s Copy link gives).
- A page's revision history; a redirect from a deleted page; writing the privacy page's words.

## 7. Acceptance

- `kernel.markdown`: each allowed tag kept, a script, a style, an `on…` attribute and a `javascript:` link gone, an `h1` made an `h2`, the result stable when cleaned again.
- Contract tests: every route's access (anonymous 401, member 403, editor allowed; public reads open), a taken address 409 naming its owner, an address change leaving a move that answers 301, no chain after two changes, a stale `version` 409, a draft and an unpublished page 404, a scheduled page live once `kernel.publish_due` runs, each menu's pages in order.
- The server copy: a live page's head, words and JSON-LD, a move's 301, a draft's real 404, the sitemap's entries.
- The slots: a module's loaded links after its fixed ones, none while it's off, a failed load leaving the rest; the frame's footer drawing `nav.footer`.
- Migration round trip; the seed twice gives the same rows; export lists a person's pages; erase clears `updated_by`; the privacy item shows and goes.
- Web: both admin pages and the public page in both themes against the boards, axe clean; the editor's Write and Preview, unsaved changes guarded.
- `python -m tools.validate_schemas`, `module-contract-lint`, the brand check, and `mechframe add pages` then `mechframe check` on a new site.

## 8. The owner's answers (2026-11-21)

1. **What a page is:** a Markdown page for the Vibrant Mindz site for now, and VybeSite's builder ported after ("that was really the whole point"). For `blog`: the whole blog system from the start, its editor, AI-assisted writing and image generation (its contract; the kernel's `ai.client()` isn't built yet).
2. **Where the shared editor lives:** the kernel, in its own PR first (as recommended).
3. **Saving a live page:** Save changes the site at once (as recommended): the panel says Live, its button Update, and Preview shows the words before they're saved; Unpublish takes it down. `blog` does the same.
4. **Menus:** header and footer (recommended was footer only), so the slots take links a module loads (decision 0056).

## 9. Changes after approval

- 2026-11-22, in #121: `GET /menu` and `GET /admin/pages` answer `{items: [...]}`, not a bare list, since every answer of the API is a typed object (`tests/test_openapi.py`). The admin's list isn't paged: a site's fixed pages are a handful.
- 2026-11-22, in #121: the kernel exports its `NotFound` page, which the public page draws for an address with no live page.
