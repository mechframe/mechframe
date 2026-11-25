// audio-player's parts as a page draws them (harness/web/player.html, at
// /player.html; dev plans/contracts/audio-player.md §7): a Spotlight-style bar,
// embeds' YouTube playlist taking turns with it through `useExclusive`, and a
// dock after the footer on a long page. The tracks are WAV files Playwright
// answers itself (modules/audio-player/tests/e2e/audio-player.spec.ts); YouTube's
// API is its fake too. Sample words only.
import "../../../themes/machined-light/tokens.css";
import "../../../themes/vibrant-mindz/tokens.css";
import "./frame.css";

import { useRef } from "react";

import { AfterFooter, defineSite, mountApp } from "@/kernel";
import { PlayerBar, PlayerDock, useExclusive, type PlayerItem } from "@/modules/audio-player/public";
import { VideoPlaylist, type VideoPlaylistHandle } from "@/modules/embeds/public";

const TRACKS: PlayerItem[] = [
  { key: "harness.track:one", title: "First sample", line: "Sample album, the harness", stream_url: "/e2e-audio/one.wav" },
  { key: "harness.track:two", title: "Second sample", line: "Sample album, the harness", stream_url: "/e2e-audio/two.wav" },
];

const VIDEOS = [{ url: "https://www.youtube.com/watch?v=aBcDeFgHiJk", title: "A sample video" }];

function Players() {
  const videos = useRef<VideoPlaylistHandle>(null);
  const claim = useExclusive(() => {
    videos.current?.pause();
  });
  return (
    <>
      <section className="frame-long">
        <h1>The player</h1>
        <PlayerBar queue={TRACKS} label="Spotlight single" />
        <h2>Videos</h2>
        <VideoPlaylist ref={videos} items={VIDEOS} onPlay={claim} />
      </section>
      <AfterFooter>
        <PlayerDock queue={TRACKS} label="Player" />
      </AfterFooter>
    </>
  );
}

const site = defineSite({
  routes: {
    public: [{ path: "/player.html", lazy: () => Promise.resolve({ default: Players }) }],
    member: [],
  },
});

void mountApp({ modules: [], site });
