// What a site's own code, and a module that lists embeds in requires.modules,
// may use as `@/modules/embeds/public` (SPEC 7, decision 0057): the reading of
// a link, the player for one, its frame alone behind a page's own facade
// (0.1.2), and the YouTube playlist player.
export { Embed, EmbedFrame } from "./Embed";
export type { EmbedFrameProps, EmbedProps } from "./Embed";
export { recognise, wordsFor, youtubeId } from "./providers";
export type { Embed as RecognisedEmbed } from "./providers";
export { VideoPlaylist } from "./VideoPlaylist";
export type { PlaylistItem, VideoPlaylistHandle, VideoPlaylistProps } from "./VideoPlaylist";
