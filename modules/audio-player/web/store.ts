/**
 * The one player (`dev plans/contracts/audio-player.md` §2, "How the player
 * behaves"). It holds the queue, plays through one of its two outputs, pauses
 * every other player as it starts, counts a play once it's really been heard,
 * and stops once no part of the page that started it is left.
 *
 * It isn't React: the hooks read it with `useSyncExternalStore`. There's one for
 * the app (`thePlayer`); tests make their own with fake outputs.
 */
import { fileOutput, soundcloudOutput, type Output, type OutputEvents, type OutputFactory } from "./outputs";
import { DEFAULT_SETTINGS, viaSoundCloud, type PlayerItem, type PlayerSettings, type PlayerState } from "./types";

export type Snapshot = {
  readonly queue: readonly PlayerItem[];
  readonly index: number;
  readonly item: PlayerItem | null;
  readonly state: PlayerState;
  readonly position_ms: number;
  readonly duration_ms: number | null;
  readonly volume: number;
  /** The page that started it, which must stay open for it to keep playing. */
  readonly page: string | null;
};

/** Another kind of player, such as embeds' YouTube one, that takes turns with this one. */
export type Exclusive = {
  /** Call as the other player starts: this one pauses, and so does every other. */
  claim: () => void;
  release: () => void;
};

export type MediaSessionLike = {
  metadata: unknown;
  playbackState: string;
  setActionHandler: (action: string, handler: (() => void) | null) => void;
};

export type PlayerOptions = {
  file?: OutputFactory;
  soundcloud?: OutputFactory;
  /** Says "Now playing: …" to a screen reader. */
  announce?: (words: string) => void;
  mediaSession?: MediaSessionLike | null;
  makeMetadata?: ((init: { title: string; artist: string; artwork: { src: string }[] }) => unknown) | undefined;
  storage?: Pick<Storage, "getItem" | "setItem"> | null;
};

export const VOLUME_KEY = "mf-player-volume";
/** A gap between two readings longer than this was a seek or a stall, not listening. */
const MAX_STEP_MS = 1500;
/** How long "This track can't play right now" shows before the queue moves on. */
export const MOVE_ON_AFTER_MS = 1500;

const IDLE: Snapshot = {
  queue: [],
  index: -1,
  item: null,
  state: "idle",
  position_ms: 0,
  duration_ms: null,
  volume: 1,
  page: null,
};

function readVolume(storage: PlayerOptions["storage"]): number {
  try {
    const value = Number(storage?.getItem(VOLUME_KEY));
    return storage?.getItem(VOLUME_KEY) != null && value >= 0 && value <= 1 ? value : 1;
  } catch {
    return 1;
  }
}

export type Player = ReturnType<typeof createPlayer>;

