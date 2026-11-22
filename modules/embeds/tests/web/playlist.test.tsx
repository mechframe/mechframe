// The YouTube playlist player (videos-player.md; embeds.md §2 and §7), with
// YouTube's IFrame API stubbed: the facade first, no thumbnail before media is
// granted, rolling through the list, Prev and Next wrapping, the switch, and
// the hand-off `audio-player` will use.
import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CONSENT_COOKIE, useConsent } from "@/kernel";
import { renderWithKernel } from "@/kernel/testing";
import { VideoPlaylist, type PlaylistItem, type VideoPlaylistHandle } from "@/modules/embeds/public";

import { IFRAME_API, loadYouTube, type YouTubeOptions } from "../../web/youtube";

const STATE = { ENDED: 0, PLAYING: 1, PAUSED: 2 };

class FakePlayer {
  static made: FakePlayer[] = [];
  loaded: string[] = [];
  paused = 0;
  destroyed = false;
  constructor(
    public element: HTMLElement,
    public options: YouTubeOptions,
  ) {
    FakePlayer.made.push(this);
  }
  loadVideoById(id: string) {
    this.loaded.push(id);
  }
  pauseVideo() {
    this.paused += 1;
  }
  destroy() {
    this.destroyed = true;
  }
  say(state: number) {
    act(() => {
      this.options.events.onStateChange({ data: state });
    });
  }
  /** YouTube's onReady: from here the player takes calls. */
  ready() {
    act(() => {
      this.options.events.onReady();
    });
  }
}

const ITEMS: PlaylistItem[] = [
  { url: "https://youtu.be/aaaaaaaaaaa", title: "First", poster: "/posters/first.jpg" },
  { url: "not a video", title: "Skipped" },
  { url: "https://www.youtube.com/watch?v=bbbbbbbbbbb", title: "Second" },
  { url: "ccccccccccc", title: "Third" },
];

function player(): FakePlayer {
  const made = FakePlayer.made.at(-1);
  if (!made) throw new Error("No player was made.");
  return made;
}

function row(name: string): HTMLElement {
  return within(screen.getByRole("list")).getByRole("button", { name: new RegExp(name) });
}

beforeEach(() => {
  FakePlayer.made = [];
  window.YT = { Player: FakePlayer, PlayerState: STATE };
});

afterEach(() => {
  delete window.YT;
  delete window.onYouTubeIframeAPIReady;
  document.head.querySelectorAll(`script[src="${IFRAME_API}"]`).forEach((script) => {
    script.remove();
  });
  document.cookie = `${CONSENT_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax; Secure`;
});

/** A banner's Withdraw for media, beside the player. */
function Withdraw() {
  const media = useConsent("media");
  return (
    <button type="button" onClick={media.withdraw}>
      Withdraw media
    </button>
  );
}

/** A banner's Allow for media, beside the player. */
function Grant() {
  const media = useConsent("media");
  return (
    <button type="button" onClick={media.grant}>
      Allow media
    </button>
  );
}

/** The playlist with its list changed by a button, as a page's data may change. */
function Changing({ lists }: { lists: Record<string, PlaylistItem[]> }) {
  const [items, setItems] = useState<PlaylistItem[]>(ITEMS);
  return (
    <>
      <VideoPlaylist items={items} />
      {Object.entries(lists).map(([name, list]) => (
        <button
          key={name}
          type="button"
          onClick={() => {
            setItems(list);
          }}
        >
          {name}
        </button>
      ))}
    </>
  );
}

/** YouTube's script arriving: the API there, and its ready call made. */
function youTubeArrives() {
  act(() => {
    window.YT = { Player: FakePlayer, PlayerState: STATE };
    window.onYouTubeIframeAPIReady?.();
  });
}

