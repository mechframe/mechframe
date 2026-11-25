// The bar docked at the window's foot (`dev plans/contracts/audio-player.md`
// §2), as the Release board draws it; a page draws it in `<AfterFooter>`. It
// shows what the player plays on this page, or its own queue's first until
// something does: the cover, the title and line, Previous, Play and Next, a thin
// progress slider, "Track 2 of 15", the queue and the volume. Under 700px the
// progress, Queue and Volume hide, as on the board.
import { useEffect, useId, useRef, useState, type PointerEvent } from "react";

import { usePlayer } from "../hooks";
import type { PlayerItem } from "../types";
import { Cover, Credit, isGoing, Note, pressedAt, QueueIcon, seekProps, Transport, VolumeIcon } from "./parts";
import { Equalizer } from "./Equalizer";

import "../player.css";

export type PlayerDockProps = {
  /** What it starts when nothing plays yet: the release's playable tracks. */
  queue: readonly PlayerItem[];
  /** The region's name: "Player". */
  label: string;
};

type Open = "queue" | "volume" | null;

export function PlayerDock({ queue, label }: PlayerDockProps) {
  const player = usePlayer();
  const [open, setOpen] = useState<Open>(null);
  const ids = { queue: useId(), volume: useId() };
  const triggers = { queue: useRef<HTMLButtonElement>(null), volume: useRef<HTMLButtonElement>(null) };
  const panelRef = useRef<HTMLElement | null>(null);
  const active = player.queue.length > 0;
  const list = active ? player.queue : queue;
  const at = active ? player.index : 0;
  const item = list[at];
  const { queue: queueButton, volume: volumeButton } = triggers;
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // Focus in the panel goes back to its button, or the keyboard loses its place (CodeRabbit on #149).
      const held = panelRef.current?.contains(document.activeElement) ?? false;
      setOpen(null);
      if (held) (open === "queue" ? queueButton : volumeButton).current?.focus();
    };
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("keydown", close);
    };
  }, [open, queueButton, volumeButton]);
  if (!item) return null;
  const going = active && isGoing(player.state);
  const length = active ? (player.duration_ms ?? 0) : 0;
  const progress = length ? Math.min(1, player.position_ms / length) : 0;
  const start = (index: number) => {
    if (active) player.play(player.queue, index);
    else player.play(queue, index);
  };
  const press = (event: PointerEvent<HTMLDivElement>) => {
    if (length) player.seek(pressedAt(event.currentTarget, event.clientX, length));
  };
  const toggle = (which: Exclude<Open, null>) => {
    setOpen((now) => (now === which ? null : which));
  };
  return (
    <section className="mf-player-dock" aria-label={label}>
      <Cover item={item} size={52} />
      <div className="mf-player-words">
        <p className="mf-player-title">{item.title}</p>
        <p className="mf-player-line">
          {item.line} <Credit item={item} />
        </p>
        {active ? <Note state={player.state} /> : null}
      </div>
      <Transport
        item={item}
        going={going}
        count={list.length}
        onPrevious={() => { if (active) player.prev(); }}
        onNext={() => {
          if (active) player.next();
          else start(Math.min(1, queue.length - 1));
        }}
        onPlay={() => {
          if (active) player.toggle();
          else start(0);
        }}
      />
      <div className="mf-player-progress-box mf-player-wide">
        {length ? (
          <div className="mf-player-progress" {...seekProps(player)} onPointerDown={press}>
            <span className="mf-player-progress-done" style={{ transform: `scaleX(${String(progress)})` }} />
          </div>
        ) : (
          <div className="mf-player-progress" aria-hidden="true" />
        )}
        <p className="mf-player-count">
          Track {at + 1} of {list.length}
        </p>
      </div>
      <div className="mf-player-extra mf-player-wide">
        <button
          type="button"
          className="mf-player-button"
          aria-label="Queue"
          aria-expanded={open === "queue"}
          ref={queueButton}
          aria-controls={ids.queue}
          onClick={() => { toggle("queue"); }}
        >
          <QueueIcon />
        </button>
        <button
          type="button"
          className="mf-player-button"
          aria-label="Volume"
          aria-expanded={open === "volume"}
          ref={volumeButton}
          aria-controls={ids.volume}
          onClick={() => { toggle("volume"); }}
        >
          <VolumeIcon />
        </button>
        {open === "queue" ? (
          <ol
            ref={(node) => {
              panelRef.current = node;
            }}
            id={ids.queue}
            className="mf-player-popover mf-player-queue"
            aria-label="Queue"
          >
            {list.map((each, index) => {
              const here = active && index === at;
              return (
                <li key={each.key}>
                  <button
                    type="button"
                    className="mf-player-queue-row"
                    aria-label={`Play ${each.title}`}
                    aria-current={here ? "true" : undefined}
                    onClick={() => { start(index); }}
                  >
                    {each.title}
                    {here ? <Equalizer playing={going} /> : null}
                  </button>
                </li>
              );
            })}
          </ol>
        ) : null}
        {open === "volume" ? (
          <div
            ref={(node) => {
              panelRef.current = node;
            }}
            id={ids.volume}
            className="mf-player-popover mf-player-volume"
          >
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              aria-label="Volume"
              value={Math.round(player.volume * 100)}
              onChange={(event) => { player.setVolume(Number(event.target.value) / 100); }}
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}
