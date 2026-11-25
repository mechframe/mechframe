/**
 * The player's parts as a page draws them (`web/public.ts`;
 * `dev plans/contracts/audio-player.md` §2 and §7): the play button, the
 * Spotlight-style bar, the docked bar with its queue and volume, the waveform's
 * keys, SoundCloud's credit and consent, a YouTube player taking turns, the
 * settings the player reads, a page move, and the Settings section. Each test
 * has its own player on fake outputs; every answer comes from a fetch that
 * answers by method and path.
 */
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CONSENT_COOKIE } from "@/kernel";
import { renderApp, renderWithKernel, testUser } from "@/kernel/testing";
import { Equalizer, PlayButton, PlayerBar, PlayerDock, Waveform, useExclusive, type PlayerItem } from "@/modules/audio-player/public";

import { PlayerContext } from "../../web/hooks";
import audioPlayer from "../../web/module.web";
import type { Output, OutputEvents, OutputFactory } from "../../web/outputs";
import { createPlayer, type Player } from "../../web/store";

type Answer = { status: number; body?: unknown };

function routed(answers: Record<string, Answer>) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) => {
      sent.push(request);
      const found = answers[`${request.method} ${new URL(request.url).pathname}`];
      if (!found) return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve(
        new Response(found.body === undefined ? null : JSON.stringify(found.body), {
          status: found.status,
          headers: { "content-type": "application/json" },
        }),
      );
    }),
  );
  return sent;
}

const SETTINGS = { "GET /api/audio-player/settings": { status: 200, body: { autoplay_next: true, count_after_seconds: 30 } } };

type Fake = Output & { events: OutputEvents; calls: string[]; seeks: number[] };

function testPlayer() {
  const made: Record<"file" | "soundcloud", Fake[]> = { file: [], soundcloud: [] };
  const factory =
    (kind: "file" | "soundcloud"): OutputFactory =>
    (events) => {
      const output: Fake = {
        events,
        calls: [],
        seeks: [],
        load: () => output.calls.push("load"),
        play: () => output.calls.push("play"),
        pause: () => output.calls.push("pause"),
        seek: (ms) => output.seeks.push(ms),
        volume: () => output.calls.push("volume"),
        stop: () => output.calls.push("stop"),
      };
      made[kind].push(output);
      return output;
    };
  const player = createPlayer({ file: factory("file"), soundcloud: factory("soundcloud") });
  const file = (): Fake => {
    const found = made.file[0];
    if (!found) throw new Error("Nothing played yet.");
    return found;
  };
  return { player, made, file };
}

/** An item, where `undefined` takes a default away. */
type Overrides = { [K in keyof PlayerItem]?: PlayerItem[K] | undefined };

function item(name: string, overrides: Overrides = {}): PlayerItem {
  return {
    key: `discography.track:${name}`,
    title: name,
    line: "Unified Vibration, Vibrant Mindz",
    stream_url: `https://cdn.test/${name}.mp3`,
    duration_ms: 180_000,
    peaks: Array.from({ length: 1000 }, (_, at) => at % 256),
    ...overrides,
  } as PlayerItem;
}

const QUEUE = [item("Gather Around"), item("Unified"), item("Vibrate")];
const CATALYST = item("Catalyst (full album)", {
  stream_url: undefined,
  peaks: undefined,
  soundcloud_url: "https://soundcloud.com/petrodestroys/sets/catalyst",
});

function draw(ui: React.ReactElement, player: Player, path = "/") {
  return renderWithKernel(<PlayerContext value={player}>{ui}</PlayerContext>, { path });
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = `${CONSENT_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax; Secure`;
});

