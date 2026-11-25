// A release's tracks in audio-player's parts (`dev plans/contracts/audio-player.md`
// §2, "discography 0.1.1"; the Release board): Play album, each row's play and the
// three bars by the row that plays, and the bar docked at the window's foot. Drawn
// only while audio-player is on; else a page keeps `Plays`, the browser's own.
import { AfterFooter } from "@/kernel";
import { Equalizer, PlayButton, PlayerDock, usePlayer, type PlayerItem } from "@/modules/audio-player/public";

/** Whether the player holds `queue`, the same items in the same order. */
function holds(playing: readonly PlayerItem[], queue: readonly PlayerItem[]): boolean {
  return playing.length === queue.length && playing.every((item, at) => item.key === queue[at]?.key);
}

function going(state: ReturnType<typeof usePlayer>["state"]): boolean {
  return state === "playing" || state === "loading" || state === "blocked";
}

/**
 * "Play album", or "Pause album" while any of it plays: once the album is the
 * player's queue, it pauses or resumes the track it's on; else it starts the first.
 */
export function PlayAlbum({ queue }: { queue: readonly PlayerItem[] }) {
  const player = usePlayer();
  const mine = holds(player.queue, queue);
  const on = mine && going(player.state);
  return (
    <PlayButton queue={queue} index={mine ? player.index : 0} label="album" className="mf-music-play">
      {on ? "Pause album" : "Play album"}
    </PlayButton>
  );
}

/** A row's play, "Play 01 Gather Around", and the bars beside the row the player is on. */
export function PlayTrack({ queue, index, label }: { queue: readonly PlayerItem[]; index: number; label: string }) {
  const player = usePlayer();
  const current = player.item?.key === queue[index]?.key;
  return (
    <>
      <PlayButton queue={queue} index={index} label={label} className="mf-player-button" />
      {current ? <Equalizer playing={going(player.state)} /> : null}
    </>
  );
}

/** The Release board's docked bar, "Player", after the site's footer. */
export function ReleaseDock({ queue }: { queue: readonly PlayerItem[] }) {
  if (queue.length === 0) return null;
  return (
    <AfterFooter>
      <PlayerDock queue={queue} label="Player" />
    </AfterFooter>
  );
}
