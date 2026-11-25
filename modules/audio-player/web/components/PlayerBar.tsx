// The bar inline in a page (`dev plans/contracts/audio-player.md` §2), as the
// homepage's Spotlight draws it: a region named by `label`, the cover, the title
// and its line, Previous, Play and Next, and the waveform; `children` at its end
// ("Full album"). Until its queue plays, Previous and Next move through it and
// Play starts the one shown; once it plays, they drive the player.
import { useState, type ReactNode } from "react";

import { isQueue, usePlayer } from "../hooks";
import type { PlayerItem } from "../types";
import { Cover, Credit, isGoing, Note, Transport } from "./parts";
import { Waveform } from "./Waveform";

import "../player.css";

export type PlayerBarProps = {
  queue: readonly PlayerItem[];
  /** The region's name: "Spotlight single". */
  label: string;
  previousLabel?: string | undefined;
  nextLabel?: string | undefined;
  /** How many bars the waveform draws. */
  bars?: number | undefined;
  children?: ReactNode;
};

export function PlayerBar({ queue, label, previousLabel, nextLabel, bars, children }: PlayerBarProps) {
  const player = usePlayer();
  const [shown, setShown] = useState(0);
  const mine = queue.length > 0 && isQueue(player, queue);
  const count = queue.length;
  const at = mine ? player.index : Math.min(shown, count - 1);
  const item = queue[at];
  if (!item) return null;
  const going = mine && isGoing(player.state);
  const move = (step: 1 | -1) => {
    if (mine) {
      if (step === 1) player.next();
      else player.prev();
    } else setShown((at + step + count) % count);
  };
  return (
    <section className="mf-player-bar" aria-label={label}>
      <Cover item={item} size={52} />
      <div className="mf-player-words">
        <p className="mf-player-title">{item.title}</p>
        <p className="mf-player-line">
          {item.line} <Credit item={item} />
        </p>
        {mine ? <Note state={player.state} /> : null}
      </div>
      <Waveform item={item} bars={bars} />
      <Transport
        item={item}
        going={going}
        count={count}
        previousLabel={previousLabel}
        nextLabel={nextLabel}
        onPrevious={() => { move(-1); }}
        onNext={() => { move(1); }}
        onPlay={() => {
          if (mine) player.toggle();
          else player.play(queue, at);
        }}
      />
      {children}
    </section>
  );
}