describe("VideoPlaylist", () => {
  it("shows the facade first, with the site's poster and no thumbnail of YouTube's before media is granted", () => {
    const { container } = renderWithKernel(<VideoPlaylist items={ITEMS} />);
    expect(screen.getByRole("button", { name: "Play First" })).toBeInTheDocument();
    const images = Array.from(container.querySelectorAll("img")).map((image) => image.getAttribute("src"));
    expect(images).toEqual(["/posters/first.jpg"]);
    expect(within(screen.getByRole("list")).getAllByRole("button")).toHaveLength(3);
    expect(row("First")).toHaveAttribute("aria-current", "true");
    expect(FakePlayer.made).toHaveLength(0);
  });

  it("shows YouTube's thumbnail once media is granted", () => {
    const { container } = renderWithKernel(<VideoPlaylist items={ITEMS} />, {
      site: { consent: { mode: "off", categories: [] } },
    });
    expect(container.querySelector(".mf-playlist-thumb")).toHaveAttribute(
      "src",
      "https://i.ytimg.com/vi/aaaaaaaaaaa/hqdefault.jpg",
    );
  });

  it("plays on youtube-nocookie.com when Play is clicked, granting media, and says so to onPlay", async () => {
    const onPlay = vi.fn();
    renderWithKernel(<VideoPlaylist items={ITEMS} onPlay={onPlay} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    expect(player().options).toMatchObject({
      host: "https://www.youtube-nocookie.com",
      videoId: "aaaaaaaaaaa",
      playerVars: { autoplay: 1, rel: 0, playsinline: 1 },
    });
    expect(document.cookie).toContain(`${CONSENT_COOKIE}=media`);
    expect(screen.queryByRole("button", { name: "Play First" })).toBeNull();
    player().say(STATE.PLAYING);
    expect(onPlay).toHaveBeenCalledTimes(1);
    expect(row("First").querySelector(".mf-playlist-eq")).not.toBeNull();
  });

  it("rolls on to the next video at the end, moving the highlight, and stops after the last", async () => {
    renderWithKernel(<VideoPlaylist items={ITEMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    player().say(STATE.ENDED);
    expect(player().loaded).toEqual(["bbbbbbbbbbb"]);
    expect(row("Second")).toHaveAttribute("aria-current", "true");
    player().say(STATE.ENDED);
    player().say(STATE.ENDED);
    expect(player().loaded).toEqual(["bbbbbbbbbbb", "ccccccccccc"]);
    expect(row("Third")).toHaveAttribute("aria-current", "true");
  });

  it("stays on a video that ends with Autoplay off, and the switch never restarts what plays", async () => {
    renderWithKernel(<VideoPlaylist items={ITEMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    const autoplay = screen.getByRole("button", { name: "Autoplay" });
    expect(autoplay).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(autoplay);
    expect(autoplay).toHaveAttribute("aria-pressed", "false");
    expect(player().loaded).toEqual([]);
    player().say(STATE.ENDED);
    expect(player().loaded).toEqual([]);
    expect(row("First")).toHaveAttribute("aria-current", "true");
  });

  it("starts with Autoplay off when asked", () => {
    renderWithKernel(<VideoPlaylist items={ITEMS} autoplay={false} />);
    expect(screen.getByRole("button", { name: "Autoplay" })).toHaveAttribute("aria-pressed", "false");
  });

  it("plays a row's video on its click, and Prev and Next wrap around", async () => {
    renderWithKernel(<VideoPlaylist items={ITEMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Previous video" }));
    expect(player().options.videoId).toBe("ccccccccccc");
    expect(row("Third")).toHaveAttribute("aria-current", "true");
    player().ready();
    await userEvent.click(screen.getByRole("button", { name: "Next video" }));
    expect(player().loaded).toEqual(["aaaaaaaaaaa"]);
    await userEvent.click(row("Second"));
    expect(player().loaded).toEqual(["aaaaaaaaaaa", "bbbbbbbbbbb"]);
    expect(FakePlayer.made).toHaveLength(1);
  });

  it("pauses through its handle, takes the bars away on a pause, and goes when it's taken away", async () => {
    const handle = createRef<VideoPlaylistHandle>();
    const { unmount } = renderWithKernel(<VideoPlaylist items={ITEMS} ref={handle} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    player().say(STATE.PLAYING);
    act(() => {
      handle.current?.pause();
    });
    expect(player().paused).toBe(1);
    player().say(STATE.PAUSED);
    expect(row("First").querySelector(".mf-playlist-eq")).toBeNull();
    unmount();
    expect(player().destroyed).toBe(true);
  });

  it("takes the player away and shows the facade again when media is withdrawn (Codex on #127)", async () => {
    renderWithKernel(
      <>
        <VideoPlaylist items={ITEMS} />
        <Withdraw />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    player().say(STATE.PLAYING);
    await userEvent.click(screen.getByRole("button", { name: "Withdraw media" }));
    expect(player().destroyed).toBe(true);
    expect(screen.getByRole("button", { name: "Play First" })).toBeInTheDocument();
    expect(row("First").querySelector(".mf-playlist-eq")).toBeNull();
  });

  it("makes no player when media is withdrawn while YouTube's script loads (Codex on #127)", async () => {
    delete window.YT;
    renderWithKernel(
      <>
        <VideoPlaylist items={ITEMS} />
        <Withdraw />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    await userEvent.click(screen.getByRole("button", { name: "Withdraw media" }));
    youTubeArrives();
    await act(() => Promise.resolve());
    expect(FakePlayer.made).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Play First" })).toBeInTheDocument();
  });

  it("plays the row picked last while YouTube's script loads (Codex on #127)", async () => {
    delete window.YT;
    renderWithKernel(<VideoPlaylist items={ITEMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    await userEvent.click(row("Second"));
    youTubeArrives();
    await act(() => Promise.resolve());
    expect(FakePlayer.made).toHaveLength(1);
    expect(player().options.videoId).toBe("bbbbbbbbbbb");
    expect(player().loaded).toEqual([]);
    expect(row("Second")).toHaveAttribute("aria-current", "true");
  });

  it("keeps the facade after a withdrawal, whatever grants media next (CodeRabbit on #127)", async () => {
    renderWithKernel(
      <>
        <VideoPlaylist items={ITEMS} />
        <Withdraw />
        <Grant />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    await userEvent.click(screen.getByRole("button", { name: "Withdraw media" }));
    await userEvent.click(screen.getByRole("button", { name: "Allow media" }));
    expect(screen.getByRole("button", { name: "Play First" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    expect(FakePlayer.made).toHaveLength(2);
  });

  it("keeps its selection within a list that shrinks (CodeRabbit on #127)", async () => {
    renderWithKernel(<Changing lists={{ "Just one": [{ url: "https://youtu.be/aaaaaaaaaaa", title: "First" }] }} />);
    await userEvent.click(row("Third"));
    player().ready();
    await userEvent.click(screen.getByRole("button", { name: "Just one" }));
    expect(row("First")).toHaveAttribute("aria-current", "true");
    expect(screen.getByText("First", { selector: ".mf-playlist-now" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next video" }));
    expect(player().loaded).toEqual(["aaaaaaaaaaa"]);
  });

  it("keeps the selection it was clamped to when the list grows again (CodeRabbit on #127)", async () => {
    renderWithKernel(
      <Changing lists={{ "Just one": [{ url: "https://youtu.be/aaaaaaaaaaa", title: "First" }], All: ITEMS }} />,
    );
    await userEvent.click(row("Third"));
    await userEvent.click(screen.getByRole("button", { name: "Just one" }));
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    expect(row("First")).toHaveAttribute("aria-current", "true");
    expect(row("Third")).not.toHaveAttribute("aria-current");
  });

  it("forgets a failed load once the list empties, and one that fails after (CodeRabbit on #127)", async () => {
    delete window.YT;
    renderWithKernel(<Changing lists={{ None: [], All: ITEMS }} />);
    const fail = () => {
      act(() => {
        document.head.querySelector(`script[src="${IFRAME_API}"]`)?.dispatchEvent(new Event("error"));
      });
    };
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    fail();
    expect(await screen.findByText(/YouTube's player didn't load/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "None" }));
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.queryByText(/YouTube's player didn't load/)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    await userEvent.click(screen.getByRole("button", { name: "None" }));
    fail();
    await act(() => Promise.resolve());
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    expect(screen.queryByText(/YouTube's player didn't load/)).toBeNull();
  });

  it("lets its player go while the list has no video, and makes a new one after (CodeRabbit on #127)", async () => {
    renderWithKernel(<Changing lists={{ None: [], All: ITEMS }} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    const first = player();
    await userEvent.click(screen.getByRole("button", { name: "None" }));
    expect(first.destroyed).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "All" }));
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    expect(FakePlayer.made).toHaveLength(2);
  });

  it("holds a row picked before the player is ready, and plays it once it is (CodeRabbit on #127)", async () => {
    renderWithKernel(<VideoPlaylist items={ITEMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    await userEvent.click(row("Second"));
    expect(player().loaded).toEqual([]);
    player().ready();
    expect(player().loaded).toEqual(["bbbbbbbbbbb"]);
    await userEvent.click(row("Third"));
    expect(player().loaded).toEqual(["bbbbbbbbbbb", "ccccccccccc"]);
  });

  it("draws nothing for a list with no video it can play", () => {
    const { container } = renderWithKernel(<VideoPlaylist items={[{ url: "nope", title: "Nope" }]} />);
    expect(container.querySelector(".mf-playlist")).toBeNull();
  });

  it("says so when YouTube's player can't load, and offers the video on YouTube", async () => {
    delete window.YT;
    renderWithKernel(<VideoPlaylist items={ITEMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Play First" }));
    const script = document.head.querySelector<HTMLScriptElement>(`script[src="${IFRAME_API}"]`);
    act(() => {
      script?.dispatchEvent(new Event("error"));
    });
    expect(await screen.findByRole("status")).toHaveTextContent("YouTube's player didn't load.");
    expect(screen.getByRole("link", { name: "YouTube" })).toHaveAttribute(
      "href",
      "https://www.youtube.com/watch?v=aaaaaaaaaaa",
    );
    expect(screen.getByRole("button", { name: "Play First" })).toBeInTheDocument();
  });
});

describe("loadYouTube", () => {
  it("adds YouTube's script once, and answers the API once it says it's ready", async () => {
    delete window.YT;
    const first = loadYouTube();
    const second = loadYouTube();
    const scripts = document.head.querySelectorAll(`script[src="${IFRAME_API}"]`);
    expect(scripts).toHaveLength(1);
    window.YT = { Player: FakePlayer, PlayerState: STATE };
    window.onYouTubeIframeAPIReady?.();
    await expect(first).resolves.toBe(window.YT);
    await expect(second).resolves.toBe(window.YT);
    await expect(loadYouTube()).resolves.toBe(window.YT);
    scripts[0]?.remove();
  });
});