describe("the play button", () => {
  it("plays its item, and says Pause while it plays", async () => {
    routed(SETTINGS);
    const { player, file } = testPlayer();
    draw(<PlayButton queue={QUEUE} index={1} label="02 Unified" />, player);
    await userEvent.click(screen.getByRole("button", { name: "Play 02 Unified" }));
    expect(player.snapshot()).toMatchObject({ index: 1, page: "/" });
    act(() => {
      file().events.playing();
    });
    await userEvent.click(screen.getByRole("button", { name: "Pause 02 Unified" }));
    expect(player.snapshot().state).toBe("paused");
    expect(screen.getByRole("button", { name: "Play 02 Unified" })).toBeInTheDocument();
  });
});

describe("the bar", () => {
  it("moves through its queue before it plays, then plays the one shown", async () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    draw(<PlayerBar queue={QUEUE} label="Spotlight single" previousLabel="Previous spotlight track" nextLabel="Next spotlight track" />, player);
    const bar = screen.getByRole("region", { name: "Spotlight single" });
    expect(within(bar).getByText("Gather Around")).toBeInTheDocument();
    await userEvent.click(within(bar).getByRole("button", { name: "Next spotlight track" }));
    expect(within(bar).getByText("Unified")).toBeInTheDocument();
    expect(player.snapshot().state).toBe("idle");
    await userEvent.click(within(bar).getByRole("button", { name: "Play Unified" }));
    expect(player.snapshot()).toMatchObject({ index: 1, state: "loading" });
    await userEvent.click(within(bar).getByRole("button", { name: "Next spotlight track" }));
    expect(player.snapshot().index).toBe(2);
    expect(within(bar).getByText("Vibrate")).toBeInTheDocument();
  });

  it("seeks with the waveform's keys once its item plays, and reads the time out", async () => {
    routed(SETTINGS);
    const { player, file } = testPlayer();
    draw(<PlayerBar queue={QUEUE} label="Spotlight single" />, player);
    expect(screen.queryByRole("slider")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Play Gather Around" }));
    act(() => {
      file().events.playing();
      file().events.time(72_000, 220_000);
    });
    const seek = screen.getByRole("slider", { name: "Seek" });
    expect(seek).toHaveAttribute("aria-valuetext", "1:12 of 3:40");
    seek.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(file().seeks).toEqual([77_000]);
    await userEvent.keyboard("{Home}");
    expect(file().seeks.at(-1)).toBe(0);
  });

  it("credits SoundCloud, and its Play is the visitor's consent to media", async () => {
    routed(SETTINGS);
    const { player, made } = testPlayer();
    draw(<PlayerBar queue={[CATALYST]} label="Spotlight single" />, player);
    const credit = screen.getByRole("link", { name: "on SoundCloud (opens SoundCloud)" });
    expect(credit).toHaveAttribute("href", "https://soundcloud.com/petrodestroys/sets/catalyst");
    expect(document.cookie).not.toContain(`${CONSENT_COOKIE}=media`);
    await userEvent.click(screen.getByRole("button", { name: "Play Catalyst (full album)" }));
    expect(document.cookie).toContain(`${CONSENT_COOKIE}=media`);
    expect(made.soundcloud[0]?.calls.filter((call) => call !== "volume")).toEqual(["load", "play"]);
  });

  it("plays SoundCloud on the first press whichever of two players is pressed (CodeRabbit on #149)", async () => {
    routed(SETTINGS);
    const { player, made } = testPlayer();
    draw(
      <>
        <PlayButton queue={[CATALYST]} label="Catalyst, first" />
        <PlayButton queue={[CATALYST]} label="Catalyst, second" />
      </>,
      player,
    );
    await userEvent.click(screen.getByRole("button", { name: "Play Catalyst, first" }));
    expect(made.soundcloud[0]?.calls.filter((call) => call !== "volume")).toEqual(["load", "play"]);
  });

  it("says when a track can't play", async () => {
    routed(SETTINGS);
    const { player, file } = testPlayer();
    draw(<PlayerBar queue={QUEUE} label="Spotlight single" />, player);
    await userEvent.click(screen.getByRole("button", { name: "Play Gather Around" }));
    act(() => {
      file().events.failed();
    });
    expect(screen.getByText("This track can’t play right now.")).toBeInTheDocument();
  });
});

