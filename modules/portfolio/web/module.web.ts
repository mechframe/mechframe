// portfolio's web binding (SPEC.md section 8; dev plans/contracts/portfolio.md): the
// Art page at /art, a discipline at /art/:discipline and a piece at
// /art/piece/:slug (one page, the panel open at a piece's address), Portfolio
// under Collective in the sidebar for anyone who may add pieces, Art in the
// site's header, and the "Art page" section of Settings.
import { defineModule } from "@/kernel";

import { ADD } from "./api";

export default defineModule({
  id: "portfolio",
  routes: {
    public: [
      { path: "/art", lazy: () => import("./pages/Art") },
      { path: "/art/:discipline", lazy: () => import("./pages/Art") },
      { path: "/art/piece/:slug", lazy: () => import("./pages/Art") },
    ],
    member: [],
    admin: [
      { path: "/admin/portfolio", lazy: () => import("./pages/PortfolioAdmin"), permission: ADD },
      // A piece in the editor has an address of its own, so the kit's guard asks before another replaces it.
      { path: "/admin/portfolio/:id", lazy: () => import("./pages/PortfolioAdmin"), permission: ADD },
    ],
  },
  slots: {
    "nav.public": [{ label: "Art", to: "/art" }],
    "nav.admin": [{ label: "Portfolio", to: "/admin/portfolio", section: "Collective", icon: "people", permission: ADD }],
    "admin.settings.section": [{ id: "portfolio", title: "Art page", lazy: () => import("./pages/ArtSettings") }],
  },
});
