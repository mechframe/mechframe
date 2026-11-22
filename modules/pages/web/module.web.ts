// pages' web binding (SPEC.md section 8; dev plans/contracts/pages.md): each
// live page at its address, the list and the editor under Content in the
// sidebar, and the header's and footer's menus loaded from the module's API
// (decision 0056). `/:address` is the least fixed route there is, so any other
// route that meets an address wins it.
import { defineModule } from "@/kernel";

import { menu } from "./api";

export default defineModule({
  id: "pages",
  routes: {
    public: [{ path: "/:address", lazy: () => import("./pages/PublicPage") }],
    member: [],
    admin: [
      { path: "/admin/pages", lazy: () => import("./pages/AdminPages"), permission: "pages.page.write" },
      { path: "/admin/pages/:id", lazy: () => import("./pages/AdminPage"), permission: "pages.page.write" },
    ],
  },
  slots: {
    "nav.admin": [{ label: "Pages", to: "/admin/pages", section: "Content", icon: "document", permission: "pages.page.write" }],
  },
  links: {
    "nav.public": () => menu("header"),
    "nav.footer": () => menu("footer"),
  },
});
