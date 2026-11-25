/**
 * The player in React (`dev plans/contracts/audio-player.md` §2): `usePlayer`
 * reads the one player and acts on it for the page it's drawn on, and
 * `useExclusive` lets another kind of player take turns with it.
 *
 * - Each part that calls `usePlayer` holds its page open for the player: once
 *   none of the page that started it is left, it stops (§8, 4).
 * - Pressing Play on a SoundCloud item grants `media`, as an embed's Play does
 *   (SPEC 8); the player never loads SoundCloud without it.
 */
import { useConsent } from "@/kernel";
import { createContext, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { useLocation } from "react-router";

import { SETTINGS, useApiQuery } from "./api";
import { thePlayer, type Player, type Snapshot } from "./store";
import { viaSoundCloud, type PlayerItem } from "./types";

/** The player the hooks use: the app's one, or a test's own. */
export const PlayerContext = createContext<Player | null>(null);

function usePlayerInstance(): Player {
  return useContext(PlayerContext) ?? thePlayer();
}

export type PlayerControls = Snapshot & {
  play: (queue: readonly PlayerItem[], index?: number) => void;
  toggle: () => void;
  pause: () => void;
  next: () => void;
  prev: () => void;
  seek: (ms: number) => void;
  setVolume: (volume: number) => void;
};

export function usePlayer(): PlayerControls {
  const player = usePlayerInstance();
  const page = useLocation().pathname;
  const media = useConsent("media");
  const settings = useApiQuery("get", SETTINGS, {}, { staleTime: 60_000 });
  const snapshot = useSyncExternalStore(player.subscribe, player.snapshot, player.snapshot);

  useEffect(() => player.attach(page), [player, page]);
  // Read when the player asks, so a grant from another part counts at once.
  const granted = useRef(media.granted);
  useEffect(() => {
    granted.current = media.granted;
  }, [media.granted]);
  useEffect(() => {
    player.configure({ soundcloudAllowed: () => granted.current });
  }, [player]);
  useEffect(() => {
    if (settings.data) player.configure(settings.data);
  }, [player, settings.data]);

  const { grant } = media;
  return useMemo(() => {
    /** A press that's about to start `item`: for SoundCloud, that's the visitor's consent to `media`. */
    const pressing = (item: PlayerItem | null | undefined) => {
      if (viaSoundCloud(item) && !granted.current) {
        grant();
        granted.current = true;
      }
    };
    const after = (step: 1 | -1) => snapshot.queue[(snapshot.index + step + snapshot.queue.length) % Math.max(1, snapshot.queue.length)];
    return {
      ...snapshot,
      play: (queue, index = 0) => {
        pressing(queue[index]);
        player.play(queue, index, page);
      },
      toggle: () => {
        pressing(snapshot.item);
        player.toggle();
      },
      pause: () => {
        player.pause();
      },
      next: () => {
        if (snapshot.state !== "paused" && snapshot.state !== "idle") pressing(after(1));
        player.next();
      },
      prev: () => {
        if (snapshot.state !== "paused" && snapshot.state !== "idle") pressing(after(-1));
        player.prev();
      },
      seek: (ms) => {
        player.seek(ms);
      },
      setVolume: (volume) => {
        player.setVolume(volume);
      },
    };
  }, [player, page, snapshot, grant]);
}

/**
 * For a player that isn't this module's, such as embeds' `VideoPlaylist`:
 * `pause` is called when the audio starts, and the `claim` it gives is called
 * as that player starts, which pauses the audio.
 *
 *     const videos = useRef<VideoPlaylistHandle>(null);
 *     const claim = useExclusive(() => videos.current?.pause());
 *     <VideoPlaylist ref={videos} onPlay={claim} items={...} />
 */
export function useExclusive(pause: () => void): () => void {
  const player = usePlayerInstance();
  const latest = useRef(pause);
  useEffect(() => {
    latest.current = pause;
  }, [pause]);
  const turn = useRef<ReturnType<Player["exclusive"]> | null>(null);
  useEffect(() => {
    const made = player.exclusive(() => {
      latest.current();
    });
    turn.current = made;
    return () => {
      made.release();
      turn.current = null;
    };
  }, [player]);
  return useMemo(
    () => () => {
      turn.current?.claim();
    },
    [],
  );
}

/** Whether `queue` is the one playing (or paused) now: the same items in the same order. */
export function isQueue(snapshot: Pick<Snapshot, "queue">, queue: readonly PlayerItem[]): boolean {
  return snapshot.queue.length === queue.length && snapshot.queue.every((item, at) => item.key === queue[at]?.key);
}
