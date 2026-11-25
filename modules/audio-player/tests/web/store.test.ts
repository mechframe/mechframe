/**
 * The one player (`web/store.ts`; `dev plans/contracts/audio-player.md` §2 and
 * §7) on fake outputs: one thing at a time, pausing keeps the place, the queue's
 * wrap and end, counting only what's really heard, a page move, a track that
 * can't play, SoundCloud only with consent, the volume, the lock screen.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Output, OutputEvents, OutputFactory } from "../../web/outputs";
import { createPlayer, MOVE_ON_AFTER_MS, VOLUME_KEY, type MediaSessionLike } from "../../web/store";
import type { PlayerItem } from "../../web/types";

type FakeOutput = Output & { events: OutputEvents; loaded: PlayerItem[]; calls: string[]; seeks: number[]; volumes: number[] };

function fakes() {
  const made: Record<"file" | "soundcloud", FakeOutput[]> = { file: [], soundcloud: [] };
  const factory =
    (kind: "file" | "soundcloud"): OutputFactory =>
    (events) => {
      const output: FakeOutput = {
        events,
        loaded: [],
        calls: [],
        seeks: [],
        volumes: [],
        load: (item) => {
          output.loaded.push(item);
          output.calls.push("load");
        },
        play: () => output.calls.push("play"),
        pause: () => output.calls.push("pause"),
        seek: (ms) => output.seeks.push(ms),
        volume: (volume) => output.volumes.push(volume),
        stop: () => output.calls.push("stop"),
      };
      made[kind].push(output);
      return output;
    };
  return { made, file: factory("file"), soundcloud: factory("soundcloud") };
}

/** An item, where `undefined` takes a default away. */
type Overrides = { [K in keyof PlayerItem]?: PlayerItem[K] | undefined };

function item(name: string, overrides: Overrides = {}): PlayerItem {
  return { key: `discography.track:${name}`, title: name, line: "Vibrant Mindz", stream_url: `https://cdn.test/${name}.mp3`, duration_ms: 180_000, ...overrides } as PlayerItem;
}

const A = item("Gather Around");
const B = item("Unified");
const C = item("Vibrate");

function setup(extra: Parameters<typeof createPlayer>[0] = {}) {
  const outputs = fakes();
  const said: string[] = [];
  const player = createPlayer({ file: outputs.file, soundcloud: outputs.soundcloud, announce: (words) => said.push(words), ...extra });
  const file = () => {
    const found = outputs.made.file[0];
    if (!found) throw new Error("No file output yet.");
    return found;
  };
  return { player, outputs, said, file };
}

