// social's web binding (SPEC.md section 8; dev plans/contracts/social.md): the Share
// card every admin page that draws `ShareParts` gets (`content.share`, decision 0067),
// and the "Social" section of Settings, the Buffer token's.
import { defineModule } from "@/kernel";

import { SEND_PERMISSION } from "./api";

export default defineModule({
  id: "social",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "content.share": [{ id: "buffer", lazy: () => import("./SharePanel"), permission: SEND_PERMISSION }],
    "admin.settings.section": [
      { id: "social", title: "Social", lazy: () => import("./SocialSettings"), permission: "kernel.settings.manage" },
    ],
  },
});
