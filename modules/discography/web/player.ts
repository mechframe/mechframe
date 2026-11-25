// discography's tracks as audio-player's items (`dev plans/contracts/audio-player.md`
// §2, "discography 0.1.1"): what the Release and Track pages hand the player, and
// what a site's homepage builds its Spotlight and deck queues from (`public.ts`).
// An item counts its play through discography's own route, which checks the track.
import type { PlayerItem } from "@/modules/audio-player/public";

import { api, type LiveRelease, type ReleaseCard, type TrackLine } from "./api";

/** audio-player's source for a track: an item's key is `discography.track:<id>`. */
export const SOURCE = "discography.track";

/** What a track's line under its title names: the release and who made it. */
export type ItemRelease = Pick<ReleaseCard, "title" | "artist_line" | "cover">;

/** Tells the site the track was heard long enough. Nothing is said back, and a failure is let go. */
export function countPlay(trackId: string): void {
  api.POST("/api/discography/tracks/{track_id}/plays", { params: { path: { track_id: trackId } } }).catch(() => undefined);
}

/**
 * A track that plays, as the player's item: its stream file once one is made,
 * else its SoundCloud link; its line "Catalyst, petro and J Tone"; the release's
 * cover; its peaks when the answer has them (a track's own page); and `count`.
 */
export function playerItem(track: TrackLine & { peaks?: readonly number[] | null }, release: ItemRelease): PlayerItem {
  const line = [release.title, release.artist_line].filter(Boolean).join(", ");
  const stream = track.plays_from === "upload" ? track.stream_url : null;
  return {
    key: `${SOURCE}:${track.id}`,
    title: track.title,
    line,
    ...(release.cover ? { cover: { src: release.cover.url, alt: release.cover.decorative ? "" : (release.cover.alt ?? "") } } : {}),
    ...(stream ? { stream_url: stream } : track.soundcloud_url ? { soundcloud_url: track.soundcloud_url } : {}),
    ...(track.duration_ms ? { duration_ms: track.duration_ms } : {}),
    ...(track.peaks?.length ? { peaks: track.peaks } : {}),
    path: track.path,
    count: () => {
      countPlay(track.id);
    },
  };
}

/** A live release's tracks that play, in order: the queue its Play album and dock start. */
export function playerQueue(release: LiveRelease): PlayerItem[] {
  return release.tracks.map((track) => playerItem(track, release));
}