/** Readings every second from `from` to `to`, as an audio element's timeupdate gives them. */
function listen(output: FakeOutput, from: number, to: number, duration: number | null = 180_000) {
  for (let at = from; at <= to; at += 1000) output.events.time(at, duration);
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("playing", () => {
  it("loads the item, plays it and says so", () => {
    const { player, file, said } = setup();
    player.play([A, B], 0, "/");
    expect(file().loaded).toEqual([A]);
    expect(file().calls).toEqual(["load", "play"]);
    expect(player.snapshot()).toMatchObject({ item: A, index: 0, state: "loading", page: "/" });
    file().events.playing();
    expect(player.snapshot().state).toBe("playing");
    expect(said).toEqual(["Now playing: Gather Around"]);
  });

  it("pauses where it is and plays on from there, without loading it again", () => {
    const { player, file } = setup();
    player.play([A], 0, "/");
    file().events.playing();
    listen(file(), 0, 42_000);
    player.toggle();
    expect(player.snapshot()).toMatchObject({ state: "paused", position_ms: 42_000 });
    player.toggle();
    expect(file().calls).toEqual(["load", "play", "pause", "play"]);
    expect(player.snapshot().position_ms).toBe(42_000);
  });

  it("has one element, so starting another item lets the first go", () => {
    const { player, file, outputs } = setup();
    player.play([A], 0, "/");
    player.play([B, C], 1, "/");
    expect(outputs.made.file).toHaveLength(1);
    expect(file().loaded).toEqual([A, C]);
    expect(player.snapshot().item).toBe(C);
  });
});

describe("one thing at a time", () => {
  it("pauses another kind of player as it starts, and is paused by one's claim", () => {
    const { player, file } = setup();
    const video = vi.fn();
    const turn = player.exclusive(video);
    player.play([A], 0, "/");
    expect(video).toHaveBeenCalledTimes(1);
    file().events.playing();
    turn.claim();
    expect(player.snapshot().state).toBe("paused");
    expect(file().calls.at(-1)).toBe("pause");
    // The claimer isn't paused by its own claim.
    expect(video).toHaveBeenCalledTimes(1);
    turn.release();
    player.toggle();
    expect(video).toHaveBeenCalledTimes(1);
  });

  it("pauses every other player's turn when one claims", () => {
    const { player } = setup();
    const videos = vi.fn();
    const playlist = vi.fn();
    player.exclusive(videos);
    const other = player.exclusive(playlist);
    other.claim();
    expect(videos).toHaveBeenCalledTimes(1);
    expect(playlist).not.toHaveBeenCalled();
  });
});

describe("the queue", () => {
  it("wraps round with Previous and Next, and keeps playing or paused", () => {
    const { player, file } = setup();
    player.play([A, B, C], 2, "/");
    file().events.playing();
    player.next();
    expect(player.snapshot()).toMatchObject({ index: 0, state: "loading" });
    player.prev();
    expect(player.snapshot()).toMatchObject({ index: 2, state: "loading" });
    player.pause();
    player.next();
    expect(player.snapshot()).toMatchObject({ index: 0, state: "paused" });
    expect(file().calls.filter((call) => call === "play")).toHaveLength(3);
  });

  it("plays the next at an item's end, and stops at the end of the last", () => {
    const { player, file } = setup();
    player.play([A, B], 0, "/");
    file().events.ended();
    expect(player.snapshot()).toMatchObject({ index: 1, state: "loading" });
    file().events.ended();
    expect(player.snapshot()).toMatchObject({ index: 1, state: "paused", position_ms: 0 });
  });

  it("stops at an item's end when autoplay_next is off", () => {
    const { player, file } = setup();
    player.configure({ autoplay_next: false });
    player.play([A, B], 0, "/");
    file().events.ended();
    expect(player.snapshot()).toMatchObject({ index: 0, state: "paused" });
  });

  it("says a track can't play, then moves on", () => {
    const { player, file } = setup();
    player.play([A, B], 0, "/");
    file().events.failed();
    expect(player.snapshot().state).toBe("failed");
    vi.advanceTimersByTime(MOVE_ON_AFTER_MS);
    expect(player.snapshot()).toMatchObject({ index: 1, state: "loading" });
  });
});

describe("counting", () => {
  it("counts once, after 30 seconds really heard", () => {
    const { player, file } = setup();
    const count = vi.fn();
    player.play([{ ...A, count }], 0, "/");
    file().events.playing();
    listen(file(), 0, 29_000);
    expect(count).not.toHaveBeenCalled();
    listen(file(), 30_000, 90_000);
    expect(count).toHaveBeenCalledTimes(1);
  });

  it("doesn't count time skipped by seeking, or while paused", () => {
    const { player, file } = setup();
    const count = vi.fn();
    player.play([{ ...A, count }], 0, "/");
    file().events.playing();
    listen(file(), 0, 10_000);
    player.seek(150_000);
    listen(file(), 150_000, 165_000);
    expect(count).not.toHaveBeenCalled();
    player.pause();
    listen(file(), 165_000, 179_000);
    expect(count).not.toHaveBeenCalled();
  });

  it("counts a short track once nearly all of it is heard", () => {
    const { player, file } = setup();
    const count = vi.fn();
    player.play([{ ...A, duration_ms: 20_000, count }], 0, "/");
    file().events.playing();
    listen(file(), 0, 17_000, 20_000);
    expect(count).not.toHaveBeenCalled();
    listen(file(), 18_000, 20_000, 20_000);
    expect(count).toHaveBeenCalledTimes(1);
  });

  it("counts each play-through: from the start again counts again", () => {
    const { player, file } = setup();
    const count = vi.fn();
    const once = { ...A, count };
    player.configure({ autoplay_next: false });
    player.play([once], 0, "/");
    file().events.playing();
    listen(file(), 0, 31_000);
    file().events.ended();
    player.play([once], 0, "/");
    file().events.playing();
    listen(file(), 0, 31_000);
    expect(count).toHaveBeenCalledTimes(2);
  });

  it("takes its seconds from the settings", () => {
    const { player, file } = setup();
    const count = vi.fn();
    player.configure({ count_after_seconds: 10 });
    player.play([{ ...A, count }], 0, "/");
    file().events.playing();
    listen(file(), 0, 10_000);
    expect(count).toHaveBeenCalledTimes(1);
  });
});

describe("a page move", () => {
  it("stops once nothing of the page that started it is left", () => {
    const { player, file } = setup();
    const leave = player.attach("/music/unified");
    player.play([A], 0, "/music/unified");
    const other = player.attach("/videos");
    leave();
    vi.runAllTimers();
    expect(player.snapshot()).toMatchObject({ state: "idle", item: null, queue: [] });
    expect(file().calls.at(-1)).toBe("stop");
    other();
  });

  it("keeps playing while a part of its page is drawn again", () => {
    const { player } = setup();
    const first = player.attach("/music/unified");
    player.play([A], 0, "/music/unified");
    first();
    const again = player.attach("/music/unified");
    vi.runAllTimers();
    expect(player.snapshot().item).toBe(A);
    again();
  });
});

describe("SoundCloud", () => {
  const CATALYST = item("Catalyst", { stream_url: undefined, soundcloud_url: "https://soundcloud.com/petrodestroys/sets/catalyst" });

  it("plays through the widget's output, and the file's is let go", () => {
    const { player, outputs, file } = setup();
    player.play([A, CATALYST], 0, "/");
    player.next();
    expect(file().calls.at(-1)).toBe("stop");
    expect(outputs.made.soundcloud[0]?.calls).toEqual(["load", "play"]);
  });

  it("never loads SoundCloud without media consent: it waits, paused, then loads once allowed", () => {
    const { player, outputs } = setup();
    player.configure({ mediaGranted: false });
    player.play([CATALYST], 0, "/");
    expect(player.snapshot()).toMatchObject({ item: CATALYST, state: "paused" });
    const calls = () => outputs.made.soundcloud[0]?.calls.filter((call) => call !== "volume") ?? [];
    expect(calls()).toEqual([]);
    player.toggle();
    expect(calls()).toEqual([]);
    player.configure({ mediaGranted: true });
    player.toggle();
    expect(calls()).toEqual(["load", "play"]);
  });

  it("stops the SoundCloud item playing when consent goes and Next moves to another (CodeRabbit on #149)", () => {
    const { player, outputs } = setup();
    const other = item("Unified (SoundCloud)", { stream_url: undefined, soundcloud_url: "https://soundcloud.com/petrodestroys/unified" });
    player.play([CATALYST, other], 0, "/");
    outputs.made.soundcloud[0]?.events.playing();
    player.configure({ mediaGranted: false });
    player.next();
    expect(player.snapshot()).toMatchObject({ item: other, state: "paused" });
    const calls = outputs.made.soundcloud[0]?.calls.filter((call) => call !== "volume") ?? [];
    expect(calls).toEqual(["load", "play", "stop"]);
  });

  it("doesn't load SoundCloud without consent when the queue reaches it on its own (Codex on #149)", () => {
    const { player, outputs, file } = setup();
    player.configure({ mediaGranted: false });
    player.play([A, CATALYST], 0, "/");
    file().events.ended();
    expect(player.snapshot()).toMatchObject({ index: 1, state: "paused" });
    // A paused queue moved onto it doesn't load it either. (Stopping an output that loaded nothing reaches no one.)
    player.prev();
    player.next();
    expect(outputs.made.soundcloud[0]?.calls.filter((call) => call === "load" || call === "play") ?? []).toEqual([]);
  });

  it("says when the browser wants SoundCloud's own Play", () => {
    const { player, outputs } = setup();
    player.play([CATALYST], 0, "/");
    outputs.made.soundcloud[0]?.events.blocked();
    expect(player.snapshot().state).toBe("blocked");
    player.toggle();
    expect(player.snapshot().state).toBe("paused");
  });
});

describe("the volume and the lock screen", () => {
  it("keeps the volume in this browser, and reads it back", () => {
    const kept = new Map<string, string>();
    const storage = { getItem: (key: string) => kept.get(key) ?? null, setItem: (key: string, value: string) => kept.set(key, value) };
    const { player, file } = setup({ storage });
    player.play([A], 0, "/");
    player.setVolume(0.4);
    expect(file().volumes.at(-1)).toBe(0.4);
    expect(kept.get(VOLUME_KEY)).toBe("0.4");
    expect(setup({ storage }).player.snapshot().volume).toBe(0.4);
  });

  it("gives the lock screen the title, line and cover, and its four buttons", () => {
    const handlers = new Map<string, (() => void) | null>();
    const session: MediaSessionLike = { metadata: null, playbackState: "none", setActionHandler: (action, handler) => handlers.set(action, handler) };
    const { player, file } = setup({ mediaSession: session, makeMetadata: (init) => init });
    player.play([{ ...A, cover: { src: "/covers/unified.jpg", alt: "" } }, B], 0, "/");
    expect(session.metadata).toEqual({ title: "Gather Around", artist: "Vibrant Mindz", artwork: [{ src: "/covers/unified.jpg" }] });
    file().events.playing();
    expect(session.playbackState).toBe("playing");
    handlers.get("nexttrack")?.();
    expect(player.snapshot().index).toBe(1);
    handlers.get("pause")?.();
    expect(session.playbackState).toBe("paused");
    expect([...handlers.keys()].sort()).toEqual(["nexttrack", "pause", "play", "previoustrack"]);
  });
});
