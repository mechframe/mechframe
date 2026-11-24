// How a track plays until `audio-player` is on (`dev plans/contracts/discography.md`
// §2, Pages): an upload's stream file in the browser's own player, loading nothing
// until it's pressed, and a SoundCloud track as a link to it. Nothing loads from
// SoundCloud.
import type { TrackLine } from "../api";

export function Plays({ track, label }: { track: Pick<TrackLine, "plays_from" | "stream_url" | "soundcloud_url" | "soundcloud_kind">; label: string }) {
  if (track.plays_from === "upload" && track.stream_url) {
    return (
      <audio controls preload="none" src={track.stream_url} aria-label={`Play ${label}`}>
        <a href={track.stream_url}>Listen to {label}</a>
      </audio>
    );
  }
  if (track.soundcloud_url) {
    return (
      <a href={track.soundcloud_url} target="_blank" rel="noreferrer">
        {track.soundcloud_kind === "set" ? "Listen to the full album on SoundCloud" : "Listen on SoundCloud"}
        <span className="mf-visually-hidden"> (opens SoundCloud)</span>
      </a>
    );
  }
  return null;
}
