/**
 * The player's two outputs (`web/outputs.ts`): the audio element for a stream
 * file, and SoundCloud's widget, hidden at the end of `<body>`, on a fake Widget
 * API. Nothing reaches SoundCloud: `window.SC` is the fake, so the script is
 * never added.
 */
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { BLOCKED_AFTER_MS, fileOutput, HOST_CLASS, SHOWN_CLASS, soundcloudOutput, type OutputEvents } from "../../web/outputs";
import { WIDGET_API } from "../../web/soundcloud";
import type { PlayerItem } from "../../web/types";

function heard() {
  const said: string[] = [];
  const times: [number, number | null][] = [];
  /** Whether each time said its length was the whole item's. */
  const wholes: boolean[] = [];
  const events: OutputEvents = {
    time: (position, duration, whole) => {
      times.push([position, duration]);
      wholes.push(whole ?? true);
    },
    playing: () => said.push("playing"),
    paused: () => said.push("paused"),
    waiting: () => said.push("waiting"),
    ended: () => said.push("ended"),
    failed: () => said.push("failed"),
    blocked: () => said.push("blocked"),
  };
  return { events, said, times, wholes };
}

const FILE: PlayerItem = { key: "discography.track:a", title: "Gather Around", line: "Vibrant Mindz", stream_url: "https://cdn.test/a.mp3" };
const SET: PlayerItem = { key: "discography.track:c", title: "Catalyst", line: "petro and J Tone", soundcloud_url: "https://soundcloud.com/petrodestroys/sets/catalyst" };

