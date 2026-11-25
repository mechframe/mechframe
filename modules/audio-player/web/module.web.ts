// audio-player's web binding (SPEC.md section 8; dev plans/contracts/audio-player.md):
// no pages of its own, only the "Player" section of Settings. The player itself
// is what modules and a site's own pages draw from `public.ts`.
import { defineModule } from "@/kernel";

export default defineModule({
  id: "audio-player",
  routes: {
    public: [],
    member: [],
    admin: [],
  },
  slots: {
    "admin.settings.section": [{ id: "audio-player", title: "Player", lazy: () => import("./components/SettingsSection") }],
  },
});
