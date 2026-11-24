# 0065: Generated covers: the AI draws an SVG, the kernel cleans it, media keeps a PNG

- **Status:** Decided. The owner approved `dev plans/contracts/blog-covers.md` as recommended on 2026-11-24 (§8's five answers), and VM Website drew its board, "Admin: Post editor" at canvas version 104, with the owner's OK. Applied in its PR (blog 0.1.4, media 0.1.4).
- **Context:**
  - `blog.md` §8, 3 asked for covers generated as VybeSite makes them: Claude draws an SVG in one of a few house styles, from the post.
  - An SVG is a document that can carry scripts, media refuses one, and social sites take no SVG `og:image`. A model's SVG can also hold anything: external references, a DOCTYPE with entities, a million elements.
  - A module can't declare a Python dependency (`module.schema.json` has no place for one), so whatever cleans and renders the drawing has to be the kernel's.
- **Decision:**
  1. **The kernel holds `kernel.svg`** (SPEC 6), on the public surface: `svg.clean(text, width=, height=)` takes the first `<svg>` in a model's answer, refuses a DOCTYPE or an entity anywhere in it, anything over 100 KB, 5,000 elements or 32 levels, and a drawing with nothing drawn, and rebuilds the rest from an allowlist of elements and attributes, written out by the kernel. A link (`href`, `url(…)`) is kept only to an `#id` in the drawing, and every `font-family` becomes Inter. `await svg.png(svg, width=, height=)` renders it with resvg (`resvg-py`, MIT) in a process of its own (`python -I`, only resvg imported), stopped at 10 seconds, with the kernel's own fonts and never the system's. A thread can't be stopped, so a slow render would have kept running past the limit (Codex on #147).
  2. **Inter** (OFL-1.1), Regular, SemiBold and Bold, is bundled in `kernel/backend/kernel/fonts/` with its licence (the owner's answer 2, and their OK for the download).
  3. **Only a PNG is ever kept or served** (SPEC 15). The SVG lives in the editor's dialog, shown as an `<img>` of a `data:` address, where nothing in it runs. `POST /api/blog/admin/covers` cleans what the browser sends again, never trusting it, then keeps a 2400 × 1260 PNG, twice the card (the owner's answer 5), through media 0.1.4's `public.store`.
  4. **Blog's task, `blog.covers`,** is VybeSite's: Editorial, Signal and Minimal in its words, plus Custom from the writer's description (the owner's answer 4); its hard requirements; one repair try with the reason the cleaner gave; and a revision that sends the drawing back with the changes. It asks through `ai.client(db)` for `{svg, alt}`, so Claude writes the alt text too. A second refusal is 502 `kernel.ai_failed`, "The AI couldn't draw a cover this time. Try again, or change what you asked for."
  5. **The site's colours come from the editor,** which reads the theme's surface, text and accent tokens where it's drawn: the server never sees a site's theme. Custom uses them only when "In the site's colours" is on.
  6. **The wordmark is set by code,** the site's name in Inter SemiBold on a plate of the ground colour in the top-left corner, over a rule of the accent, as VybeSite sets it. The model only keeps the corner clear. A revision takes it off before the model sees the drawing.
  7. **One budget:** each press of Draw, Draw again or Change it is one call against the kernel's AI_RATE_LIMIT, its repair try included. `ai.budget` is that dependency, now public, for any module's AI task. Keeping a cover spends none.
- **Rejected:**
  - **Keeping the SVG:** a stored SVG is a stored document. A PNG is what media, `srcset` and social sites take.
  - **CairoSVG:** LGPL, and it needs Cairo installed (GTK on Windows). resvg-py has wheels everywhere and no system library.
  - **defusedxml:** a second new dependency the contract didn't name. The cleaner refuses `<!` (other than a comment or CDATA) in the whole answer before the standard library parses it.
  - **The system's fonts:** a slim Docker image has none, and the cover would change with the host.
  - **An image model:** Claude draws vectors, as VybeSite's does; no new vendor or key.
  - **The server reading the theme:** a site's theme is CSS the server doesn't parse, and a site may change its tokens without a deploy of the kernel.
- **Consequences:**
  - `kernel.svg` and `ai.budget` are on the kernel's public surface; the kernel's web index exports `sayAi`, and the kit's toast takes `returnTo`, so its Close gives focus back to where the action began.
  - `GET /api/blog/admin/covers` answers `{storage}`, so the editor shows Draw a cover only while a cover could be kept. Media's `public.storage_on()` answers it.
  - The fake Anthropic answers a structured `svg` with `COVER`, a small drawing the cleaner keeps, so every suite draws a cover end to end and none calls Anthropic. `harness.e2e` runs with storage off, so the end-to-end test stands a kept cover in at the browser; the contract suite keeps a real one.
  - Covers for pages, discography's artwork or a share card can come later through `kernel.svg`. A cover is drawn only when asked, never on publishing.
