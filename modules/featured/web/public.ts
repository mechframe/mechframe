// What a site's own pages (and modules listing featured in `requires`) may import
// from featured's web, as `@/modules/featured/public` (SPEC 7, decision 0057): a
// player's live list through TanStack Query, and its types. The site's homepage and
// Videos page draw their players from it; featured never decides how.
import { LIVE, useApiQuery } from "./api";

export type { Kind, LinkShown, LivePlacement, LiveSlot } from "./api";

/** What's live in the player `key` now, in order: `data.items`, each an item (`ref`) or a YouTube link (`link`). 404 `featured.slot_not_found` while there's no such player. */
export function useFeatured(key: string) {
  return useApiQuery("get", LIVE, { params: { path: { key } } });
}
