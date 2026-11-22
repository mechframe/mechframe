// embeds' web binding (SPEC.md section 8; dev plans/contracts/embeds.md): no
// pages of its own, the Embed button in every editor (editor.tools), and the
// player in place of a lone link it recognises in every Prose (prose.embed,
// decision 0060).
import { defineModule } from "@/kernel";

import { recognise } from "./providers";

export default defineModule({
  id: "embeds",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "editor.tools": [{ id: "embed", lazy: () => import("./EmbedButton") }],
    "prose.embed": [{ claims: (href) => recognise(href) !== null, lazy: () => import("./ProsePlayer") }],
  },
});
