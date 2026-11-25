// discography's web binding (SPEC.md section 8; dev plans/contracts/discography.md):
// the library at /music, each live release at /music/:release and each track that
// plays at /music/:release/:track; Albums, Tracks and Credits under Music in the
// sidebar, in the boards' order, with the album editor; Music in the header; and
// the Dashboard's "Plays this week" (0.1.1).
import { defineModule } from "@/kernel";

import { MANAGE } from "./api";

export default defineModule({
  id: "discography",
  routes: {
    public: [
      { path: "/music", lazy: () => import("./pages/Music") },
      { path: "/music/:release", lazy: () => import("./pages/Release") },
      { path: "/music/:release/:track", lazy: () => import("./pages/Track") },
    ],
    member: [],
    admin: [
      { path: "/admin/music", lazy: () => import("./pages/AdminMusic"), permission: MANAGE },
      { path: "/admin/music/tracks", lazy: () => import("./pages/AdminTracks"), permission: MANAGE },
      { path: "/admin/music/credits", lazy: () => import("./pages/AdminCredits"), permission: MANAGE },
      { path: "/admin/music/:id", lazy: () => import("./pages/AdminRelease"), permission: MANAGE },
    ],
  },
  slots: {
    "nav.public": [{ label: "Music", to: "/music" }],
    "nav.admin": [
      { label: "Albums", to: "/admin/music", section: "Music", icon: "music", permission: MANAGE },
      { label: "Tracks", to: "/admin/music/tracks", section: "Music", icon: "music", permission: MANAGE },
      { label: "Credits", to: "/admin/music/credits", section: "Music", icon: "music", permission: MANAGE },
    ],
    "admin.dashboard.widget": [{ lazy: () => import("./widgets/PlaysCard"), permission: MANAGE }],
  },
});