describe("the dock", () => {
  it("shows its queue's first until something plays, then what plays, with the count", async () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    draw(<PlayerDock queue={QUEUE} label="Player" />, player);
    const dock = screen.getByRole("region", { name: "Player" });
    expect(within(dock).getByText("Track 1 of 3")).toBeInTheDocument();
    await userEvent.click(within(dock).getByRole("button", { name: "Next track" }));
    expect(player.snapshot().index).toBe(1);
    expect(within(dock).getByText("Track 2 of 3")).toBeInTheDocument();
  });

  it("opens its queue to play any of it, and closes it with Escape", async () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    draw(<PlayerDock queue={QUEUE} label="Player" />, player);
    const queue = screen.getByRole("button", { name: "Queue" });
    await userEvent.click(queue);
    expect(queue).toHaveAttribute("aria-expanded", "true");
    const list = screen.getByRole("list", { name: "Queue" });
    await userEvent.click(within(list).getByRole("button", { name: "Play Vibrate" }));
    expect(player.snapshot().index).toBe(2);
    expect(within(list).getByRole("button", { name: "Play Vibrate" })).toHaveAttribute("aria-current", "true");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("list", { name: "Queue" })).toBeNull();
  });

  it("gives focus back to Queue or Volume when Escape closes a panel holding it (CodeRabbit on #149)", async () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    draw(<PlayerDock queue={QUEUE} label="Player" />, player);
    const queue = screen.getByRole("button", { name: "Queue" });
    await userEvent.click(queue);
    within(screen.getByRole("list", { name: "Queue" })).getByRole("button", { name: "Play Unified" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(queue).toHaveFocus();
    const volume = screen.getByRole("button", { name: "Volume" });
    await userEvent.click(volume);
    screen.getByRole("slider", { name: "Volume" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(volume).toHaveFocus();
    // With focus outside the panel, Escape closes it and leaves focus where it is.
    await userEvent.click(queue);
    screen.getByRole("button", { name: "Next track" }).focus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("list", { name: "Queue" })).toBeNull();
    expect(screen.getByRole("button", { name: "Next track" })).toHaveFocus();
  });

  it("sets the volume from its slider", async () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    draw(<PlayerDock queue={QUEUE} label="Player" />, player);
    await userEvent.click(screen.getByRole("button", { name: "Volume" }));
    const volume = screen.getByRole("slider", { name: "Volume" });
    expect(volume).toHaveValue("100");
    fireEvent.change(volume, { target: { value: "40" } });
    expect(player.snapshot().volume).toBeCloseTo(0.4);
    expect(volume).toHaveValue("40");
  });
});

describe("the waveform", () => {
  it("is only a picture for an item that isn't playing", () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    const { container } = draw(<Waveform item={CATALYST} bars={40} />, player);
    expect(screen.queryByRole("slider")).toBeNull();
    // A made-up shape for a link with no peaks, the same each time it's drawn.
    const heights = () => Array.from(container.querySelectorAll(".mf-wave-rest rect")).map((rect) => rect.getAttribute("height"));
    expect(heights()).toHaveLength(40);
    const first = heights();
    expect(new Set(first).size).toBeGreaterThan(5);
    const again = draw(<Waveform item={CATALYST} bars={40} />, player);
    expect(Array.from(again.container.querySelectorAll(".mf-wave-rest rect")).map((rect) => rect.getAttribute("height"))).toEqual(first);
  });
});

describe("one thing at a time", () => {
  function Video({ paused }: { paused: () => void }) {
    const held = useRef(paused);
    const claim = useExclusive(() => {
      held.current();
    });
    return (
      <button type="button" onClick={claim}>
        Start the video
      </button>
    );
  }

  it("pauses the video as audio starts, and the audio as the video starts", async () => {
    routed(SETTINGS);
    const { player, file } = testPlayer();
    const paused = vi.fn();
    draw(
      <>
        <Video paused={paused} />
        <PlayButton queue={QUEUE} label="Gather Around" />
      </>,
      player,
    );
    await userEvent.click(screen.getByRole("button", { name: "Play Gather Around" }));
    expect(paused).toHaveBeenCalledTimes(1);
    act(() => {
      file().events.playing();
    });
    await userEvent.click(screen.getByRole("button", { name: "Start the video" }));
    expect(player.snapshot().state).toBe("paused");
    expect(paused).toHaveBeenCalledTimes(1);
  });
});

