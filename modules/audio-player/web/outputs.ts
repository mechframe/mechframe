/**
 * What the player plays through (`dev plans/contracts/audio-player.md` §2): one
 * audio element for stream files, and one hidden SoundCloud widget, each made
 * the first time it's needed. The store drives either through `Output` and
 * hears back through `OutputEvents`; tests give it fakes.
 */
import type { PlayerItem } from "./types";
import { loadSoundCloud, widgetAddress, type SoundCloudWidget } from "./soundcloud";

export type OutputEvents = {
  /** Where it is, and how long the item is once that's known. */
  time: (position_ms: number, duration_ms: number | null) => void;
  playing: () => void;
  paused: () => void;
  waiting: () => void;
  ended: () => void;
  failed: () => void;
  /** The browser wouldn't start a hidden player: SoundCloud's own Play is shown. */
  blocked: () => void;
};

export type Output = {
  /** Let go of what was loaded and ready this item, without playing it. */
  load: (item: PlayerItem) => void;
  play: () => void;
  pause: () => void;
  seek: (ms: number) => void;
  /** From 0 to 1. */
  volume: (volume: number) => void;
  /** Stop and let go. */
  stop: () => void;
};

export type OutputFactory = (events: OutputEvents) => Output;

function seconds(value: number): number | null {
  return Number.isFinite(value) && value > 0 ? value * 1000 : null;
}

/** A stream file in one audio element, never in the page's layout. */
export const fileOutput: OutputFactory = (events) => {
  const audio = new Audio();
  audio.preload = "none";
  audio.addEventListener("timeupdate", () => {
    events.time(audio.currentTime * 1000, seconds(audio.duration));
  });
  audio.addEventListener("durationchange", () => {
    events.time(audio.currentTime * 1000, seconds(audio.duration));
  });
  audio.addEventListener("playing", events.playing);
  audio.addEventListener("pause", () => {
    if (!audio.ended) events.paused();
  });
  audio.addEventListener("waiting", events.waiting);
  audio.addEventListener("ended", events.ended);
  audio.addEventListener("error", () => {
    if (audio.getAttribute("src")) events.failed();
  });
  return {
    load: (item) => {
      audio.pause();
      audio.src = item.stream_url ?? "";
    },
    play: () => {
      audio.play().catch((error: unknown) => {
        // A browser that wants a press first says NotAllowedError: that's paused, not broken.
        if (error instanceof DOMException && error.name === "NotAllowedError") events.paused();
        else if (!(error instanceof DOMException && error.name === "AbortError")) events.failed();
      });
    },
    pause: () => {
      audio.pause();
    },
    seek: (ms) => {
      audio.currentTime = ms / 1000;
    },
    volume: (volume) => {
      audio.volume = volume;
    },
    stop: () => {
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
    },
  };
};

/** How long a press may wait for SoundCloud's widget to start before its own Play is shown. */
export const BLOCKED_AFTER_MS = 4000;
export const HOST_CLASS = "mf-player-host";
export const SHOWN_CLASS = "mf-player-host-shown";

/**
 * SoundCloud's widget, hidden behind the site's controls in a holder of its own
 * at the end of `<body>`. A playlist plays as one item with one timeline: its
 * tracks' lengths add up, the place is the tracks before plus where the playing
 * one is, a seek into another track skips to it first, and the item ends after
 * the last (CodeRabbit on #149). Each load counts up, and a getter's answer for
 * an earlier load is dropped.
 */
