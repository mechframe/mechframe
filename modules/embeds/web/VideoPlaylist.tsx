/**
 * The YouTube playlist player (`docs/plans/vibrant-mindz-backend/videos-player.md`;
 * `dev plans/contracts/embeds.md` §2): a 16:9 stage with its control bar,
 * and the list beside it, scrolling at the stage's height, stacked under
 * 980px.
 *
 * - **The facade comes first:** the poster, the title and a big Play. YouTube's
 *   thumbnails show only once `media` is granted (the owner, 2026-11-22), so
 *   nothing reaches Google before a visitor plays.
 * - **Play** grants `media`, loads the IFrame API and plays on
 *   `youtube-nocookie.com`.
 * - **At a video's end,** with Autoplay on, the next one plays and the highlight
 *   moves; after the last, it stops.
 * - **Controls:** a row's click plays it, and Prev and Next wrap. Autoplay is a
 *   switch that never restarts what's playing.
 * - `onPlay`, and the handle's `pause()`, are for `audio-player`'s
 *   one-thing-at-a-time store (step 2), so it can drive this one.
 */
import { Button, useConsent } from "@/kernel";
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";

import "./embeds.css";
import { youtubeId } from "./providers";
import { loadYouTube, type YouTubePlayer } from "./youtube";

export type PlaylistItem = {
  /** Any YouTube link, or a bare 11-character id. */
  url: string;
  title: string;
  /** The site's own art for it, shown before YouTube's thumbnail may be. */
  poster?: string;
};

export type VideoPlaylistHandle = { pause: () => void };

export type VideoPlaylistProps = {
  items: readonly PlaylistItem[];
  /** Whether the switch starts on; it does by default. */
  autoplay?: boolean;
  /** Called each time a video starts playing. */
  onPlay?: () => void;
  ref?: Ref<VideoPlaylistHandle>;
  /** The list's name, for a screen reader: "Videos". */
  label?: string;
};

type Video = PlaylistItem & { id: string };

const NOCOOKIE = "https://www.youtube-nocookie.com";

function thumbnail(id: string): string {
  return `https://i.ytimg.com/vi/${id}/hqdefault.jpg`;
}

/** The moving bars beside the row that plays. */
function Equalizer() {
  return (
    <span className="mf-playlist-eq" aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

export function VideoPlaylist({ items, autoplay = true, onPlay, ref, label = "Videos" }: VideoPlaylistProps) {
  const videos: Video[] = items.flatMap((item) => {
    const id = youtubeId(item.url);
    return id ? [{ ...item, id }] : [];
  });
  const media = useConsent("media");
  const [current, setCurrent] = useState(0);
  const [started, setStarted] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [rolling, setRolling] = useState(autoplay);
  const [failed, setFailed] = useState(false);
  const stage = useRef<HTMLDivElement>(null);
  const player = useRef<YouTubePlayer | null>(null);
  // What the player's events read when they come, after this render.
  const now = useRef({ current, rolling, count: videos.length, onPlay, ids: videos.map((video) => video.id) });
  useEffect(() => {
    now.current = { current, rolling, count: videos.length, onPlay, ids: videos.map((video) => video.id) };
  });

  useImperativeHandle(ref, () => ({
    pause: () => {
      player.current?.pauseVideo();
    },
  }));

  useEffect(
    () => () => {
      player.current?.destroy();
      player.current = null;
    },
    [],
  );

  const shown = videos[Math.min(current, videos.length - 1)];
  if (!shown) return null;

  const play = (at: number) => {
    const video = videos[at];
    if (!video) return;
    setCurrent(at);
    if (player.current) {
      player.current.loadVideoById(video.id);
      return;
    }
    media.grant();
    setStarted(true);
    setFailed(false);
    loadYouTube()
      .then((api) => {
        const frame = stage.current?.querySelector<HTMLElement>(".mf-playlist-frame");
        if (!frame || player.current) return;
        // YouTube swaps the element it's given for its iframe: one of its own, not React's.
        const host = document.createElement("div");
        frame.append(host);
        player.current = new api.Player(host, {
          host: NOCOOKIE,
          videoId: video.id,
          width: "100%",
          height: "100%",
          playerVars: { autoplay: 1, rel: 0, playsinline: 1 },
          events: {
            onStateChange: ({ data }) => {
              if (data === api.PlayerState.PLAYING) {
                setPlaying(true);
                now.current.onPlay?.();
              } else if (data === api.PlayerState.PAUSED) {
                setPlaying(false);
              } else if (data === api.PlayerState.ENDED) {
                setPlaying(false);
                const next = now.current.current + 1;
                const id = now.current.ids[next];
                if (now.current.rolling && id) {
                  setCurrent(next);
                  player.current?.loadVideoById(id);
                }
              }
            },
          },
        });
      })
      .catch(() => {
        setStarted(false);
        setFailed(true);
      });
  };

  const step = (by: number) => {
    play((current + by + videos.length) % videos.length);
  };

  return (
    <section className="mf-playlist" aria-label={label}>
      <div className="mf-playlist-main">
        <div className="mf-playlist-stage" ref={stage}>
          <div className="mf-playlist-frame" />
          {started ? null : (
            <div className="mf-playlist-facade">
              {shown.poster ? <img className="mf-playlist-poster" src={shown.poster} alt="" /> : null}
              {media.granted ? <img className="mf-playlist-thumb" src={thumbnail(shown.id)} alt="" /> : null}
              <p className="mf-playlist-caption">{shown.title}</p>
              <Button
                variant="primary"
                size="large"
                icon="play"
                className="mf-playlist-play"
                aria-label={`Play ${shown.title}`}
                onClick={() => {
                  play(current);
                }}
              >
                Play
              </Button>
              {failed ? (
                <p className="mf-playlist-failed" role="status">
                  YouTube's player didn't load. Try again, or watch on{" "}
                  <a href={`https://www.youtube.com/watch?v=${shown.id}`}>YouTube</a>.
                </p>
              ) : null}
            </div>
          )}
        </div>
        <div className="mf-playlist-bar">
          <p className="mf-playlist-now">{shown.title}</p>
          <div className="mf-playlist-controls">
            <Button
              size="small"
              aria-label="Previous video"
              onClick={() => {
                step(-1);
              }}
            >
              Prev
            </Button>
            <Button
              size="small"
              aria-label="Next video"
              onClick={() => {
                step(1);
              }}
            >
              Next
            </Button>
            <Button
              size="small"
              aria-pressed={rolling}
              onClick={() => {
                setRolling((was) => !was);
              }}
            >
              Autoplay
            </Button>
          </div>
        </div>
      </div>
      <div className="mf-playlist-side">
        <ol className="mf-playlist-list">
          {videos.map((video, at) => (
            <li key={`${video.id}:${String(at)}`}>
              <button
                type="button"
                className="mf-playlist-row"
                aria-current={at === current ? "true" : undefined}
                onClick={() => {
                  play(at);
                }}
              >
                <span className="mf-playlist-number">{at + 1}</span>
                <span className="mf-playlist-title">{video.title}</span>
                {at === current && playing ? <Equalizer /> : null}
              </button>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
