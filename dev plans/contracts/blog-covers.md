---
feature: Generated covers for blog posts (decision 0065; `blog.md` §8, 3, answered 2026-11-22)
status: approved
approved: 2026-11-24, as recommended ("Approve as recommended"): §8's five answers
plan: `dev plans/2026-11-23-next-session-m4h-blog-covers.md` §4, 2; after blog 0.1.3 (#143) and the AI's model (#144)
---

# Contract: generated covers

## 1. Goal

From a post's editor, a writer who may use the AI asks for a cover. Claude draws an SVG from the post in one of VybeSite's styles, which the owner chose (`blog.md` §8, 3). The server cleans it to an allowlist and shows it. On "Use this cover", the server makes it a PNG and stores it in the media library as any image, with the alt text Claude wrote and the writer can change. It's then placed as the post's cover, kept when the post is saved, as a chosen cover is.

It's a PNG, not VybeSite's SVG, as the owner asked:
- an SVG is a document that can carry scripts, and media refuses one;
- social sites don't take an SVG `og:image`;
- every cover then gets media's sizes, `srcset` and uses, like any other.

## 2. Interfaces

**The kernel's SVG helper, `kernel.svg`** (new, SPEC 6; §8, 3). The kernel holds it because a module can't declare a Python dependency (`module.schema.json` has no place for one), and because other modules can draw with it too (discography's artwork, a page's share card).

- **`svg.clean(text, *, width, height) -> str`** takes the first `<svg>…</svg>` in a model's answer.
  - **Refused** (`svg.Refused(reason)`, in words for the model's one repair try) when it holds a DOCTYPE or an entity, is over 100 KB, holds over 5,000 elements or nests deeper than 32, or leaves nothing drawable.
  - **Rebuilt** from the allowlist below and written out by the kernel. What's stored and rendered is never the model's own text. The root gets `viewBox="0 0 {width} {height}"`, `width` and `height`.
  - **Elements kept:** `svg`, `g`, `defs`, `title`, `desc`, `path`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `text`, `tspan`, `linearGradient`, `radialGradient`, `stop`, `clipPath`, `mask`, `pattern`, `filter`, and the filter primitives:
    - `feBlend`, `feColorMatrix`, `feComponentTransfer` (with `feFuncR`, `feFuncG`, `feFuncB` and `feFuncA`), `feComposite`;
    - `feDisplacementMap`, `feFlood`, `feGaussianBlur`, `feMerge`, `feMergeNode`, `feOffset`, `feTurbulence`;
    - and `use`, only to a local `#id`.
  - **Dropped, with all they hold:** `script`, `style`, `foreignObject`, `image`, `a`, `textPath`, `animate`, `animateMotion`, `animateTransform`, `set`, `font`, `iframe`, any element not listed, and anything outside the SVG namespace.
  - **Attributes kept:** `id`, and the listed elements' geometry, presentation, gradient, filter and text attributes (`x`, `y`, `d`, `points`, `transform`, `fill`, `stroke`, `opacity`, `stop-color`, `stdDeviation`, `font-size`, `font-weight`, `letter-spacing`, `text-anchor` and the rest, each named in the code's table).
    - `href` and `xlink:href` are kept only as `#id`, and a `url(…)` only as `url(#id)`.
    - Every `font-family` becomes the kernel's font (§8, 2).
  - **Attributes dropped:** every `on…`, `style`, `class`, anything holding `javascript:` or `data:`, and any attribute not listed.
- **`svg.png(svg, *, width, height) -> bytes`** renders with resvg, using the kernel's font files only, never the system's. It runs in a worker thread, in at most 10 seconds.
- **The font:** Inter (OFL-1.1) in three weights, Regular, SemiBold and Bold, in `kernel/backend/kernel/fonts/` (about 900 KB), its licence in NOTICE (§8, 2).

**The dependency:** `resvg-py==0.5.0` (MIT; resvg itself is Apache-2.0). It has wheels for Windows, glibc and musl Linux, and macOS, and needs no system library. Pinned with hashes in `requirements.in` and `requirements.txt`, and the template's through `tools.site_template`. CairoSVG was the other choice: LGPL, and it needs Cairo installed (GTK on Windows).

**Blog's task, `blog.covers`:**
- **`draw`** calls `await ai.client(db)`, then `writer.write(task, schema={svg, alt}, max_tokens=12000, effort="medium", seconds=180, retries=0)`. It uses the model in use (decision 0064), as every task does. The answer is cleaned to 1200 × 630, the blog card's shape (`blog.css`). A refusal gets one repair try with its reason, as VybeSite's does. If the repair fails too, it's 502 `kernel.ai_failed`: "The AI couldn't draw a cover this time. Try again, or change what you asked for."
- **The styles** are VybeSite's, in its words:
  - Editorial: the title large, with an eyebrow, one accent rule and quiet geometry;
  - Signal: thin waveform or network lines, with no title;
  - Minimal: the title set modestly, with one accent detail;
  - Custom: drawn from the writer's description.
- **The site's colours,** `{ground, ink, accent}` as `#rrggbb`, come from the editor: it reads the theme's tokens (`--mf-color-surface`, `--mf-color-text`, `--mf-color-accent`), since the server never sees a site's theme. Editorial, Signal and Minimal always use them; Custom only when "In the site's colours" is on.
- **The wordmark:** the site's name (`server_copy.identity`), set by code after cleaning, on a plate of the ground colour in the top-left corner, as VybeSite does. The model is only told to keep that corner clear. It's added when "With the site's name" is on.
- **A revision** sends the shown SVG back with "What to change" (at most 600 characters), the wordmark taken off first, as VybeSite does.

**HTTP**, under `/api/blog/admin`:
- **`POST /covers/draw`** needs `blog.post.write` and `kernel.ai.write`. Each press is one call against the kernel's AI_RATE_LIMIT budget, its repair try included.
  - It takes `{title, summary, body, style, description?, colours?, wordmark, current?, changes?}`: the editor's fields as they stand, so a post not yet saved can have a cover. The body is read only as far as `ai.BODY_READ`, and `current` holds at most 100 KB.
  - It answers 200 `{svg, alt}`, cleaned, with `alt` at most 250 characters (media's). It answers 503 or 502 as the AI's routes do, and 422 for a body out of its limits.
- **`POST /covers`** needs `blog.post.write` and `media.image.upload`.
  - It takes `{svg, alt}`. The SVG is cleaned again, never trusted from the browser, then made a PNG at 2400 × 1260 (twice the card) and stored through `media.public.store`.
  - It answers 201 `{"cover": Cover}`, blog's cover shape, which the editor puts in the Cover field.
  - It answers 422 `blog.cover_refused` for an SVG with nothing drawable left, and media's 503 `media.storage_off` while storage is off. It spends no AI budget.
  - The image stays in the library like any upload, used or not.

**Media 0.1.4:** `media.public.store(db, data, *, filename, alt, by) -> Picture`. It's another module's image, put through upload's checks and stored with its alt. The same bytes again answer the image already kept, as an upload does. It's audited as `media.image.uploaded`.

**The fake:** `harness/fake_anthropic.py`'s structured answers fill a string property named `svg` with a small drawable SVG, `COVER`. So the cover flow runs end to end in every suite, and no suite calls Anthropic. A test can queue an answer the cleaner refuses.

**Web,** `AdminPost.tsx`'s Cover image block (§8, 1):
- **The button:** "Draw a cover", with the sparkle icon Write with AI has, beside "Choose a cover" or "Change". It shows to someone holding `kernel.ai.write` while a key works (`GET /api/kernel/ai`'s `ready`) and media's storage is on.
- **The dialog, "Draw a cover":** Style, a select; "What to draw", shown for Custom, at most 600 characters; the switches "In the site's colours" (for Custom) and "With the site's name"; and Draw.
- **Then the preview:** an `<img>` of the cleaned SVG as a `data:` URL, where no script can run, at the card's shape. Under it:
  - Alt text, filled with Claude's and editable, with the hint "Says what the cover shows, for anyone who can't see it.";
  - "What to change" with Change it, Draw again, and Use this cover.
- **Use this cover** stores the cover, puts it in the Cover field, closes the dialog and says "The cover is in place. Save the post to keep it."

## 3. Data

None. Covers are rows of `media_image`, as uploads are, and blog keeps `cover_id`, as it does now. No migration; `blog_0002` stays free.

## 4. Files

- **Kernel:**
  - `kernel/backend/kernel/svg.py` (new) and `kernel/tests/test_svg.py`;
  - `kernel/backend/kernel/fonts/` with Inter's three files, and Inter's licence in `NOTICE`.
- **Blog:**
  - `modules/blog/backend/blog/covers.py` (new): the task, its styles, the wordmark;
  - `router.py`: the two routes;
  - `tests/backend/test_covers.py` and `tests/contract/test_covers_contract.py`;
  - `web/pages/AdminPost.tsx`, `web/components/CoverDialog.tsx` (new) and `tests/web/covers.test.tsx`;
  - `module.json`: version 0.1.4 and `kernel.ai.write` in what it reads;
  - `CHANGELOG.md` and `MODULE.md`.
- **Media:** `modules/media/backend/media/public.py` (`store`), its test, and media 0.1.4's `module.json`, `CHANGELOG.md` and `MODULE.md`.
- **Harness:** `harness/fake_anthropic.py` (`COVER`).
- **Dependencies:** `requirements.in` and `requirements.txt` (`resvg-py`), the template's through `python -m tools.site_template`, `docs/TESTING.md`'s frameworks table, and `CLAUDE.md`'s Stack.
- **Generated:**
  - the OpenAPI specs and `schema.ts` (`python -m tools.openapi`, `npm run api:types`);
  - `catalog.json`, and `docs/HOST-VARIABLES.md` for the versions;
  - `docs/progress.json`, then `python -m tools.progress`.
- **Docs:**
  - `SPEC.md` 6 (`kernel.svg`'s row) and 15 (an SVG from a model is cleaned to an allowlist and only ever served as a PNG), plus the change log;
  - `docs/decisions/0065-generated-covers.md`;
  - `dev plans/contracts/blog.md` §9 and `media.md`, a line in each.

## 5. Conventions this follows

- Decision 0058: covers go through `ai.client(db)`, never a key in the browser, failures in plain sentences, and no suite calls Anthropic.
- Decision 0041's way with HTML, applied to SVG: an allowlist, then the kernel's own serialisation.
- Media's upload checks, and the `use` that saving a post already records.
- VybeSite's cover task: its styles, the wordmark's plate and corner, one repair try, a revision with the wordmark off.
- `CLAUDE.md`'s provenance rule: the brand check runs on anything lifted from VybeSite.

## 6. Non-goals

- No SVG kept, served or shown outside the dialog's preview: only the PNG is stored.
- No cover drawn on its own when a post is published, and no cover for pages or other modules yet. `kernel.svg` makes those possible later.
- No image model. Claude draws vectors, as VybeSite's does.
- No price shown for a draw.
- No `<image>`, so no photo or logo file goes inside a cover. The wordmark is the site's name in Inter.

## 7. Acceptance

- **`kernel/tests/test_svg.py`:**
  - `test_only_the_allowlist_survives`, parametrized over a script, an `onload`, a `style`, an `<image>`, `foreignObject`, a `javascript:` and a `data:` `href`, an outside `url()` and a `textPath`;
  - `test_a_doctype_or_an_entity_is_refused`;
  - `test_too_big_too_many_or_too_deep_is_refused`;
  - `test_what_is_written_out_is_the_kernels_own`;
  - `test_every_font_is_the_kernels`;
  - `test_a_cleaned_svg_renders_to_a_png_of_its_size`: the PNG's header holds 2400 × 1260.
- **`modules/blog/tests/backend/test_covers.py`:**
  - `test_each_style_says_its_direction_and_the_sites_colours`;
  - `test_a_refused_drawing_gets_one_repair_then_a_plain_failure`;
  - `test_the_wordmark_is_set_by_code_and_taken_off_for_a_revision`.
- **`modules/blog/tests/contract/test_covers_contract.py`:**
  - `test_post_covers_draw`: 200 cleaned; 403 without `kernel.ai.write`; 503 with no key; 429 past AI_RATE_LIMIT;
  - `test_post_covers`: 201 stored as a PNG in media with its alt, and the post saved with it shows it; the SVG is cleaned again; 422 `blog.cover_refused`; 403 without `media.image.upload`.
- **Media:** `test_store_takes_another_modules_image_with_its_alt`.
- **Web, `covers.test.tsx`:** the button only with a working key and storage; draw, revise, then use, which fills the Cover field; a failure in its words.
- **End to end:** `blog.spec.ts`, "An editor draws a cover and the post shows it", against the fake, in both themes, with axe on the dialog.
- **Live:** none in the suites. Your first real cover is drawn from the editor once a key works.

## 8. Open questions

None. The owner's answers, 2026-11-24, as recommended:
1. **The button:** "Draw a cover" in the Cover image block, beside "Choose a cover", opening the dialog of §2. VM Website draws the button and the dialog's two states, the ask and the preview.
2. **Text in a cover:** kept, with Inter (OFL-1.1, three weights, about 900 KB) bundled in the kernel and every `font-family` forced to it. The build asks the owner once more before it downloads the files from rsms/inter's GitHub release, naming each file and its size.
3. **The SVG helper:** in the kernel, `kernel.svg`.
4. **The styles:** VybeSite's Editorial, Signal and Minimal, plus Custom, in its words.
5. **The PNG's size:** 2400 × 1260, twice the 1200 × 630 card and share image.

## Changes after approval

- 2026-11-24, as built so far (branch `feat/blog-covers`):
  - **`kernel.svg` is in,** with its 27 tests: the allowlist, the refusals, the kernel's own form as a fixed point, every font forced to Inter, a 2400 × 1260 PNG and a render that takes too long. Two mutants (every value kept, `script` allowed) were seen letting the bad parts through, so the tests would catch them.
  - **A DOCTYPE or an entity anywhere in the answer is refused,** not only inside the `<svg>`, so one declared before it can't slip past. The parser is the standard library's, after that refusal, with a `noqa: S314` that says why. defusedxml would be a second new dependency the contract didn't name.
  - **This project has no `docs/TESTING.md`.** The new dependency is in `CLAUDE.md`'s Stack, `requirements.in` and `requirements.txt` (`resvg-py==0.5.0`, hashed).
  - **The fonts are in** (the owner's OK, 2026-11-24: "Yes, download it"). `Inter-4.1.zip` (33,707,794 bytes) from rsms/inter's v4.1 release went into an empty scratch folder. Only `extras/ttf/`'s Regular, SemiBold and Bold (1.25 MB together, more than the 900 KB first said) and `LICENSE.txt` were copied into `kernel/backend/kernel/fonts/`, where the OFL's text travels with them into every site. NOTICE names them, and `.gitattributes` marks `*.ttf` binary. A test draws words, with a control showing they draw nothing without the kernel's fonts.
  - **Still to build:** media 0.1.4's `store`, blog's task and routes, the fake's `COVER`, the dialog, the docs and the generated files.
