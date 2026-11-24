// What a site's own pages (and other modules listing pages in `requires`) may
// import from pages' web, as `@/modules/pages/public` (SPEC 7, decision 0057):
// its page read and its answer's types, so a site's own page at /:address,
// replacing pages', draws pages' live page (`dev plans/contracts/pages.md` §10).
export { isMoved, usePage } from "./reads";
export { day } from "./api";
export type { LivePage, PageMoved } from "./api";
