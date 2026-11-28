// reactions' web binding (SPEC.md section 8; dev plans/contracts/reactions.md): the row
// of reactions every public page that draws `ReactionParts` gets under its thing
// (`content.reactions`, decision 0068). No pages of its own.
import { defineModule } from "@/kernel";

export default defineModule({
  id: "reactions",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "content.reactions": [{ id: "row", lazy: () => import("./ReactionRow") }],
  },
});
