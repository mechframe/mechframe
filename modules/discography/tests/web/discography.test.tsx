/**
 * discography's web (`dev plans/contracts/discography.md`): the library, a
 * release and a track on the site, and the admin's Albums, album editor, Tracks
 * and Credits boards. Every answer comes from a fetch that answers by method and
 * path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "@/kernel/testing";

import type { AdminRelease, AdminTrack, FullRelease, FullTrack, LiveRelease, LiveTrack, ReleaseCard, TrackAudio } from "../../web/api";
import { clock, msOf } from "../../web/api";
import { changed, mineOf, releaseBody, releaseFormOf } from "../../web/editing";
import discography from "../../web/module.web";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const ID = "11111111-1111-4111-8111-111111111111";
const ONE = `/api/discography/admin/releases/${ID}`;
const T1 = "21111111-1111-4111-8111-111111111111";
const T2 = "31111111-1111-4111-8111-111111111111";
const ARTIST = "41111111-1111-4111-8111-111111111111";
const PRODUCER = "51111111-1111-4111-8111-111111111111";
const ROLES = {
  items: [
    { id: ARTIST, name: "Artist", credits: 2 },
    { id: PRODUCER, name: "Produced by", credits: 0 },
  ],
};
const FILES = "https://files.mechframe.test/discography/stream";

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = {
        "GET /api/discography/admin/roles": { status: 200, body: ROLES },
        "GET /api/discography/links": { status: 200, body: { items: [] } },
        ...answers,
      };
      const found = all[`${request.method} ${new URL(request.url).pathname}`];
      if (!found) throw new TypeError("Failed to fetch");
      const answer = typeof found === "function" ? await found(request) : found;
      const type = answer.status >= 400 ? "application/problem+json" : "application/json";
      return new Response(answer.body === undefined ? null : JSON.stringify(answer.body), { status: answer.status, headers: { "content-type": type } });
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function problem(status: number, code: string, extra: Record<string, unknown> = {}): Answer {
  return { status, body: { type: `urn:mechframe:problem:${code}`, title: "Refused", status, detail: "Refused.", code, ...extra } };
}

async function json(request: Request): Promise<Record<string, unknown>> {
  return (await request.json()) as Record<string, unknown>;
}

function audio(overrides: Partial<TrackAudio> = {}): TrackAudio {
  return {
    state: "ready",
    plays_from: "upload",
    percent: 100,
    error: null,
    error_words: null,
    master_name: "Night Drive.wav",
    master_bytes: 1000,
    soundcloud_url: null,
    soundcloud_kind: null,
    duration_ms: 222_000,
    stream_url: `${FILES}/abc.mp3`,
    ...overrides,
  };
}

function track(overrides: Partial<AdminTrack> = {}): AdminTrack {
  return {
    id: T1,
    version: 1,
    release_id: ID,
    release_title: "Unified Vibration",
    number: 1,
    title: "Gather Around",
    slug: "gather-around",
    explicit: false,
    audio: audio(),
    has_lyrics: false,
    credit_count: 1,
    ...overrides,
  };
}

function fullTrack(overrides: Partial<FullTrack> = {}): FullTrack {
  return { ...track(), lyrics: null, credits: [], peaks: null, path: "/music/unified-vibration/gather-around", ...overrides };
}

function full(overrides: Partial<FullRelease> = {}): FullRelease {
  return {
    id: ID,
    version: 1,
    title: "Unified Vibration",
    slug: "unified-vibration",
    kind: "album",
    year: 2024,
    artist_line: "Vibrant Mindz",
    cover: null,
    status: "draft",
    publish_at: null,
    published_at: null,
    track_count: 2,
    unplayable: 1,
    tracklist_to_come: false,
    updated_at: "2026-11-22T12:00:00+00:00",
    credit_line: "Produced by Vibrant Mindz.",
    summary: "",
    back_cover: null,
    tracks: [track(), track({ id: T2, number: 2, title: "Pray For You", slug: "pray-for-you", audio: audio({ state: "none", plays_from: null, stream_url: null, duration_ms: null, master_name: null }) })],
    credits: [{ role_id: ARTIST, role: "Artist", person_id: "61111111-1111-4111-8111-111111111111", name: "Vibrant Mindz", profile: "collective" }],
    links: [],
    moves: [],
    path: "/music/unified-vibration",
    ...overrides,
  };
}

function listed(release: FullRelease): AdminRelease {
  const { id, version, title, slug, kind, year, artist_line, cover, status, publish_at, published_at, track_count, unplayable, tracklist_to_come, updated_at } = release;
  return { id, version, title, slug, kind, year, artist_line, cover, status, publish_at, published_at, track_count, unplayable, tracklist_to_come, updated_at };
}

function card(overrides: Partial<ReleaseCard> = {}): ReleaseCard {
  return {
    title: "Unified Vibration",
    slug: "unified-vibration",
    kind: "album",
    year: 2024,
    artist_line: "Vibrant Mindz",
    credit_line: "Produced by Vibrant Mindz.",
    summary: "",
    cover: null,
    explicit: true,
    track_count: 15,
    tracklist_to_come: false,
    path: "/music/unified-vibration",
    published_at: "2026-11-20T12:00:00+00:00",
    ...overrides,
  };
}

const LIVE: LiveRelease = {
  ...card(),
  back_cover: null,
  updated_at: "2026-11-21T12:00:00+00:00",
  tracks: [
    {
      title: "Gather Around",
      slug: "gather-around",
      number: 1,
      duration_ms: 222_000,
      explicit: false,
      plays_from: "upload",
      stream_url: `${FILES}/abc.mp3`,
      soundcloud_url: null,
      soundcloud_kind: null,
      has_lyrics: true,
      path: "/music/unified-vibration/gather-around",
    },
    {
      title: "Boom Bap Piff",
      slug: "boom-bap-piff",
      number: 2,
      duration_ms: null,
      explicit: true,
      plays_from: "soundcloud",
      stream_url: null,
      soundcloud_url: "https://soundcloud.com/vibrantmindz/boom-bap-piff",
      soundcloud_kind: "track",
      has_lyrics: false,
      path: "/music/unified-vibration/boom-bap-piff",
    },
  ],
  credits: [{ role: "Produced by", name: "Vibrant Mindz" }],
  links: [{ platform: "spotify", label: "Spotify", url: "https://open.spotify.com/album/1" }],
};

const editor = testUser({ roles: ["member", "editor"], second_factor: true, permissions: ["discography.release.manage", "media.image.upload"] });
const admin = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["discography.release.manage", "kernel.settings.manage"] });

describe("the site's music", () => {
  it("lists the live releases with their label, and the artist's links", async () => {
    routed({
      "GET /api/discography/releases": { status: 200, body: { items: [card(), card({ title: "Catalyst", slug: "catalyst", explicit: false, tracklist_to_come: true, path: "/music/catalyst" })], next_cursor: null } },
      "GET /api/discography/links": { status: 200, body: { items: [{ platform: "soundcloud", label: "SoundCloud", url: "https://soundcloud.com/vibrantmindz" }] } },
    });
    renderApp({ path: "/music", modules: [discography] });

    expect(await screen.findByRole("heading", { level: 2, name: "Unified Vibration" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Catalyst" })).toHaveAttribute("href", "/music/catalyst");
    expect(screen.getAllByText("Parental Advisory")).toHaveLength(1);
    expect(screen.getByText("The tracklist is to come.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "SoundCloud" })).toHaveAttribute("href", "https://soundcloud.com/vibrantmindz");
  });

  it("plays an upload in the browser's own player, loading nothing until it's pressed, and links a SoundCloud track", async () => {
    routed({ "GET /api/discography/releases/unified-vibration": { status: 200, body: LIVE } });
    renderApp({ path: "/music/unified-vibration", modules: [discography] });

    expect(await screen.findByRole("heading", { level: 1, name: "Unified Vibration" })).toBeInTheDocument();
    const player = document.querySelector("audio");
    expect(player).toHaveAttribute("preload", "none");
    expect(player).toHaveAttribute("src", `${FILES}/abc.mp3`);
    expect(player).toHaveAttribute("controls");
    expect(screen.getByRole("link", { name: /Listen on SoundCloud/ })).toHaveAttribute("href", "https://soundcloud.com/vibrantmindz/boom-bap-piff");
    expect(screen.getByText("3:42")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Spotify" })).toBeInTheDocument();
    expect(screen.getByText("Produced by: Vibrant Mindz")).toBeInTheDocument();
    expect(document.querySelector("iframe")).toBeNull(); // nothing loads from SoundCloud
  });

  it("moves on from an address a release left, and answers 404 for one it never had", async () => {
    routed({
      "GET /api/discography/releases/old": { status: 200, body: { moved: "/music/unified-vibration" } },
      "GET /api/discography/releases/unified-vibration": { status: 200, body: LIVE },
    });
    const { router } = renderApp({ path: "/music/old?from=mail", modules: [discography] });
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/music/unified-vibration");
    });
    expect(router.state.location.search).toBe("?from=mail");
  });

  it("shows a track's lyrics, verse by verse, and its release", async () => {
    const shown: LiveTrack = {
      ...(LIVE.tracks[0] as LiveRelease["tracks"][number]),
      release: { title: "Unified Vibration", slug: "unified-vibration", kind: "album", path: "/music/unified-vibration" },
      artist_line: "Vibrant Mindz",
      cover: null,
      peaks: null,
      lyrics: "Gather around\nall of you\n\nSecond verse",
      credits: [],
    };
    routed({ "GET /api/discography/releases/unified-vibration/tracks/gather-around": { status: 200, body: shown } });
    renderApp({ path: "/music/unified-vibration/gather-around", modules: [discography] });

    expect(await screen.findByRole("heading", { level: 1, name: "Gather Around" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Lyrics" })).toBeInTheDocument();
    expect(screen.getByText("Second verse")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Unified Vibration" })[0]).toHaveAttribute("href", "/music/unified-vibration");
  });
});

describe("the Albums board", () => {
  it("says which track can't play, badges each release, and keeps the settings to admins", async () => {
    routed({ "GET /api/discography/admin/releases": { status: 200, body: { items: [listed(full({ status: "published" })), listed(full({ id: T2, title: "Catalyst", tracklist_to_come: true, unplayable: 0 }))] } } });
    renderApp({ path: "/admin/music", modules: [discography], session: editor });

    expect(await screen.findByText("A track on Unified Vibration can't play")).toBeInTheDocument();
    expect(screen.getByText("1 track can't play")).toBeInTheDocument();
    expect(screen.getByText("Tracklist to come")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit Catalyst" })).toHaveAttribute("href", `/admin/music/${T2}`);
    expect(screen.getByRole("link", { name: "Preview Unified Vibration on the site" })).toHaveAttribute("href", "/music/unified-vibration");
    expect(screen.queryByRole("switch", { name: "Show lyrics on release pages" })).toBeNull();
    expect(screen.getByText(/An admin changes these/)).toBeInTheDocument();
  });

  it("saves the music settings for an admin", async () => {
    const sent = routed({
      "GET /api/discography/admin/releases": { status: 200, body: { items: [] } },
      "GET /api/kernel/admin/settings/discography": { status: 200, body: { id: "discography", version: 1, values: { stream_bitrate_kbps: 256, show_explicit_badge: true, show_lyrics: true }, fields: [] } },
      "PUT /api/kernel/admin/settings/discography": { status: 200, body: { version: 2, changed: ["show_lyrics"], merged: [] } },
    });
    renderApp({ path: "/admin/music", modules: [discography], session: admin });

    await userEvent.click(await screen.findByRole("switch", { name: "Show lyrics on release pages" }));
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PUT")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PUT") as Request)).toEqual({ version: 1, changes: { show_lyrics: false } });
  });

  it("makes a new release as a draft and opens its editor", async () => {
    const sent = routed({
      "GET /api/discography/admin/releases": { status: 200, body: { items: [] } },
      "POST /api/discography/admin/releases": { status: 201, body: full({ title: "Catalyst", kind: "ep" }) },
      [`GET ${ONE}`]: { status: 200, body: full({ title: "Catalyst", kind: "ep" }) },
    });
    const { router } = renderApp({ path: "/admin/music", modules: [discography], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "New release" }));
    const dialog = within(await screen.findByRole("dialog", { name: "New release" }));
    await userEvent.type(dialog.getByRole("textbox", { name: "Title" }), "Catalyst");
    await userEvent.selectOptions(dialog.getByRole("combobox", { name: "Kind" }), "ep");
    await userEvent.click(dialog.getByRole("button", { name: "Make the draft" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/admin/music/${ID}`);
    });
    expect(await json(sent.find((each) => each.method === "POST") as Request)).toEqual({ title: "Catalyst", kind: "ep" });
  });
});

describe("the album editor", () => {
  it("refuses a file over 60 MB before anything is sent, with the FLAC words", async () => {
    const sent = routed({ [`GET ${ONE}`]: { status: 200, body: full() } });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    const input = await screen.findByLabelText("Upload tracks", { selector: "input" });
    const huge = new File(["x"], "Huge.wav", { type: "audio/wav" });
    Object.defineProperty(huge, "size", { value: 60 * 1024 * 1024 + 1 });
    await userEvent.upload(input, huge);

    expect(await screen.findByText(/Huge\.wav: The file is over 60 MB\. Export it as FLAC/)).toBeInTheDocument();
    expect(sent.some((each) => each.url.includes("/tracks/upload"))).toBe(false);
  });

  it("uploads each file as a track and reads the release again", async () => {
    let reads = 0;
    const sent = routed({
      [`GET ${ONE}`]: () => {
        reads += 1;
        return { status: 200, body: reads === 1 ? full() : full({ tracks: [...full().tracks, track({ id: "71111111-1111-4111-8111-111111111111", number: 3, title: "New One", audio: audio({ state: "processing", plays_from: null, percent: 10, stream_url: null }) })] }) };
      },
      [`POST ${ONE}/tracks/upload`]: { status: 201, body: fullTrack({ title: "New One" }) },
    });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    const input = await screen.findByLabelText("Upload tracks", { selector: "input" });
    await userEvent.upload(input, new File(["RIFF"], "New One.wav", { type: "audio/wav" }));
    expect(await screen.findByText("New One")).toBeInTheDocument();
    expect(screen.getByText(/Making the stream file 10%/)).toBeInTheDocument();
    const upload = sent.find((each) => each.url.endsWith("/tracks/upload")) as Request;
    expect(upload.headers.get("content-type")).toMatch(/^multipart\/form-data; boundary=/);
  });

  it("saves the tracks' new order with the release", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: { status: 200, body: full({ version: 2, tracks: [...full().tracks].reverse() }) },
    });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Move Pray For You up" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Save" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 1, track_ids: [T2, T1] });
  });

  it("says a track can't play, and sends someone to give it audio", async () => {
    routed({ [`GET ${ONE}`]: { status: 200, body: full() } });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });
    expect(await screen.findByText("Pray For You can't play")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add audio" })).toHaveAttribute("href", `/admin/music/tracks?track=${T2}`);
  });

  it("asks field by field when someone saved first, and saves again with the choice", async () => {
    let patches = 0;
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: async (request) => {
        patches += 1;
        if (patches === 1) return problem(409, "discography.changed", { release: full({ title: "Their title", summary: "Theirs.", version: 2 }) });
        const body = await json(request);
        return { status: 200, body: full({ title: typeof body.title === "string" ? body.title : "Their title", summary: "Theirs.", version: 3 }) };
      },
    });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "My title");
    await userEvent.click(screen.getAllByRole("button", { name: "Save" })[0] as HTMLElement);
    expect(await screen.findByText("Their title")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Keep mine" }));
    await userEvent.click(screen.getByRole("button", { name: /Save with these choices/ }));
    await waitFor(() => {
      expect(patches).toBe(2);
    });
    expect(await json(sent.filter((each) => each.method === "PATCH")[1] as Request)).toEqual({ version: 2, title: "My title" });
    expect(screen.getByRole("textbox", { name: "Summary" })).toHaveValue("Theirs.");
  });

  it("keeps a field typed back to its saved value while the save waits, and asks about it", async () => {
    let answer: (value: Answer) => void = () => undefined;
    let patches = 0;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full({ title: "A" }) },
      [`PATCH ${ONE}`]: () => {
        patches += 1;
        return patches === 1
          ? new Promise<Answer>((resolve) => {
              answer = resolve;
            })
          : { status: 200, body: full({ title: "A", version: 3 }) };
      },
    });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "B");
    await userEvent.click(screen.getAllByRole("button", { name: "Save" })[0] as HTMLElement);
    await waitFor(() => {
      expect(patches).toBe(1);
    });
    await userEvent.clear(title);
    await userEvent.type(title, "A");
    answer(problem(409, "discography.changed", { release: full({ title: "B", version: 2 }) }));

    expect(await screen.findByRole("radio", { name: "Keep mine" })).toBeInTheDocument();
    expect(title).toHaveValue("A");
  });

  it("adds a SoundCloud track, and says why a link that isn't one is refused", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`POST ${ONE}/tracks`]: problem(422, "discography.not_soundcloud", { errors: { soundcloud_url: ["That isn't a SoundCloud track or playlist."] } }),
    });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Add SoundCloud link" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Add a SoundCloud link" }));
    await userEvent.type(dialog.getByRole("textbox", { name: "Title" }), "Catalyst");
    await userEvent.type(dialog.getByRole("textbox", { name: /SoundCloud link/ }), "https://soundcloud.com/petrodestroys");
    await userEvent.click(dialog.getByRole("button", { name: "Add the track" }));
    expect(await dialog.findByText("That isn't a SoundCloud track or playlist.")).toBeInTheDocument();
    expect(await json(sent.find((each) => each.method === "POST") as Request)).toEqual({ title: "Catalyst", soundcloud_url: "https://soundcloud.com/petrodestroys" });
  });

  it("publishes on a release day it's given", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`POST ${ONE}/publish`]: { status: 200, body: full({ status: "scheduled", publish_at: "2026-12-01T17:00:00+00:00" }) },
    });
    renderApp({ path: `/admin/music/${ID}`, modules: [discography], session: editor });

    await userEvent.click(await screen.findByRole("radio", { name: "On its release day" }));
    await userEvent.type(screen.getByLabelText("Goes live at"), "2026-12-01T12:00");
    await userEvent.click(screen.getByRole("button", { name: "Schedule" }));
    expect(await screen.findAllByText("Scheduled")).not.toHaveLength(0);
    const body = await json(sent.find((each) => each.url.endsWith("/publish")) as Request);
    expect(typeof body.at).toBe("string");
  });
});

describe("the Tracks board", () => {
  const LIST = "GET /api/discography/admin/tracks";
  const TRACK = `/api/discography/admin/tracks/${T2}`;
  const silent = fullTrack({ id: T2, number: 2, title: "Pray For You", slug: "pray-for-you", audio: audio({ state: "none", plays_from: null, stream_url: null, duration_ms: null, master_name: null }) });

  it("filters, picks a track from the address, and saves its lyrics and credits", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [track(), silent], next_cursor: null, total: 2, releases: 1 } },
      [`GET ${TRACK}`]: { status: 200, body: silent },
      [`PATCH ${TRACK}`]: { status: 200, body: fullTrack({ ...silent, version: 2, lyrics: "Pray for you", has_lyrics: true }) },
    });
    renderApp({ path: `/admin/music/tracks?track=${T2}`, modules: [discography], session: editor });

    expect(await screen.findByRole("button", { name: "Pray For You", pressed: true })).toBeInTheDocument();
    expect(screen.getByText("2 tracks on 1 release.")).toBeInTheDocument();
    await userEvent.type(await screen.findByRole("textbox", { name: "Lyrics" }), "Pray for you");
    await userEvent.click(screen.getByRole("button", { name: "Add a credit" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Name" }), "Moya Brown");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({
      version: 1,
      lyrics: "Pray for you",
      credits: [{ role_id: ARTIST, name: "Moya Brown" }],
    });

    await userEvent.click(screen.getByRole("button", { name: "Can't play", pressed: false }));
    await waitFor(() => {
      expect(sent.some((each) => new URL(each.url).searchParams.get("show") === "cant_play")).toBe(true);
    });
  });

  it("refuses a replacement over 60 MB before it's sent", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [silent], next_cursor: null, total: 1, releases: 1 } },
      [`GET ${TRACK}`]: { status: 200, body: silent },
    });
    renderApp({ path: `/admin/music/tracks?track=${T2}`, modules: [discography], session: editor });

    const input = await screen.findByLabelText("Upload a file", { selector: "input" });
    const huge = new File(["x"], "Huge.wav", { type: "audio/wav" });
    Object.defineProperty(huge, "size", { value: 61 * 1024 * 1024 });
    await userEvent.upload(input, huge);
    await waitFor(() => {
      expect(screen.getAllByText(/Export it as FLAC/).length).toBeGreaterThan(0);
    });
    expect(sent.some((each) => each.method === "PUT")).toBe(false);
  });

  it("asks before it takes theirs when a track's save crossed someone else's", async () => {
    routed({
      [LIST]: { status: 200, body: { items: [silent], next_cursor: null, total: 1, releases: 1 } },
      [`GET ${TRACK}`]: { status: 200, body: silent },
      [`PATCH ${TRACK}`]: problem(409, "discography.changed", { track: { ...silent, title: "Pray", version: 2 } }),
    });
    renderApp({ path: `/admin/music/tracks?track=${T2}`, modules: [discography], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "Pray For You (live)");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("radio", { name: "Keep mine" })).toBeInTheDocument();
    expect(screen.getByText("Pray")).toBeInTheDocument();
  });
});

describe("the Credits board", () => {
  const PEOPLE = {
    items: [
      { id: "81111111-1111-4111-8111-111111111111", version: 1, name: "petro", profile: "unlinked", roster_profile_id: null, credited_for: "Artist, Catalyst", credits: 1 },
      { id: "91111111-1111-4111-8111-111111111111", version: 1, name: "Vibrant Mindz", profile: "collective", roster_profile_id: null, credited_for: "Artist and producer, Unified Vibration", credits: 2 },
    ],
    unlinked: 1,
  };

  it("names who isn't linked, and saves a name's profile state", async () => {
    const sent = routed({
      "GET /api/discography/admin/people": { status: 200, body: PEOPLE },
      "PATCH /api/discography/admin/people/81111111-1111-4111-8111-111111111111": { status: 200, body: { ...PEOPLE, unlinked: 0 } },
    });
    renderApp({ path: "/admin/music/credits", modules: [discography], session: editor });

    expect(await screen.findByText("“petro” isn't linked to a profile")).toBeInTheDocument();
    expect(screen.getByText("The collective")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Edit petro" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Edit petro" }));
    await userEvent.selectOptions(dialog.getByRole("combobox", { name: "Profile" }), "not_member");
    await userEvent.click(dialog.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 1, profile: "not_member" });
  });

  it("keeps a role credits name, and saves the list in its new order", async () => {
    const sent = routed({
      "GET /api/discography/admin/people": { status: 200, body: PEOPLE },
      "PUT /api/discography/admin/roles": { status: 200, body: { items: [ROLES.items[1], ROLES.items[0]] } },
    });
    renderApp({ path: "/admin/music/credits", modules: [discography], session: editor });

    expect(await screen.findByText("2 credits")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Edit the roles" }));
    expect(dialog.getByRole("button", { name: "Remove Artist" })).toBeDisabled();
    await userEvent.click(dialog.getByRole("button", { name: "Move Produced by up" }));
    await userEvent.click(dialog.getByRole("button", { name: "Save the roles" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PUT")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PUT") as Request)).toEqual({
      items: [
        { id: PRODUCER, name: "Produced by" },
        { id: ARTIST, name: "Artist" },
      ],
    });
  });
});

describe("the forms' rules", () => {
  it("reads and writes a length as minutes and seconds", () => {
    expect(clock(222_000)).toBe("3:42");
    expect(clock(3_725_000)).toBe("1:02:05");
    expect(clock(null)).toBe("--");
    expect(msOf("3:42")).toBe(222_000);
    expect(msOf("1:02:05")).toBe(3_725_000);
    expect(msOf("3:75")).toBeNull();
    expect(msOf("about 3 minutes")).toBeNull();
  });

  it("sends a year as a number, covers by id and credits without blank rows", () => {
    const form = { ...releaseFormOf(full()), year: "2025", credits: [{ role_id: ARTIST, name: " petro " }, { role_id: ARTIST, name: " " }], links: [" https://open.spotify.com/album/1 ", ""] };
    expect(releaseBody(form, ["year", "credits", "links", "cover"])).toEqual({
      year: 2025,
      credits: [{ role_id: ARTIST, name: "petro" }],
      links: ["https://open.spotify.com/album/1"],
      cover_id: null,
    });
  });

  it("counts a field typed back to its saved value after a save went as the person's", () => {
    const base = releaseFormOf(full({ title: "A" }));
    const sent = { ...base, title: "B" };
    const now = { ...base, title: "A" };
    expect(changed(now, base)).toEqual([]);
    expect(mineOf(now, base, sent)).toEqual(["title"]);
  });
});
