// A play button for one item of a queue (`dev plans/contracts/audio-player.md`
// §2): "Play {label}", or "Pause {label}" while that item plays. The Release
// board's rows and its Play album, and the homepage's "Play Catalyst".
import type { ReactNode } from "react";

import { usePlayer } from "../hooks";
import type { PlayerItem } from "../types";
import { isGoing, PauseIcon, PlayIcon } from "./parts";

import "../player.css";

export type PlayButtonProps = {
  queue: readonly PlayerItem[];
  index?: number;
  /** What it plays, for its name: "01 Gather Around", or the album's title. */
  label: string;
  className?: string;
  /** Its own words or art in place of the icon; its name stays "Play {label}". */
  children?: ReactNode;
};

export function PlayButton({ queue, index = 0, label, className, children }: PlayButtonProps) {
  const player = usePlayer();
  const item = queue[index];
  if (!item) return null;
  const current = player.item?.key === item.key;
  const going = current && isGoing(player.state);
  return (
    <button
      type="button"
      className={className ?? "mf-player-button mf-player-play"}
      aria-label={`${going ? "Pause" : "Play"} ${label}`}
      onClick={() => {
        if (current) player.toggle();
        else player.play(queue, index);
      }}
    >
      {children ?? (going ? <PauseIcon /> : <PlayIcon />)}
    </button>
  );
}
