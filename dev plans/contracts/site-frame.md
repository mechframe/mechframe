---
feature: The site's own header and footer, and full-bleed pages (VM Website's "For MechFrame" item 5)
status: approved
approved: 2026-11-21 (the owner: "Approve as recommended", the three answers in §8)
plan: VM Website docs/HANDOFF.md "For MechFrame" item 5 (the owner, 2026-11-21); SPEC 8; decision 0048
pr: predicted at push time (the highest number plus one)
---

# Contract: the site's own header and footer, and full-bleed pages

## 1. Goal

A site draws its own header and footer in the site frame, and any public or member page can run edge to edge. Vibrant Mindz's boards draw both, full width, so its site can drop the CSS in `app/web/src/site/home/frame.css` that hides the kernel's on the homepage.

## 2. Interfaces

**`defineSite`** (`kernel/web/src/modules.ts`) takes two more fields:

```ts
export type SiteDefinition = {
  routes: { public: ModuleRoute[]; member: ModuleRoute[] };
  slots?: Slots;
  /** The site's header, drawn in place of the frame's on every page in the site frame. Its root is a <header>. */
  header?: ComponentType;
  /** The site's footer, in place of the frame's. Its root is a <footer>. */
  footer?: ComponentType;
};
```

- They're components, not `lazy` parts. Every page draws them, so waiting for a chunk would flash the frame's own first.
- `defineSite` refuses a `header` or `footer` that isn't a component: "The site's header must be a component, such as `header: Header`."
- The frame keeps its skip link first, then the site's header, then `<main id="main">`, then the site's footer. The site's header draws no skip link of its own.
- A header or footer that throws is caught by the kit's `ErrorBoundary`, and the frame's own header or footer is drawn in its place. The page stays up, and the console names the part that failed.
- Where they show: every page in the site frame. That covers the site's and the modules' public and member pages, the kernel's home and member pages (`/account`), and the 404 page, including the one a member gets under `/admin`. The sign-in frame (`AuthFrame`) and the admin frame keep their own.

**`SiteAccountLinks`**, new from `@/kernel`: the frame's account links. Signed out, that's Sign in. Signed in, it's `nav.member`'s links, then Your account, Admin for staff, and Sign out. Sign out keeps its handling of unsaved changes (#82, #83). A site's header wraps it in its own `<nav aria-label="Account">`. `SlotOutlet` (`nav.public`, `site.footer`) and `useSite` (the site's name) are already public. A site's header or footer that leaves a slot out doesn't show that slot's entries; that's the site's call.

**`bleed`** on a route (`ModuleRoute`, for modules and the site alike):

```ts
/** A public or member page drawn edge to edge: the site frame's <main> drops its padding. */
bleed?: boolean;
```

- `defineModule` refuses `bleed` on an admin route: "blog's admin route /admin/blog can't be bleed: the admin frame has its own layout."
- The frame draws `<main id="main" class="mf-bleed">` while a bleed page is open. `frames.css` gains `.mf-site main.mf-bleed { padding: 0 }`; every other page keeps its 1rem.
- The route's element sets it in a layout effect, before paint, as soon as the route matches, so there's no shift while the page's chunk loads. It sits inside the module's switch, so a switched-off module's bleed route is the ordinary, padded 404 page. The page at `/` takes its owner's `bleed`.

**Setup:** `KernelSetup` (`app/context.ts`) gains `frame: { header?: ComponentType; footer?: ComponentType }`, filled by `mountApp({ site })` and by `renderApp({ sitePages })`.

## 3. Data

None.

## 4. Files

- `kernel/web/src/modules.ts`: the types and checks. `app/frames.tsx`: `SiteFrame`, `SiteAccountLinks`, and the bleed state. `app/frames.css`. `app/routes.tsx`: the bleed wrapper. `app/context.ts`, `app/mount.tsx`, `kernel/web/testing.ts`. `kernel/web/index.ts`: export `SiteAccountLinks`.
- Tests: `kernel/web/src/app/frames.test.tsx` (new), `kernel/web/src/modules.test.ts`, and `kernel/tests/e2e/frame.spec.ts` (new) on `harness/web/frame.html` with `harness/web/src/frame.tsx`. That page is like `kit.html`: the app with a site header, footer and a bleed page at `/frame.html`, plus a link to an ordinary page. It's added to `harness/web/vite.config.ts`.
- `templates/site/web/src/site/site.ts`: a comment showing `header`, `footer` and `bleed`. The template keeps the frame's own header and footer.
- Docs: SPEC 8's "The site's own pages" and the change log; decision 0048, amended; `kernel/web/README.md`; `dev plans/README.md`.

## 5. Conventions this follows

`CLAUDE.md`'s Rules (tests first, one PR). SPEC 8's slot rules: tokens only, WCAG 2.2 AA. `SlotOutlet` is the pattern for catching a part that fails. #101 is the pattern for the docs that change with it.

## 6. Non-goals

- No change to the server's copy. A crawler reads a page's words, as now. A site's header and footer words aren't in that copy, just as the frame's links aren't today; `sitemap.xml` and `llms.txt` list the pages. The template's parity test already reads only `main`.
- No header or footer of the site's in the sign-in or admin frames.
- No `Header.tsx` or `Footer.tsx` in the template. A copy there would stop getting the kernel's fixes.
- No per-page header (a page choosing a different one), and no "transparent over the hero" mode. A site's header styles itself.
- No change to `nav.public`, `nav.member` or `site.footer`.

## 7. Acceptance

- `frames.test.tsx`:
  - a site's header and footer replace the frame's on `/`, a module's page, `/account` and the 404 page, and the frame's "Site" navigation is gone;
  - the skip link comes before the site's header;
  - `/sign-in` and `/admin` show no part of the site's;
  - `SiteAccountLinks` gives Sign in when signed out; signed in, it gives the account links and Sign out, which signs out and goes home;
  - a header that throws falls back to the frame's own, and the page's heading still shows;
  - a bleed page's `main` has `mf-bleed`, and moving to an ordinary page drops it;
  - the home owner's `bleed` holds at `/`;
  - a switched-off module's bleed route is the 404 page, without `mf-bleed`.
- `modules.test.ts`: a header that isn't a component is refused; `bleed` on an admin route is refused.
- `frame.spec.ts`, in both themes:
  - the bleed page's first block spans the viewport from x = 0 to its full width;
  - `main`'s computed padding is 0, and 16px after the link to an ordinary page;
  - there's one banner, one main and one contentinfo;
  - the first Tab reaches the skip link, and the next reaches the site's header;
  - axe finds nothing serious or critical.
- The live check: the Vibrant Mindz session moves its homepage to `defineSite({ header, footer })` with `bleed: true`, and deletes `frame.css`'s hiding rules. That's its own job, in its repo.

## 8. Open questions

None. The owner answered all three on 2026-11-21, as recommended:

1. The shape: `header` and `footer` as components given to `defineSite`, drawn on every page in the site frame, with the frame's own as the fallback when one fails.
2. Full bleed per route (`bleed: true`), for modules too.
3. The site's part draws its own `<header>` and `<footer>`, so it can be sticky.

## Changes after approval

- 2026-11-21 (the build): `KernelSetup.frame` is optional (`frame?: SiteFrameParts`, the type in `modules.ts`). Code that builds a setup without it, such as `session.test.tsx`, keeps working, and the frame reads a missing one as none. `siteModule` checks the header and footer too, so `mountApp({ site })` refuses a bad one even when `defineSite` was skipped. `pages.test.tsx` holds both.
