/**
 * SoundCloud's Widget API (https://developers.soundcloud.com/docs/api/html5-widget),
 * loaded once, the first time a SoundCloud track is played: never before, so
 * nothing reaches SoundCloud until a visitor asks (its host is in the CSP under
 * `media`). Only the calls the player makes are typed.
 */

export type SoundCloudWidget = {
  bind: (event: string, listener: (event?: { currentPosition?: number }) => void) => void;
  load: (url: string, options: Record<string, boolean | (() => void)>) => void;
  play: () => void;
  pause: () => void;
  seekTo: (ms: number) => void;
  setVolume: (volume: number) => void;
  getDuration: (callback: (ms: number) => void) => void;
  getCurrentSoundIndex: (callback: (index: number) => void) => void;
  getSounds: (callback: (sounds: readonly unknown[]) => void) => void;
};

export type SoundCloudApi = {
  Widget: ((iframe: HTMLIFrameElement) => SoundCloudWidget) & {
    Events: { READY: string; PLAY: string; PAUSE: string; FINISH: string; PLAY_PROGRESS: string; ERROR: string };
  };
};

declare global {
  interface Window {
    SC?: SoundCloudApi;
  }
}

export const WIDGET_API = "https://w.soundcloud.com/player/api.js";
export const WIDGET = "https://w.soundcloud.com/player/";

let loading: Promise<SoundCloudApi> | null = null;

/** The API, its script added the first time it's asked for; asked again after a failed load. */
export function loadSoundCloud(): Promise<SoundCloudApi> {
  const ready = window.SC;
  if (ready?.Widget) return Promise.resolve(ready);
  loading ??= new Promise<SoundCloudApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = WIDGET_API;
    script.async = true;
    script.onload = () => {
      loading = null;
      if (window.SC?.Widget) resolve(window.SC);
      else reject(new Error("SoundCloud's player didn't load."));
    };
    script.onerror = () => {
      loading = null;
      script.remove();
      reject(new Error("SoundCloud's player didn't load."));
    };
    document.head.append(script);
  });
  return loading;
}

/** The widget's address for a track or playlist, with SoundCloud's own parts hidden behind the site's controls. */
export function widgetAddress(url: string): string {
  const options = new URLSearchParams({
    url,
    auto_play: "false",
    visual: "false",
    show_comments: "false",
    show_artwork: "false",
    show_playcount: "false",
    show_user: "false",
    buying: "false",
    sharing: "false",
    download: "false",
  });
  return `${WIDGET}?${options.toString()}`;
}
