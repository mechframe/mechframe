# 0066: The site frame's footer waits for the page

- **Status:** Decided. The owner approved `dev plans/contracts/footer-shift.md` as recommended on 2026-11-24, and put it next, after generated covers. Applied in its PR.
- **Context:**
  - The site frame draws the header, an empty `<main>` and the footer, and a page's code arrives after that first paint (every page loads lazily). The footer then jumps from just under the header to below the page.
  - VM Website Dev 15 measured it on staging: a layout shift of 0.40 on a phone and 0.16 at 1440, on every page's first load, which alone takes about 19 points off Lighthouse's Performance (`C:\DEV\VM Website\dev plans\2026-11-24-lighthouse-after-141.md`). Good is 0.1 or under.
  - `<main>` is also empty while the module switches are read (`ModuleGate`). While a member page waits for the session, `RequireAuth` draws an empty `<div aria-busy="true">` in it, so it isn't empty then, and the rule names that state too (CodeRabbit on #148).
- **Decision:**
  1. **One rule in `frames.css`:** `.mf-site > #main:empty ~ * { display: none !important; }`, and the same for a `<main>` holding only the session guard's empty busy mark (`#main:has(> [aria-busy="true"]:only-child:empty)`; CodeRabbit on #148). While `<main>` holds nothing, the footer and anything else after `<main>` (a site's own footer, the `AfterFooter` holder) aren't drawn. When the page is in, the footer appears under it. An element that appears isn't a layout shift, so the score is 0.
  2. **`!important`,** because the frame's rules are in the layer `mf.base`, and a site's own footer styles, outside any layer, would win with their own `display` otherwise.
  3. **A move between pages** keeps the page shown until the next one is ready (React Router's navigations are transitions), so the footer stays.
- **Rejected:**
  - **Loading the first page's code before the first render** (route-level `lazy`, or a preload in `mountApp`): the page would draw a little sooner, but it changes the router and the module gate, with more to go wrong.
  - **A `min-height` on `<main>`** to push the footer below the fold: it would change every short page's layout.
  - **The site's own guard** (VM Website's way 2): the kernel's rule covers every site.
- **Consequences:**
  - `frame.spec.ts` measures a first load at 412 × 823 and 1440 × 900 with every script held back 400 ms and a 327 px footer styled outside any layer: 0 on the kernel's home and its 404 page, against 0.13 and 0.14 at 412 before the rule. Without `!important`, all four fail.
  - **A page that draws its heading first and its content once its read answers** still grows under the footer then. Blog's own `/blog` moves it 50 px as its list arrives (0.03 at 412, under 0.1). That's each page's own, closed by the page holding back until its first read. Blog 0.1.6 does so for `/blog`, holding back until its posts and categories answer.
  - A site takes the fix with `mechframe upgrade kernel`.