describe("a stream file", () => {
  let play: Mock<() => Promise<void>>;

  beforeEach(() => {
    play = vi.fn<() => Promise<void>>(() => Promise.resolve());
    vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(play);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("plays the item's file in one element it never puts on the page", () => {
    const { events, said } = heard();
    const output = fileOutput(events);
    output.load(FILE);
    output.play();
    expect(play).toHaveBeenCalledTimes(1);
    expect(document.querySelector("audio")).toBeNull();
    output.volume(0.5);
    output.seek(12_000);
    expect(said).toEqual([]);
  });

  it("hears the element's events", () => {
    const { events, said, times } = heard();
    const audio = vi.spyOn(window, "Audio");
    const output = fileOutput(events);
    const element = audio.mock.results[0]?.value as HTMLAudioElement;
    output.load(FILE);
    for (const name of ["playing", "waiting", "ended"]) element.dispatchEvent(new Event(name));
    element.dispatchEvent(new Event("timeupdate"));
    element.dispatchEvent(new Event("error"));
    expect(said).toEqual(["playing", "waiting", "ended", "failed"]);
    expect(times).toEqual([[0, null]]);
  });

  it("reads a browser that wants a press first as paused, not broken", async () => {
    play.mockImplementation(() => Promise.reject(new DOMException("Wants a press", "NotAllowedError")));
    const { events, said } = heard();
    const output = fileOutput(events);
    output.load(FILE);
    output.play();
    await vi.waitFor(() => {
      expect(said).toEqual(["paused"]);
    });
  });

  it("says a file that won't play failed", async () => {
    play.mockImplementation(() => Promise.reject(new DOMException("No such file", "NotSupportedError")));
    const { events, said } = heard();
    const output = fileOutput(events);
    output.load(FILE);
    output.play();
    await vi.waitFor(() => {
      expect(said).toEqual(["failed"]);
    });
  });
});

type Bound = Record<string, (event?: { currentPosition?: number }) => void>;

/**
 * The Widget API as SoundCloud documents it: each sound's `duration` from
 * `getSounds`, the playing sound's index, `skip` to another, and a playlist
 * moving on to its next sound after each FINISH. With `deferred`, the getters'
 * answers wait for `flush()`, as the real ones arrive later by postMessage.
 */
function fakeSoundCloud({ lengths = [2_400_000], deferred = false }: { lengths?: number[]; deferred?: boolean } = {}) {
  const bound: Bound = {};
  const calls: string[] = [];
  const frames: HTMLIFrameElement[] = [];
  const waiting: (() => void)[] = [];
  let index = 0;
  const answer = (reply: () => void) => {
    if (deferred) waiting.push(reply);
    else reply();
  };
  const widget = {
    bind: (event: string, listener: (event?: { currentPosition?: number }) => void) => {
      bound[event] = listener;
    },
    load: (url: string, options: Record<string, unknown>) => {
      calls.push(`load ${url}`);
      index = 0;
      (options.callback as () => void)();
    },
    play: () => calls.push("play"),
    pause: () => calls.push("pause"),
    seekTo: (ms: number) => calls.push(`seek ${String(ms)}`),
    skip: (to: number) => {
      calls.push(`skip ${String(to)}`);
      index = to;
    },
    setVolume: (volume: number) => calls.push(`volume ${String(volume)}`),
    getDuration: (callback: (ms: number) => void) => {
      const at = index;
      answer(() => {
        callback(lengths[at] ?? 0);
      });
    },
    getCurrentSoundIndex: (callback: (at: number) => void) => {
      const at = index;
      answer(() => {
        callback(at);
      });
    },
    getSounds: (callback: (list: readonly unknown[]) => void) => {
      answer(() => {
        callback(lengths.map((duration) => ({ duration })));
      });
    },
  };
  const Widget = Object.assign(
    (frame: HTMLIFrameElement) => {
      frames.push(frame);
      return widget;
    },
    { Events: { READY: "ready", PLAY: "play", PAUSE: "pause", FINISH: "finish", PLAY_PROGRESS: "progress", ERROR: "error" } },
  );
  window.SC = { Widget };
  const say = (event: string, data?: { currentPosition?: number }) => {
    bound[event]?.(data);
    // A playlist moves on to its next sound after one finishes.
    if (event === "finish" && index < lengths.length - 1) index += 1;
  };
  const flush = () => {
    for (const reply of waiting.splice(0)) reply();
  };
  return { calls, frames, say, flush };
}

describe("SoundCloud's widget", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    delete window.SC;
    document.querySelectorAll(`.${HOST_CLASS}`).forEach((host) => {
      host.remove();
    });
  });

  async function loaded(options: Parameters<typeof fakeSoundCloud>[0] = {}) {
    const fake = fakeSoundCloud(options);
    const { events, said, times, wholes } = heard();
    const output = soundcloudOutput(events);
    output.load(SET);
    output.play();
    await vi.waitFor(() => {
      expect(fake.frames).toHaveLength(1);
    });
    return { ...fake, output, said, times, wholes };
  }

  it("plays a hidden widget once it's ready, its own parts hidden", async () => {
    const { frames, calls, say, said, times } = await loaded();
    const frame = frames[0] as HTMLIFrameElement;
    const address = new URL(frame.src);
    expect(`${address.origin}${address.pathname}`).toBe("https://w.soundcloud.com/player/");
    expect(address.searchParams.get("url")).toBe(SET.soundcloud_url);
    expect(address.searchParams.get("auto_play")).toBe("false");
    expect(frame).toHaveAttribute("aria-hidden", "true");
    expect(frame).toHaveAttribute("title", "SoundCloud player");
    expect(frame.closest(`.${HOST_CLASS}`)).not.toHaveClass(SHOWN_CLASS);
    expect(document.head.querySelector(`script[src="${WIDGET_API}"]`)).toBeNull();
    say("ready");
    expect(calls).toEqual(["volume 100", "play"]);
    expect(times).toEqual([[0, 2_400_000]]);
    say("play");
    say("progress", { currentPosition: 61_000 });
    expect(said).toEqual(["playing"]);
    expect(times.at(-1)).toEqual([61_000, 2_400_000]);
  });

  it("ends a playlist after its last track, not its first", async () => {
    const { say, said } = await loaded({ lengths: [60_000, 60_000] });
    say("ready");
    say("play");
    say("finish");
    expect(said).toEqual(["playing"]);
    say("play");
    say("finish");
    expect(said).toEqual(["playing", "playing", "ended"]);
  });

  it("gives a playlist one timeline across its tracks, and seeks within it (CodeRabbit on #149)", async () => {
    const { calls, output, say, times, wholes } = await loaded({ lengths: [60_000, 60_000] });
    say("ready");
    expect(times.at(-1)).toEqual([0, 120_000]);
    say("play");
    say("progress", { currentPosition: 5_000 });
    expect(times.at(-1)).toEqual([5_000, 120_000]);
    say("finish");
    say("play");
    say("progress", { currentPosition: 5_000 });
    expect(times.at(-1)).toEqual([65_000, 120_000]);
    // Every length known: the item's whole length, which the store may count a short item by.
    expect(wholes.every(Boolean)).toBe(true);
    // Within the track playing: a seek in it.
    output.seek(90_000);
    expect(calls.at(-1)).toBe("seek 30000");
    // In another track: skip to it, then seek once it plays.
    output.seek(10_000);
    expect(calls.at(-1)).toBe("skip 0");
    say("play");
    expect(calls.at(-1)).toBe("seek 10000");
    say("progress", { currentPosition: 10_000 });
    expect(times.at(-1)).toEqual([10_000, 120_000]);
  });

  it("plays a playlist with a length it doesn't give to its end, a track at a time (CodeRabbit on #149)", async () => {
    // The second track's length isn't known yet: each track's own place shows.
    const { output, say, said, times, calls, wholes } = await loaded({ lengths: [60_000, 0] });
    say("ready");
    expect(times.at(-1)).toEqual([0, 60_000]);
    say("play");
    say("progress", { currentPosition: 5_000 });
    expect(times.at(-1)).toEqual([5_000, 60_000]);
    output.seek(20_000);
    expect(calls.at(-1)).toBe("seek 20000");
    say("finish");
    // Not ended: the playlist has a second track.
    expect(said).toEqual(["playing"]);
    say("play");
    say("progress", { currentPosition: 3_000 });
    expect(times.at(-1)).toEqual([3_000, null]);
    // Each track's own length is never the whole item's (CodeRabbit on #149).
    expect(wholes.some(Boolean)).toBe(false);
    say("finish");
    expect(said).toEqual(["playing", "playing", "ended"]);
  });

  it("keeps the newest seek into a track still being skipped to (CodeRabbit on #149)", async () => {
    const { calls, flush, output, say } = await loaded({ lengths: [60_000, 60_000], deferred: true });
    say("ready");
    flush();
    output.seek(90_000);
    expect(calls.at(-1)).toBe("skip 1");
    // A second seek into the same track before it plays: it wins.
    output.seek(100_000);
    say("play");
    flush();
    expect(calls).toContain("seek 40000");
    expect(calls).not.toContain("seek 30000");
  });

  it("drops a getter's answer that comes after another load (CodeRabbit on #149)", async () => {
    const { calls, flush, output, say, times } = await loaded({ lengths: [60_000, 60_000], deferred: true });
    say("ready");
    flush();
    output.seek(90_000);
    expect(calls.at(-1)).toBe("skip 1");
    say("play");
    // The answer to "which sound?" (the second) is still on its way when another link loads.
    output.load({ ...SET, key: "discography.track:e", soundcloud_url: "https://soundcloud.com/petrodestroys/other-set" });
    flush();
    expect(calls).not.toContain("seek 30000");
    // The new link's place isn't counted from the old answer's track.
    say("progress", { currentPosition: 1_000 });
    expect(times.at(-1)).toEqual([1_000, 120_000]);
  });

  it("starts the same link over when it's loaded again (CodeRabbit on #149)", async () => {
    const { calls, output, say, times } = await loaded();
    say("ready");
    say("play");
    say("progress", { currentPosition: 61_000 });
    output.load(SET);
    expect(calls.filter((call) => call.startsWith("load "))).toEqual([`load ${String(SET.soundcloud_url)}`]);
    expect(times.at(-1)).toEqual([0, 2_400_000]);
  });

  it("shows SoundCloud's own Play when the browser won't start a hidden one", async () => {
    const { frames, say, said } = await loaded();
    say("ready");
    vi.advanceTimersByTime(BLOCKED_AFTER_MS);
    expect(said).toEqual(["blocked"]);
    const frame = frames[0] as HTMLIFrameElement;
    expect(frame.closest(`.${HOST_CLASS}`)).toHaveClass(SHOWN_CLASS);
    expect(frame).not.toHaveAttribute("aria-hidden");
    say("play");
    expect(frame.closest(`.${HOST_CLASS}`)).not.toHaveClass(SHOWN_CLASS);
  });

  it("loads the next link into the same widget, and pauses and seeks it", async () => {
    const { calls, frames, output, say } = await loaded();
    say("ready");
    output.load({ ...SET, key: "discography.track:d", soundcloud_url: "https://soundcloud.com/petrodestroys/other" });
    expect(frames).toHaveLength(1);
    expect(calls.at(-1)).toBe("volume 100");
    expect(calls).toContain("load https://soundcloud.com/petrodestroys/other");
    output.seek(5000);
    output.pause();
    expect(calls.slice(-2)).toEqual(["seek 5000", "pause"]);
  });

  it("says a widget that fails", async () => {
    const { say, said } = await loaded();
    say("error");
    expect(said).toEqual(["failed"]);
  });

  it("asks for the Widget API again after it failed to load, and plays once it comes (Codex on #149)", async () => {
    const { events, said } = heard();
    const output = soundcloudOutput(events);
    const script = () => document.head.querySelector<HTMLScriptElement>(`script[src="${WIDGET_API}"]`);
    output.load(SET);
    output.play();
    script()?.dispatchEvent(new Event("error"));
    await vi.waitFor(() => {
      expect(said).toEqual(["failed"]);
    });
    expect(script()).toBeNull();
    // The store's retry loads the same link again: a second script is asked for.
    output.load(SET);
    output.play();
    expect(script()).not.toBeNull();
    const fake = fakeSoundCloud();
    script()?.dispatchEvent(new Event("load"));
    await vi.waitFor(() => {
      expect(fake.frames).toHaveLength(1);
    });
    fake.say("ready");
    expect(fake.calls).toEqual(["volume 100", "play"]);
    script()?.remove();
  });

  it("makes one widget for a link loaded twice while the API comes", async () => {
    const fake = fakeSoundCloud();
    const output = soundcloudOutput(heard().events);
    output.load(SET);
    output.load(SET);
    await vi.waitFor(() => {
      expect(fake.frames).toHaveLength(1);
    });
    await Promise.resolve();
    expect(document.querySelectorAll(`.${HOST_CLASS}`)).toHaveLength(1);
  });
});
