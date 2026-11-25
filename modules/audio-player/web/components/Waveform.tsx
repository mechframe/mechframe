// The waveform (`dev plans/contracts/audio-player.md` §2), as the Spotlight
// draws it: bars 4 wide on a 7 step, the unplayed layer under the played one,
// which is clipped to how far the item has played. For the item playing now
// it's a slider ("Seek"); for any other it's only a picture.
import { useId, type PointerEvent } from "react";

import { usePlayer } from "../hooks";
import type { PlayerItem } from "../types";
import { pressedAt, seekProps } from "./parts";

import "../player.css";

const STEP = 7;
const WIDTH = 4;
const HEIGHT = 96;
const LOWEST = 0.06;

/** A number from a string, the same each time (FNV-1a). */
function hashOf(text: string): number {
  let hash = 0x811c9dc5;
  for (let at = 0; at < text.length; at += 1) {
    hash ^= text.charCodeAt(at);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/** Each bar's height from 0 to 1: the loudest peak in its slice, or a made-up shape for `key`. */
export function barsOf(peaks: readonly number[] | undefined, key: string, count: number): number[] {
  if (peaks?.length) {
    const slice = peaks.length / count;
    return Array.from({ length: count }, (_, at) => {
      const from = Math.floor(at * slice);
      const to = Math.max(from + 1, Math.floor((at + 1) * slice));
      const loudest = Math.max(...peaks.slice(from, to));
      return Math.max(LOWEST, loudest / 255);
    });
  }
  let seed = hashOf(key) || 1;
  const random = () => {
    // xorshift32: enough to look like music, and the same for the same key.
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return (seed >>> 0) / 0xffffffff;
  };
  const phase = random() * Math.PI * 2;
  return Array.from({ length: count }, (_, at) => {
    const swell = 0.55 + 0.35 * Math.sin(at / 11 + phase);
    return Math.max(LOWEST, Math.min(1, swell * (0.45 + 0.55 * random())));
  });
}

export type WaveformProps = { item: PlayerItem; bars?: number | undefined };

export function Waveform({ item, bars = 150 }: WaveformProps) {
  const player = usePlayer();
  const clip = useId();
  const heights = barsOf(item.peaks, item.key, bars);
  const current = player.item?.key === item.key;
  const length = current ? (player.duration_ms ?? 0) : 0;
  const progress = current && length ? Math.min(1, player.position_ms / length) : 0;
  const width = bars * STEP;
  const rects = heights.map((height, at) => {
    const tall = Math.round(height * HEIGHT);
    return <rect key={at} x={at * STEP} y={(HEIGHT - tall) / 2} width={WIDTH} height={tall} rx={2} />;
  });
  const picture = (
    <svg className="mf-wave-picture" viewBox={`0 0 ${String(width)} ${String(HEIGHT)}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <defs>
        <clipPath id={clip}>
          <rect x={0} y={0} width={progress * width} height={HEIGHT} />
        </clipPath>
      </defs>
      <g className="mf-wave-rest">{rects}</g>
      <g className="mf-wave-done" clipPath={`url(#${clip})`}>
        {rects}
      </g>
    </svg>
  );
  if (!current || !length) return <div className="mf-wave">{picture}</div>;
  const press = (event: PointerEvent<HTMLDivElement>) => {
    player.seek(pressedAt(event.currentTarget, event.clientX, length));
  };
  return (
    <div className="mf-wave mf-wave-live" {...seekProps(player)} onPointerDown={press}>
      {picture}
    </div>
  );
}
