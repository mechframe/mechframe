// What a site's own pages (and other modules listing discography in `requires`)
// may import from discography's web, as `@/modules/discography/public` (SPEC 7,
// decision 0057): its public reads and their answers' types, so a site's own
// Music and Release pages, replacing discography's at /music and /music/:release,
// draw the library.
export { isMoved, useArtistLinks, useRelease, useReleases, useTrack } from "./reads";
export { KIND_WORDS, clock, pathOf, releaseLine } from "./api";
export type { Kind, LiveRelease, LiveTrack, MusicCover, MusicCredit, MusicLink, MusicMoved, ReleaseCard, ReleaseCards, TrackLine } from "./api";
