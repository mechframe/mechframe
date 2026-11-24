---
feature: The site frame holds its footer back until the page is in `<main>`, so a first load doesn't shift (decision 0066; VM Website Dev 15's ask, with the owner's OK, 2026-11-24)
status: approved
approved: 2026-11-24, as recommended ("Approve as recommended"): §8, 1, the CSS rule
plan: `dev plans/2026-11-24-next-session-m4i-covers-build.md` §4, 2 (the owner, 2026-11-24: next, after covers)
pr: — (read from GitHub just before the push)
---

# Contract: the footer's first-load shift

## 1. Goal

On every MechFrame site, a page's first load no longer moves the footer. Today the site frame draws the header, an empty `<main>` and the footer, and the page's code arrives after that first paint. The footer then jumps from just under the header to below the page: Lighthouse measures a layout shift of 0.40 on a phone and 0.16 at 1440 (good is 0.1 or under), which takes about 19 points off Performance on every page. VM Website Dev 15 measured it on 6 of 6 first loads: `C:\DEV\VM Website\dev plans\2026-11-24-lighthouse-after-141.md`.

## 2. Interfaces

**One CSS rule in the site frame's stylesheet,** `kernel/web/src/app/frames.css`, in the layer the frame's other rules are in:

```css
/* Nothing after <main> is drawn while it's empty, so the page's arrival never moves the footer (decision 0066).
   Important, because the frame's rules are in the layer mf.base, and a site's own footer styles, outside
   any layer, would otherwise win with their own display. */
.mf-site > #main:empty ~ * {
  display: none !important;
}
```

- While `<main id="main">` holds nothing, the footer is hidden, and so is anything else the frame draws after `<main>`: the kernel's footer, a site's own (`defineSite({ footer })`), and the `AfterFooter` holder. `<main>` is empty while the page's code loads (`Loaded`'s `Suspense fallback={null}`), while the module switches are read (`ModuleGate`), and while a member page waits for the session (`RequireAuth`).
- When the page is in, the footer appears under it. An element that appears isn't a layout shift; only one that moves is, so the score is 0.
- The header is above `<main>` and draws at once, as now.
- A move between pages keeps the page shown until the next one is ready (React Router's navigations are transitions), so `<main>` isn't empty between pages and the footer stays.
- **No change to the frame's components, its slots, or `mountApp`.** Nothing new on the kernel's surface.

## 3. Data

None.

## 4. Files

- `kernel/web/src/app/frames.css`: the rule.
- `kernel/tests/e2e/frame.spec.ts`: the test below.
- `templates/site/`: none. A site takes the fix with `mechframe upgrade kernel`.
- **Docs:** `docs/decisions/0066-the-footer-waits-for-the-page.md`; SPEC section 8 (the site frame), one line, and the change log; `docs/progress.json`, then `python -m tools.progress`.

## 5. Conventions this follows

`CLAUDE.md`, Rules (tests first: the test is seen failing before the rule goes in); the `verify-real-pass` skill (a test that proves the shift, with a control); the frame's own CSS layering in `frames.css`.

## 6. Non-goals

- Not loading the first page's code before the first render (route-level `lazy`, or a preload in `mountApp`). That would also draw the page sooner, but it changes the router and the module gate, for a gain this rule already gives the score.
- Not a `min-height` on `<main>` to push the footer below the fold: it would change every short page's layout.
- No change to the admin frame or the sign-in frame: neither has a footer.
- No other Lighthouse findings (VM Website's home page has no meta description yet; that's the site's own Settings).

## 7. Acceptance

- **End to end, `kernel/tests/e2e/frame.spec.ts`,** "A first load doesn't move the footer", at 412 × 823 (Lighthouse's phone) and 1440 × 900, on `/`, on `/blog` (a module's lazy page) and on a 404:
  - every script request is held back 400 ms (`page.route`), so the frame always paints before the page arrives, as on a phone;
  - a `PerformanceObserver` for `layout-shift` (without `hadRecentInput`) sums the shifts from the first load to the page drawn: the sum is at most 0.01;
  - the footer is visible once the page is in, below it;
  - a site's own footer with `display: flex` outside any layer is hidden the same way (a stylesheet added in the test).
  - **Seen failing first,** without the rule: the sum is over 0.1 at 412.
- **Kept:** the frame's existing tests (`frame.spec.ts`, the Vitest frame tests) and the template's smoke stay green.
- **Live:** none here. Once it lands, VM Website upgrades its kernel and measures again with its layout-shift script (0 expected on `/`, `/contact` and `/blog`).

## 8. Open questions

None. The owner's answer, 2026-11-24, as recommended:
1. **The fix:** the CSS rule above, hiding what's after `<main>` while `<main>` is empty, not loading the first page's code before the first render (a change to the router and the module gate, with more to go wrong).

## Changes after approval

- 2026-11-24, as built:
  - **The test** gives the footer VM Website's height (327 px) and a `display: flex` of its own in a stylesheet outside any layer, as a site's footer styles are, in every case, so the separate "site's own footer" case is folded in. It runs with Playwright's `bypassCSP`: the site's policy refuses the test's inline stylesheet.
  - **It measures `/` and the 404 page, not `/blog`.** Blog's page draws its heading first and its list once its read answers, so the list still grows under the footer then (50 px, 0.03 at 412, under 0.1): that's the page's own, not the frame's. Before the rule, `/` and the 404 measured 0.13 and 0.14 at 412; after it, 0. A page holding back until its first read closes its own part (a follow-up for blog's, and any other module page that draws in two steps).
  - **The mutant:** without `!important`, all four fail.
  - **The header's links,** loaded from the modules after the first paint, nudge it under 0.003: the bound is 0.01, not 0.
