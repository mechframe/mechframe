// What a site's own pages (and other modules listing discography in `requires`)
// may import from discography's web, as `@/modules/discography/public` (SPEC 7,
// decision 0057): its public reads and their answers' types, so a site's own
// Music and Release pages, replacing discography's at /music and /music/:release,
// draw the library; and its tracks as audio-player's items (0.1.1), so a site's
// homepage builds its Spotlight and deck queues, counting included.
export { isMoved, useArtistLinks, useRelease, useReleases, useTrack } from "./reads";
export { KIND_WORDS, clock, pathOf, releaseLine } from "./api";
export { playerItem, playerQueue } from "./player";
export type { ItemRelease } from "./player";
export type { Kind, LiveRelease, LiveTrack, MusicCover, MusicCredit, MusicLink, MusicMoved, ReleaseCard, ReleaseCards, TrackLine } from "./api";