export const soundcloudOutput: OutputFactory = (events) => {
  let host: HTMLDivElement | null = null;
  let widget: SoundCloudWidget | null = null;
  let frame: HTMLIFrameElement | null = null;
  let ready = false;
  let wanted: "play" | "pause" = "pause";
  let loadedUrl: string | null = null;
  /** The link whose widget is being made, while the Widget API loads. */
  let making: string | null = null;
  let watchdog: ReturnType<typeof setTimeout> | null = null;
  let volume = 1;
  /** Counts each load: an answer that comes for an earlier one is dropped. */
  let loads = 0;
  /** Each track's length: one for a track, each of a playlist's; none until known. */
  let lengths: number[] = [];
  /** The track of a playlist that plays now. */
  let sound = 0;
  /** Where to go in a track skipped to, once it plays. */
  let pendingSeek: number | null = null;

  const before = (at: number) => lengths.slice(0, at).reduce((sum, each) => sum + each, 0);
  const total = () => (lengths.length ? before(lengths.length) : null);
  const settle = () => {
    if (watchdog) clearTimeout(watchdog);
    watchdog = null;
  };
  const hide = () => {
    host?.classList.remove(SHOWN_CLASS);
    frame?.setAttribute("aria-hidden", "true");
    frame?.setAttribute("tabindex", "-1");
  };
  const show = () => {
    host?.classList.add(SHOWN_CLASS);
    frame?.removeAttribute("aria-hidden");
    frame?.removeAttribute("tabindex");
  };
  const begin = () => {
    if (!widget || !ready) return;
    widget.play();
    settle();
    watchdog = setTimeout(() => {
      watchdog = null;
      if (wanted === "play") {
        show();
        events.blocked();
      }
    }, BLOCKED_AFTER_MS);
  };
  const lengthOf = (sound: unknown): number => {
    const duration = typeof sound === "object" && sound !== null ? (sound as { duration?: unknown }).duration : undefined;
    return typeof duration === "number" && duration > 0 ? duration : 0;
  };
  const readied = () => {
    ready = true;
    const load = loads;
    const current = widget;
    current?.setVolume(Math.round(volume * 100));
    current?.getSounds((sounds) => {
      if (load !== loads) return;
      const found = sounds.map(lengthOf);
      if (found.length && found.every((length) => length > 0)) {
        lengths = found;
        events.time(0, total());
        return;
      }
      // A playlist's tracks not all known yet: the track playing, as the widget gives it.
      current.getDuration((ms) => {
        if (load !== loads) return;
        lengths = ms > 0 ? [ms] : [];
        events.time(0, total());
      });
    });
    if (wanted === "play") begin();
  };

  const make = (url: string) => {
    making = url;
    loadSoundCloud()
      .then((api) => {
        if (making === url) making = null;
        if (loadedUrl !== url || widget) return;
        host = document.createElement("div");
        host.className = HOST_CLASS;
        frame = document.createElement("iframe");
        frame.title = "SoundCloud player";
        frame.allow = "autoplay";
        frame.src = widgetAddress(url);
        host.append(frame);
        document.body.append(host);
        hide();
        const made = api.Widget(frame);
        widget = made;
        const on = api.Widget.Events;
        made.bind(on.READY, readied);
        made.bind(on.PLAY, () => {
          settle();
          hide();
          const load = loads;
          made.getCurrentSoundIndex((at) => {
            if (load !== loads) return;
            sound = at;
            if (pendingSeek !== null) {
              made.seekTo(pendingSeek);
              pendingSeek = null;
            }
          });
          events.playing();
        });
        made.bind(on.PAUSE, () => {
          if (wanted === "pause") events.paused();
        });
        made.bind(on.PLAY_PROGRESS, (event) => {
          events.time(before(sound) + (event?.currentPosition ?? 0), total());
        });
        // The widget moves itself on to a playlist's next track, and says PLAY.
        made.bind(on.FINISH, () => {
          if (sound >= lengths.length - 1) events.ended();
        });
        made.bind(on.ERROR, () => {
          settle();
          events.failed();
        });
      })
      .catch(() => {
        if (making === url) making = null;
        // Nothing to reuse: the next load of this link asks for the API again (Codex on #149).
        if (loadedUrl === url) loadedUrl = null;
        events.failed();
      });
  };

  return {
    load: (item) => {
      const url = item.soundcloud_url ?? "";
      wanted = "pause";
      settle();
      loads += 1;
      lengths = [];
      sound = 0;
      pendingSeek = null;
      // Its widget is on its way: that one starts it.
      if (loadedUrl === url && making === url) return;
      loadedUrl = url;
      ready = false;
      if (!widget) {
        make(url);
        return;
      }
      // The same link again loads again too, so it starts from its start (CodeRabbit on #149).
      widget.load(url, {
        auto_play: false,
        visual: false,
        show_comments: false,
        callback: readied,
      });
    },
    play: () => {
      wanted = "play";
      begin();
    },
    pause: () => {
      wanted = "pause";
      settle();
      hide();
      widget?.pause();
    },
    seek: (ms) => {
      if (!widget) return;
      if (lengths.length < 2) {
        widget.seekTo(ms);
        return;
      }
      let at = 0;
      while (at < lengths.length - 1 && ms >= before(at + 1)) at += 1;
      const within = ms - before(at);
      if (at === sound) {
        widget.seekTo(within);
        return;
      }
      pendingSeek = within;
      sound = at;
      widget.skip(at);
    },
    volume: (next) => {
      volume = next;
      widget?.setVolume(Math.round(next * 100));
    },
    stop: () => {
      wanted = "pause";
      settle();
      hide();
      widget?.pause();
    },
  };
};
