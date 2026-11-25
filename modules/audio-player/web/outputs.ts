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
 * at the end of `<body>`. A playlist plays as one item: the widget runs through
 * its tracks, and the item ends after the last.
 */
export const soundcloudOutput: OutputFactory = (events) => {
  let host: HTMLDivElement | null = null;
  let widget: SoundCloudWidget | null = null;
  let frame: HTMLIFrameElement | null = null;
  let ready = false;
  let wanted: "play" | "pause" = "pause";
  let duration: number | null = null;
  let loadedUrl: string | null = null;
  let watchdog: ReturnType<typeof setTimeout> | null = null;
  let volume = 1;

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
  const readied = () => {
    ready = true;
    widget?.setVolume(Math.round(volume * 100));
    widget?.getDuration((ms) => {
      duration = ms > 0 ? ms : null;
      events.time(0, duration);
    });
    if (wanted === "play") begin();
  };

  const make = (url: string) => {
    loadSoundCloud()
      .then((api) => {
        if (loadedUrl !== url) return;
        host = document.createElement("div");
        host.className = HOST_CLASS;
        frame = document.createElement("iframe");
        frame.title = "SoundCloud player";
        frame.allow = "autoplay";
        frame.src = widgetAddress(url);
        host.append(frame);
        document.body.append(host);
        hide();
        widget = api.Widget(frame);
        const on = api.Widget.Events;
        widget.bind(on.READY, readied);
        widget.bind(on.PLAY, () => {
          settle();
          hide();
          events.playing();
        });
        widget.bind(on.PAUSE, () => {
          if (wanted === "pause") events.paused();
        });
        widget.bind(on.PLAY_PROGRESS, (event) => {
          events.time(event?.currentPosition ?? 0, duration);
        });
        widget.bind(on.FINISH, () => {
          const finished = widget;
          if (!finished) return;
          finished.getCurrentSoundIndex((index) => {
            finished.getSounds((sounds) => {
              if (index >= sounds.length - 1) events.ended();
            });
          });
        });
        widget.bind(on.ERROR, () => {
          settle();
          events.failed();
        });
      })
      .catch(() => {
        events.failed();
      });
  };

  return {
    load: (item) => {
      const url = item.soundcloud_url ?? "";
      wanted = "pause";
      settle();
      duration = null;
      if (loadedUrl === url) return;
      loadedUrl = url;
      ready = false;
      if (!widget) {
        make(url);
        return;
      }
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
      widget?.seekTo(ms);
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