export function createPlayer(options: PlayerOptions = {}) {
  const make = { file: options.file ?? fileOutput, soundcloud: options.soundcloud ?? soundcloudOutput };
  const listeners = new Set<() => void>();
  const others = new Set<{ pause: () => void }>();
  const views = new Map<symbol, string>();
  let now: Snapshot = { ...IDLE, volume: readVolume(options.storage) };
  let settings: PlayerSettings = DEFAULT_SETTINGS;
  /** Whether the visitor has granted `media`: one value for the app, set by every part and by a press. */
  let mediaGranted = true;
  let heard = 0;
  let last: number | null = null;
  let counted = false;
  /** Whether the length the output gave is the whole item's, not one track's of a playlist. */
  let whole = true;
  let moving: ReturnType<typeof setTimeout> | null = null;
  let checking: ReturnType<typeof setTimeout> | null = null;
  const outputs: Partial<Record<"file" | "soundcloud", Output>> = {};
  let current: Output | null = null;
  /** The key of the item `current` has loaded: none while a SoundCloud item waits for consent. */
  let loaded: string | null = null;

  const set = (patch: Partial<Snapshot>) => {
    now = { ...now, ...patch };
    const session = options.mediaSession;
    if (session) session.playbackState = now.state === "playing" ? "playing" : now.item ? "paused" : "none";
    for (const listener of listeners) listener();
  };

  const events = (kind: "file" | "soundcloud"): OutputEvents => {
    // Only the output in use is heard: one let go of may still say something.
    const live = () => current === outputs[kind];
    return {
      time: (position, duration, isWhole) => {
        if (!live()) return;
        if (now.state === "playing" && last !== null) {
          const step = position - last;
          if (step > 0 && step <= MAX_STEP_MS) heard += step;
        }
        last = position;
        // The item's own length, as its module typed it, is the whole item's.
        whole = duration === null ? true : (isWhole ?? true);
        const length = duration ?? now.item?.duration_ms ?? null;
        set({ position_ms: position, duration_ms: length });
        countIfHeard();
      },
      playing: () => {
        if (live()) set({ state: "playing" });
      },
      paused: () => {
        if (live() && now.state !== "idle") set({ state: "paused" });
      },
      waiting: () => {
        if (live() && now.state === "playing") set({ state: "loading" });
      },
      ended: () => {
        if (!live()) return;
        countIfHeard(true);
        const nextIndex = now.index + 1;
        if (settings.autoplay_next && nextIndex < now.queue.length) start(nextIndex, true);
        else {
          rewind();
          set({ state: "paused", position_ms: 0 });
        }
      },
      failed: () => {
        if (!live()) return;
        set({ state: "failed" });
        const nextIndex = now.index + 1;
        if (settings.autoplay_next && nextIndex < now.queue.length) {
          moving = setTimeout(() => {
            moving = null;
            if (now.state === "failed") start(nextIndex, true);
          }, MOVE_ON_AFTER_MS);
        }
      },
      blocked: () => {
        if (live()) set({ state: "blocked" });
      },
    };
  };

  const outputFor = (item: PlayerItem): Output => {
    const kind = viaSoundCloud(item) ? "soundcloud" : "file";
    let found = outputs[kind];
    if (!found) {
      found = make[kind](events(kind));
      found.volume(now.volume);
      outputs[kind] = found;
    }
    return found;
  };

  const rewind = () => {
    heard = 0;
    last = null;
    counted = false;
    whole = true;
  };

  /**
   * Each play-through counts once: the setting's seconds, or nearly all of a
   * shorter item. Only a length that's the whole item's makes it short: one
   * track's of a playlist never does (CodeRabbit on #149).
   */
  function countIfHeard(atEnd = false) {
    const item = now.item;
    if (!item || counted) return;
    const need = settings.count_after_seconds * 1000;
    const length = now.duration_ms;
    const short = whole && length !== null && length < need;
    const enough = short ? length * 0.9 : need;
    if (heard >= enough || (atEnd && short && heard >= length * 0.9)) {
      counted = true;
      item.count?.();
    }
  }

  const pauseOthers = (except?: { pause: () => void }) => {
    for (const other of others) if (other !== except) other.pause();
  };

  const describe = (item: PlayerItem) => {
    options.announce?.(`Now playing: ${item.title}`);
    const session = options.mediaSession;
    if (session && options.makeMetadata) {
      session.metadata = options.makeMetadata({
        title: item.title,
        artist: item.line,
        artwork: item.cover ? [{ src: item.cover.src }] : [],
      });
    }
  };

  /** The item at `index` of the queue, from its start, playing or not. */
  function start(index: number, playing: boolean) {
    if (moving) clearTimeout(moving);
    moving = null;
    const item = now.queue[index];
    if (!item) return;
    const output = outputFor(item);
    const allowed = !viaSoundCloud(item) || mediaGranted;
    // What played stops: another output's, or this one's when the next can't
    // load in its place (CodeRabbit on #149).
    if (current && (current !== output || (!allowed && loaded !== null))) current.stop();
    current = output;
    rewind();
    // SoundCloud is loaded only once media is granted: loading it is already
    // reaching SoundCloud (Codex on #149). It waits, paused, unloaded.
    loaded = null;
    if (allowed) {
      output.load(item);
      loaded = item.key;
    }
    set({ index, item, position_ms: 0, duration_ms: item.duration_ms ?? null, state: playing && allowed ? "loading" : "paused" });
    if (playing && allowed) {
      pauseOthers();
      describe(item);
      output.play();
    }
  }

  const stop = () => {
    if (moving) clearTimeout(moving);
    moving = null;
    current?.stop();
    current = null;
    loaded = null;
    rewind();
    set({ ...IDLE, volume: now.volume });
  };

  const checkViews = () => {
    if (checking) return;
    checking = setTimeout(() => {
      checking = null;
      if (now.page === null) return;
      if (![...views.values()].includes(now.page)) stop();
    }, 0);
  };

  const sessionActions = () => {
    const session = options.mediaSession;
    if (!session) return;
    const handlers: Record<string, () => void> = {
      play: () => { player.resume(); },
      pause: () => { player.pause(); },
      previoustrack: () => { player.prev(); },
      nexttrack: () => { player.next(); },
    };
    for (const [action, handler] of Object.entries(handlers)) {
      try {
        session.setActionHandler(action, handler);
      } catch {
        // A browser without that action.
      }
    }
  };

  const player = {
    subscribe: (listener: () => void): (() => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    snapshot: (): Snapshot => now,
    /** The settings the site's route gives, and whether the visitor has granted `media`. */
    configure(next: Partial<PlayerSettings> & { mediaGranted?: boolean }) {
      const { mediaGranted: granted, ...rest } = next;
      settings = { ...settings, ...rest };
      if (granted !== undefined) mediaGranted = granted;
    },
    /** A part of `page` that shows or plays the player: while one is left, it may keep playing. */
    attach(page: string): () => void {
      const token = Symbol(page);
      views.set(token, page);
      return () => {
        views.delete(token);
        checkViews();
      };
    },
    play(queue: readonly PlayerItem[], index = 0, page: string | null = null) {
      if (!queue[index]) return;
      now = { ...now, queue: [...queue], page };
      start(index, true);
    },
    /** Playing goes paused, and paused plays on from where it was. */
    toggle() {
      if (now.state === "playing" || now.state === "loading" || now.state === "blocked") player.pause();
      else player.resume();
    },
    resume() {
      const item = now.item;
      if (!item || !current) return;
      if (now.state === "failed") {
        start(now.index, true);
        return;
      }
      if (viaSoundCloud(item) && !mediaGranted) return;
      // An item that waited for consent is loaded now, from its start.
      if (loaded !== item.key) {
        current.load(item);
        loaded = item.key;
        describe(item);
      }
      pauseOthers();
      set({ state: "loading" });
      current.play();
    },
    pause() {
      if (!current || now.state === "idle") return;
      current.pause();
      set({ state: "paused" });
    },
    next() {
      if (!now.queue.length) return;
      const playing = now.state !== "paused" && now.state !== "idle";
      start((now.index + 1) % now.queue.length, playing);
    },
    prev() {
      if (!now.queue.length) return;
      const playing = now.state !== "paused" && now.state !== "idle";
      start((now.index - 1 + now.queue.length) % now.queue.length, playing);
    },
    seek(ms: number) {
      if (!current || !now.item) return;
      const length = now.duration_ms;
      const to = Math.max(0, length === null ? ms : Math.min(ms, length));
      current.seek(to);
      // A jump is not listening: the next reading starts from here.
      last = to;
      set({ position_ms: to });
    },
    setVolume(volume: number) {
      const level = Math.min(1, Math.max(0, volume));
      for (const output of Object.values(outputs)) output.volume(level);
      try {
        options.storage?.setItem(VOLUME_KEY, String(level));
      } catch {
        // Private windows and blocked storage: it's only remembered here.
      }
      set({ volume: level });
    },
    /** Another kind of player that takes turns with this one. */
    exclusive(pause: () => void): Exclusive {
      const entry = { pause };
      others.add(entry);
      return {
        claim: () => {
          if (current && (now.state === "playing" || now.state === "loading" || now.state === "blocked")) {
            current.pause();
            set({ state: "paused" });
          }
          pauseOthers(entry);
        },
        release: () => {
          others.delete(entry);
        },
      };
    },
    stop,
  };
  sessionActions();
  return player;
}

let made: Player | null = null;

/** The app's one player, made when first asked for. */
export function thePlayer(): Player {
  made ??= createPlayer({
    announce: announcer(),
    mediaSession: typeof navigator !== "undefined" && "mediaSession" in navigator ? (navigator.mediaSession as unknown as MediaSessionLike) : null,
    makeMetadata: typeof MediaMetadata === "undefined" ? undefined : (init) => new MediaMetadata(init),
    storage: safeStorage(),
  });
  return made;
}

function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export const ANNOUNCER_CLASS = "mf-player-announcer";

/** One polite status line for the whole app, so two players never say it twice. */
function announcer(): (words: string) => void {
  let line: HTMLParagraphElement | null = null;
  return (words) => {
    if (!line) {
      line = document.createElement("p");
      line.className = `mf-visually-hidden ${ANNOUNCER_CLASS}`;
      line.setAttribute("role", "status");
      document.body.append(line);
    }
    line.textContent = words;
  };
}
