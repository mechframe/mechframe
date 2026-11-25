// The parts the bar and the dock share (`dev plans/contracts/audio-player.md` §2):
// the transport's icons and buttons, the SoundCloud credit, the note under a
// track that can't play, and the seek slider's keys. The kit's Icon has no
// pause or skip, so these are drawn here, in the text's colour.
import type { KeyboardEvent, ReactNode } from "react";

import type { PlayerControls } from "../hooks";
import { clock, viaSoundCloud, type PlayerItem } from "../types";

function Svg({ children }: { children: ReactNode }) {
  return (
    <svg className="mf-player-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

export function PlayIcon() {
  return (
    <Svg>
      <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
    </Svg>
  );
}

export function PauseIcon() {
  return (
    <Svg>
      <rect x="6.5" y="5" width="4" height="14" rx="1" fill="currentColor" />
      <rect x="13.5" y="5" width="4" height="14" rx="1" fill="currentColor" />
    </Svg>
  );
}

export function PreviousIcon() {
  return (
    <Svg>
      <rect x="5.5" y="6" width="2.5" height="12" rx="1" fill="currentColor" />
      <path d="M18.5 6v12L9 12z" fill="currentColor" />
    </Svg>
  );
}

export function NextIcon() {
  return (
    <Svg>
      <rect x="16" y="6" width="2.5" height="12" rx="1" fill="currentColor" />
      <path d="M5.5 6v12L15 12z" fill="currentColor" />
    </Svg>
  );
}

export function QueueIcon() {
  return (
    <Svg>
      <path d="M4 7h11M4 12h11M4 17h7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
      <path d="M17 14.5v5l4-2.5z" fill="currentColor" />
    </Svg>
  );
}

export function VolumeIcon() {
  return (
    <Svg>
      <path d="M4 9.5h3.5L12 6v12l-4.5-3.5H4z" fill="currentColor" />
      <path d="M15 9a4 4 0 0 1 0 6M17.5 6.5a7.5 7.5 0 0 1 0 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none" />
    </Svg>
  );
}

/** Playing, or about to: what Pause is shown for. */
export function isGoing(state: PlayerControls["state"]): boolean {
  return state === "playing" || state === "loading" || state === "blocked";
}

/** SoundCloud's terms ask for a credit and a link back when its widget is hidden (§8, 5). */
export function Credit({ item }: { item: PlayerItem }) {
  if (!viaSoundCloud(item) || !item.soundcloud_url) return null;
  return (
    <a className="mf-player-credit" href={item.soundcloud_url} target="_blank" rel="noreferrer" aria-label="on SoundCloud (opens SoundCloud)">
      on SoundCloud
    </a>
  );
}

export function Note({ state }: { state: PlayerControls["state"] }) {
  if (state === "failed") return <p className="mf-player-note">This track can&rsquo;t play right now.</p>;
  if (state === "blocked") return <p className="mf-player-note">Press Play in SoundCloud&rsquo;s player to start it.</p>;
  return null;
}

export function Cover({ item, size }: { item: PlayerItem; size: number }) {
  if (!item.cover) return <span className="mf-player-cover mf-player-cover-none" style={{ width: size, height: size }} aria-hidden="true" />;
  return <img className="mf-player-cover" src={item.cover.src} alt="" width={size} height={size} loading="lazy" />;
}

/** How far a seek key moves. */
export const SEEK_STEP_MS = 5000;

/** The slider's keys and words, for the item playing now. */
export function seekProps(player: PlayerControls, label = "Seek") {
  const length = player.duration_ms ?? 0;
  const at = Math.min(player.position_ms, length || player.position_ms);
  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const moves: Record<string, number> = {
      ArrowRight: at + SEEK_STEP_MS,
      ArrowUp: at + SEEK_STEP_MS,
      ArrowLeft: at - SEEK_STEP_MS,
      ArrowDown: at - SEEK_STEP_MS,
      Home: 0,
      End: length,
    };
    const to = moves[event.key];
    if (to === undefined) return;
    event.preventDefault();
    player.seek(to);
  };
  return {
    role: "slider" as const,
    tabIndex: 0,
    "aria-label": label,
    "aria-valuemin": 0,
    "aria-valuemax": Math.round(length / 1000),
    "aria-valuenow": Math.round(at / 1000),
    "aria-valuetext": length ? `${clock(at)} of ${clock(length)}` : clock(at),
    onKeyDown,
  };
}

/** Where a press along `element` lands, as a time in the item playing now. */
export function pressedAt(element: HTMLElement, clientX: number, length: number): number {
  const box = element.getBoundingClientRect();
  if (!box.width) return 0;
  return Math.min(1, Math.max(0, (clientX - box.left) / box.width)) * length;
}

type TransportProps = {
  item: PlayerItem;
  going: boolean;
  onPrevious: () => void;
  onPlay: () => void;
  onNext: () => void;
  previousLabel?: string | undefined;
  nextLabel?: string | undefined;
  /** How many items the queue has: one has no Previous or Next. */
  count: number;
};

export function Transport({ item, going, onPrevious, onPlay, onNext, previousLabel = "Previous track", nextLabel = "Next track", count }: TransportProps) {
  return (
    <div className="mf-player-transport" role="group" aria-label="Playback">
      {count > 1 ? (
        <button type="button" className="mf-player-button" aria-label={previousLabel} onClick={onPrevious}>
          <PreviousIcon />
        </button>
      ) : null}
      <button type="button" className="mf-player-button mf-player-play" aria-label={`${going ? "Pause" : "Play"} ${item.title}`} onClick={onPlay}>
        {going ? <PauseIcon /> : <PlayIcon />}
      </button>
      {count > 1 ? (
        <button type="button" className="mf-player-button" aria-label={nextLabel} onClick={onNext}>
          <NextIcon />
        </button>
      ) : null}
    </div>
  );
}
