/**
 * YouTube's IFrame API (https://developers.google.com/youtube/iframe_api_reference),
 * loaded once, the first time a playlist is played: never before, so nothing
 * reaches YouTube until a visitor asks (its host is in the CSP under `media`).
 * Only the few calls the playlist player makes are typed.
 */

export type YouTubePlayer = {
  loadVideoById: (videoId: string) => void;
  pauseVideo: () => void;
  destroy: () => void;
};

export type YouTubeOptions = {
  host: string;
  videoId: string;
  width?: string;
  height?: string;
  playerVars: Record<string, number | string>;
  events: { onStateChange: (event: { data: number }) => void };
};

export type YouTubeApi = {
  Player: new (element: HTMLElement, options: YouTubeOptions) => YouTubePlayer;
  PlayerState: { ENDED: number; PLAYING: number; PAUSED: number };
};

declare global {
  interface Window {
    YT?: YouTubeApi;
    onYouTubeIframeAPIReady?: () => void;
  }
}

export const IFRAME_API = "https://www.youtube.com/iframe_api";

let loading: Promise<YouTubeApi> | null = null;

/** The API, its script added the first time it's asked for; asked again after a failed load. */
export function loadYouTube(): Promise<YouTubeApi> {
  const ready = window.YT;
  if (ready?.Player) return Promise.resolve(ready);
  loading ??= new Promise<YouTubeApi>((resolve, reject) => {
    const before = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      before?.();
      // Kept only while it loads: once here, `window.YT` answers.
      loading = null;
      if (window.YT) resolve(window.YT);
    };
    const script = document.createElement("script");
    script.src = IFRAME_API;
    script.async = true;
    script.onerror = () => {
      loading = null;
      script.remove();
      reject(new Error("YouTube's player didn't load."));
    };
    document.head.append(script);
  });
  return loading;
}
