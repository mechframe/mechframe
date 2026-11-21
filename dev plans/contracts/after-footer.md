---
feature: A page draws something after the site frame's footer (VM Website's "For MechFrame" item 6)
status: built to the owner's goal; the interfaces are the agent's call (knowledge decision 0008, point 3), told to the owner in the PR
goal: the owner, 2026-11-21 (Release's docked player stays under the footer, as drawn; VM Website `dev plans/2026-11-21-release-dock.jpg`)
plan: VM Website docs/HANDOFF.md "For MechFrame" item 6; SPEC 8; decision 0048; `site-frame.md` (#106), which this extends
pr: 113 (predicted at push time)
---

# Contract: after the site's footer

## 1. Goal

A page can draw a part after the site frame's footer, inside `.mf-site`, the box that spans the header, `<main>` and the footer. Vibrant Mindz's Release page docks its player there: `position: sticky; bottom: 0`, it rides the window's foot all down the page and settles below the footer at the end. Since #106 a page draws only inside `<main>`, where the same bar would settle above the footer. The site then drops `frame.css`'s stopgap.

## 2. Interfaces

**`AfterFooter`**, new from `@/kernel` (`kernel/web/src/app/frames.tsx`):

```tsx
/** Draws its children after the site frame's footer while the page that renders it is open. */
export function AfterFooter({ children }: { children: ReactNode }): ReactNode;
```

- `SiteFrame` draws `<div class="mf-after-footer">` last in `.mf-site`, after the footer, the site's or its own. `AfterFooter` is a React portal into it, so its children stay in the page's tree: its context, its events and its error boundary. A part there that throws is the page's error, as anywhere else on it.
- `frames.css` gains `.mf-after-footer { display: contents }`. The holder makes no box, so what's drawn in it lays out as a child of `.mf-site`: a sticky bar sticks over the whole page, not only over its own height.
- What the open page draws there goes when the page closes. Two on one page are drawn in the order they render.
- Outside the site frame (the sign-in and admin frames) it draws nothing.
- It's outside `<main>`, so the part brings its own landmark: a `<section aria-label>` or `role="region"` with a name, as Release's `aria-label="Player"`. axe's `region` rule holds the page to that. It follows the footer in the tab order, as on the board.

## 3. Data

None.

## 4. Files

- `kernel/web/src/app/frames.tsx`: `AfterFooter`, the holder and its context. `app/frames.css`. `kernel/web/index.ts`: the export.
- Tests: `kernel/web/src/app/frames.test.tsx`; `kernel/tests/e2e/frame.spec.ts` on a third page of `harness/web/src/frame.tsx`, `/frame-docked`, reached by a link from `/frame.html`: a long page with a sticky bar after the footer (`harness/web/src/frame.css`).
- Docs: SPEC 8's "The site's own pages" and the change log; decision 0048, amended; `kernel/web/README.md`; `dev plans/README.md`.

## 5. Conventions this follows

`site-frame.md` (#106) and its tests; `CLAUDE.md`'s Rules (tests first, one PR); SPEC 8: tokens only, WCAG 2.2 AA.

## 6. Non-goals

- No slot in `kernel.json` or `slots/types.ts`: the part belongs to the open page, not to every page as `site.footer` does.
- No sticky style of the kernel's: the site styles its bar.
- No change to the server's copy: a crawler reads `<main>`'s words, as now.
- Nothing after the sign-in or admin frames' content.

## 7. Acceptance

- `frames.test.tsx`:
  - a page's part is drawn after the site's footer, inside `.mf-site` and outside `<main>`, and after the frame's own footer when the site gives none;
  - moving to another page clears it, and coming back draws it again;
  - two parts on one page keep their order;
  - an admin page's part draws nothing.
- `frame.spec.ts`, in both themes, on `/frame-docked`:
  - at the top of the long page, the bar's bottom is the window's bottom;
  - scrolled to the end, the bar's top is at or below the footer's bottom;
  - one main, one contentinfo, and the bar's region "Player";
  - going back to `/frame.html` leaves no bar;
  - axe finds nothing serious or critical.
- The live check: the Vibrant Mindz session moves Release's player into `AfterFooter` and drops `frame.css`'s stopgap, in its repo.

## Changes after approval

None yet.
