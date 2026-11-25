/**
 * discography's public surface (`web/public.ts`, decision 0057): what a site's
 * own Music and Release pages import as `@/modules/discography/public` to draw
 * the library. Each read is the API's; every answer comes from a fetch that
 * answers by method and path.
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithKernel } from "@/kernel/testing";
import { KIND_WORDS, clock, isMoved, pathOf, playerItem, playerQueue, releaseLine, useArtistLinks, useRelease, useReleases, type ReleaseCard } from "@/modules/discography/public";

import type { LiveRelease, TrackLine } from "../../web/api";

type Answer = { status: number; body?: unknown };

function routed(answers: Record<string, Answer | ((request: Request) => Answer)>) {
  const sent: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) => {
      const url = new URL(request.url);
      sent.push(url);
      const found = answers[`${request.method} ${url.pathname}`];
      if (!found) return Promise.reject(new TypeError("Failed to fetch"));
      const answer = typeof found === "function" ? found(request) : found;
      return Promise.resolve(
        new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
          status: answer.status,
          headers: { "content-type": answer.status >= 400 ? "application/problem+json" : "application/json" },
        }),
      );
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function card(overrides: Partial<ReleaseCard> = {}): ReleaseCard {
  return {
    title: "Catalyst",
    slug: "catalyst",
    kind: "album",
    year: 2026,
    artist_line: "petro and J Tone",
    credit_line: "",
    summary: "",
    cover: null,
    explicit: false,
    track_count: 1,
    tracklist_to_come: true,
    path: "/music/catalyst",
    published_at: "2026-11-20T12:00:00+00:00",
    ...overrides,
  };
}

function Releases() {
  const releases = useReleases({ kind: "album" });
  const cards = releases.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <>
      <ul>
        {cards.map((each) => (
          <li key={each.slug}>{`${each.title}: ${releaseLine(each)}`}</li>
        ))}
      </ul>
      {releases.hasNextPage ? (
        <button type="button" onClick={() => void releases.fetchNextPage()}>
          More
        </button>
      ) : null}
    </>
  );
}

function Moved() {
  const found = useRelease("old");
  if (!found.data) return null;
  return <p>{isMoved(found.data) ? `Now at ${found.data.moved}` : found.data.title}</p>;
}

function Everywhere() {
  const links = useArtistLinks();
  return <p>{(links.data?.items ?? []).map((each) => each.label).join(", ")}</p>;
}

describe("discography's public surface", () => {
  it("reads the live releases a page at a time, of one kind", async () => {
    const sent = routed({
      "GET /api/discography/releases": (request) =>
        new URL(request.url).searchParams.get("cursor")
          ? { status: 200, body: { items: [card({ title: "Unified Vibration", slug: "unified-vibration", year: 2024, track_count: 15, tracklist_to_come: false })], next_cursor: null } }
          : { status: 200, body: { items: [card()], next_cursor: "c1" } },
    });
    renderWithKernel(<Releases />);
    expect(await screen.findByText("Catalyst: Album, 2026. 1 track for now")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "More" }));
    expect(await screen.findByText("Unified Vibration: Album, 2024. 15 tracks")).toBeInTheDocument();
    expect(sent.every((each) => each.searchParams.get("kind") === "album")).toBe(true);
  });

  it("says where a release moved, and reads the artist's links", async () => {
    routed({
      "GET /api/discography/releases/old": { status: 200, body: { moved: "/music/catalyst" } },
      "GET /api/discography/links": { status: 200, body: { items: [{ platform: "spotify", label: "Spotify", url: "https://open.spotify.com/artist/1" }] } },
    });
    renderWithKernel(
      <>
        <Moved />
        <Everywhere />
      </>,
    );
    expect(await screen.findByText("Now at /music/catalyst")).toBeInTheDocument();
    expect(await screen.findByText("Spotify")).toBeInTheDocument();
  });

  it("gives the words and addresses a page needs", () => {
    expect(pathOf("catalyst")).toBe("/music/catalyst");
    expect(pathOf("catalyst", "night-drive")).toBe("/music/catalyst/night-drive");
    expect(KIND_WORDS.ep).toBe("EP");
    expect(clock(61_000)).toBe("1:01");
  });
});

const UPLOAD = "71111111-1111-4111-8111-111111111111";
const LINKED = "81111111-1111-4111-8111-111111111111";

function line(overrides: Partial<TrackLine> = {}): TrackLine {
  return {
    id: UPLOAD,
    title: "Night Drive",
    slug: "night-drive",
    number: 1,
    duration_ms: 222_000,
    explicit: false,
    plays_from: "upload",
    stream_url: "https://files.mechframe.test/discography/stream/a.mp3",
    soundcloud_url: "https://soundcloud.com/petrodestroys/night-drive",
    soundcloud_kind: "track",
    has_lyrics: false,
    path: "/music/catalyst/night-drive",
    ...overrides,
  };
}

const COVER = { id: "91111111-1111-4111-8111-111111111111", url: "https://files.mechframe.test/c.webp", srcset: "", width: 600, height: 600, alt: "Catalyst's cover", decorative: false };

describe("discography's tracks as the player's items (0.1.1)", () => {
  it("makes a track an item: its stream once made, its line, cover and page", () => {
    const item = playerItem(line(), { ...card(), cover: COVER });
    expect(item).toMatchObject({
      key: `discography.track:${UPLOAD}`,
      title: "Night Drive",
      line: "Catalyst, petro and J Tone",
      cover: { src: COVER.url, alt: "Catalyst's cover" },
      stream_url: "https://files.mechframe.test/discography/stream/a.mp3",
      duration_ms: 222_000,
      path: "/music/catalyst/night-drive",
    });
    expect(item).not.toHaveProperty("soundcloud_url"); // the stream plays, so no credit is shown
    expect(item).not.toHaveProperty("peaks"); // a tracklist has none: the player makes a shape up
  });

  it("plays a SoundCloud track through the widget, with no cover or length it hasn't got", () => {
    const item = playerItem(line({ id: LINKED, plays_from: "soundcloud", stream_url: null, duration_ms: null }), { ...card(), artist_line: "" });
    expect(item).toMatchObject({ key: `discography.track:${LINKED}`, line: "Catalyst", soundcloud_url: "https://soundcloud.com/petrodestroys/night-drive" });
    expect(item).not.toHaveProperty("stream_url");
    expect(item).not.toHaveProperty("cover");
    expect(item).not.toHaveProperty("duration_ms");
  });

  it("takes a track page's peaks, and a decorative cover without words", () => {
    const peaks = [0, 128, 255];
    const item = playerItem({ ...line(), peaks }, { ...card(), cover: { ...COVER, decorative: true } });
    expect(item.peaks).toEqual(peaks);
    expect(item.cover?.alt).toBe("");
  });

  it("counts a play through discography's route, and lets a failure go", async () => {
    const sent = routed({ [`POST /api/discography/tracks/${UPLOAD}/plays`]: { status: 204 } });
    playerItem(line(), card()).count?.();
    await waitFor(() => {
      expect(sent.map((each) => each.pathname)).toEqual([`/api/discography/tracks/${UPLOAD}/plays`]);
    });
    routed({});
    expect(() => playerItem(line(), card()).count?.()).not.toThrow(); // a network failure says nothing
  });

  it("makes a release's playable tracks its queue, in order", () => {
    const release: LiveRelease = {
      ...card(),
      back_cover: null,
      updated_at: "2026-11-21T12:00:00+00:00",
      tracks: [line(), line({ id: LINKED, title: "Catalyst", slug: "catalyst", number: 2, plays_from: "soundcloud", stream_url: null })],
      credits: [],
      links: [],
    };
    expect(playerQueue(release).map((each) => [each.key, each.title])).toEqual([
      [`discography.track:${UPLOAD}`, "Night Drive"],
      [`discography.track:${LINKED}`, "Catalyst"],
    ]);
  });
});
