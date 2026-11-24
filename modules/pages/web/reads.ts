// pages' public read as a hook (`dev plans/contracts/pages.md` §2 and §10): one
// live page, or where an address it left moved. pages' own PublicPage reads
// through it, and so does a site's own page that replaces it (`public.ts`,
// decision 0057).
import { useApiQuery, type LivePage, type PageMoved } from "./api";

/**
 * The live page at `address` (`/about`, or `about` as a route's parameter gives
 * it), or where it is now (`isMoved`); any other address is an ApiProblem, 404
 * `pages.page_not_found`.
 */
export function usePage(address: string) {
  const path = address.startsWith("/") ? address : `/${address}`;
  return useApiQuery("get", "/api/pages/page", { params: { query: { address: path } } });
}

/** Whether `found` is an address a live page left, to go on to `found.moved`. */
export function isMoved(found: LivePage | PageMoved): found is PageMoved {
  return "moved" in found;
}
