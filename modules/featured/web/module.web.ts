// featured's web binding (SPEC.md section 8; dev plans/contracts/featured.md): Players
// at /admin/featured under the sidebar's Homepage, and the Dashboard's "Now in the
// spotlight" card for each player marked to show there. The site's own pages draw
// the players, from `public.ts`'s `useFeatured`.
import { defineModule } from "@/kernel";

import { PLACE } from "./api";

export default defineModule({
  id: "featured",
  routes: {
    public: [],
    member: [],
    admin: [{ path: "/admin/featured", lazy: () => import("./pages/Players"), permission: PLACE }],
  },
  slots: {
    "nav.admin": [{ label: "Players", to: "/admin/featured", section: "Homepage", icon: "home", permission: PLACE }],
    "admin.dashboard.widget": [{ lazy: () => import("./widgets/SpotlightCard"), permission: PLACE }],
  },
});