describe("what the player reads and where it plays", () => {
  it("takes autoplay_next from the settings route", async () => {
    routed({ "GET /api/audio-player/settings": { status: 200, body: { autoplay_next: false, count_after_seconds: 30 } } });
    const { player, file } = testPlayer();
    draw(<PlayButton queue={QUEUE} label="Gather Around" />, player);
    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });
    await userEvent.click(screen.getByRole("button", { name: "Play Gather Around" }));
    await waitFor(() => {
      act(() => {
        file().events.ended();
      });
      expect(player.snapshot()).toMatchObject({ index: 0, state: "paused" });
    });
  });

  it("stops when the visitor moves to another page", async () => {
    routed(SETTINGS);
    const { player } = testPlayer();
    const { router } = draw(<PlayButton queue={QUEUE} label="Gather Around" />, player, "/music/unified");
    await userEvent.click(screen.getByRole("button", { name: "Play Gather Around" }));
    expect(player.snapshot().page).toBe("/music/unified");
    await act(async () => {
      await router.navigate("/music/unified#credits");
    });
    expect(player.snapshot().state).toBe("loading");
    await act(async () => {
      await router.navigate("/videos");
    });
    await waitFor(() => {
      expect(player.snapshot().state).toBe("idle");
    });
  });

  it("draws the row's bars, moving only while it plays", () => {
    const { container, rerender } = renderWithKernel(<Equalizer playing={false} />);
    expect(container.querySelector(".mf-player-eq")).not.toHaveClass("mf-player-eq-on");
    rerender(<Equalizer playing />);
    expect(container.querySelector(".mf-player-eq")).toHaveClass("mf-player-eq-on");
  });
});

describe("the Settings section", () => {
  const reader = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["kernel.settings.manage"] });
  const form = (version: number, values: Record<string, unknown>): Answer => ({ status: 200, body: { version, values } });
  const empty = { status: 200, body: { items: [], next_cursor: null, people: {} } };

  it("edits both settings, and the Site tab's Save sends them", async () => {
    const sent = routed({
      "GET /api/kernel/admin/settings/kernel.site": form(1, { description: "", kind: "Organization", logo: "", card_image: "", same_as: [], llms_summary: "", ai_crawlers: "allow" }),
      "GET /api/kernel/admin/settings/kernel.auth": form(0, { sign_up_mode: "closed" }),
      "GET /api/kernel/admin/settings/audio-player": form(2, { autoplay_next: true, count_after_seconds: 30 }),
      "GET /api/kernel/admin/settings/kernel.site/history": empty,
      "GET /api/kernel/admin/settings/kernel.auth/history": empty,
      "GET /api/kernel/admin/settings/audio-player/history": empty,
      "PUT /api/kernel/admin/settings/audio-player": { status: 200, body: { version: 3, changed: ["autoplay_next", "count_after_seconds"], merged: [] } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings", modules: [audioPlayer], session: reader });
    const autoplay = await screen.findByRole("switch", { name: "Play the next track when one ends" });
    expect(autoplay).toHaveAttribute("aria-checked", "true");
    await user.click(autoplay);
    const seconds = screen.getByRole("spinbutton", { name: "Count a play after (seconds)" });
    await user.clear(seconds);
    await user.type(seconds, "45");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(sent.filter((request) => request.method === "PUT")).toHaveLength(1);
    });
    const put = sent.find((request) => request.method === "PUT");
    expect(await put?.json()).toEqual({ version: 2, changes: { autoplay_next: false, count_after_seconds: 45 } });
  });
});
