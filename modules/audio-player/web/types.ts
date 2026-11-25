// What a module hands the player (`dev plans/contracts/audio-player.md` §2).

export type PlayerItem = {
  /** "<source>:<id>", unique in a queue. */
  key: string;
  title: string;
  /** The words under the title: "Catalyst, petro and J Tone". */
  line: string;
  cover?: { src: string; alt: string };
  /** A file the browser plays; else */
  stream_url?: string;
  /** a SoundCloud track or playlist. */
  soundcloud_url?: string;
  duration_ms?: number;
  /** 0 to 255; without them, a made-up shape that's always the same for its key. */
  peaks?: readonly number[];
  /** Its page. */
  path?: string;
  /** Called once, when it's been heard long enough. */
  count?: () => void;
};

export type PlayerState = "idle" | "loading" | "playing" | "paused" | "failed" | "blocked";

export type PlayerSettings = { autoplay_next: boolean; count_after_seconds: number };

export const DEFAULT_SETTINGS: PlayerSettings = { autoplay_next: true, count_after_seconds: 30 };

/** Whether it plays through SoundCloud's widget. */
export function viaSoundCloud(item: PlayerItem | null | undefined): boolean {
  return Boolean(item && !item.stream_url && item.soundcloud_url);
}

/** "1:12", or "1:02:05" past an hour. */
export function clock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = String(total % 60).padStart(2, "0");
  return hours ? `${String(hours)}:${String(minutes).padStart(2, "0")}:${secs}` : `${String(minutes)}:${secs}`;
}
