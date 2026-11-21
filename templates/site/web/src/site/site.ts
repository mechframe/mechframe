/**
 * This site's own pages and the slots it fills (decision 0048). They're always
 * on, with no switch on Features, and win a tie with a module's route.
 *
 * Each public page here has its server copy in `backend/app/site/pages.py`,
 * with the same words, so a crawler that runs no script reads what a person
 * sees: add both together. Member pages sit behind sign-in.
 *
 * The site frame draws the kernel's header and footer until the site gives
 * its own: `header: Header, footer: Footer`, components whose root is a
 * `<header>` or a `<footer>`. Build the header from `SiteAccountLinks`,
 * `SlotOutlet` (`nav.public`) and `useSite`, and put `SlotOutlet` for
 * `site.footer` in the footer, so the modules' links still show. A page that
 * runs edge to edge says `bleed: true` beside its path (SPEC 8).
 */
import { defineSite } from "@/kernel";

export const site = defineSite({
  routes: {
    public: [{ path: "/", lazy: () => import("./Home") }],
    member: [],
  },
});
