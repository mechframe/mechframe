/**
 * featured's web (`dev plans/contracts/featured.md` §7): the words the board uses,
 * each row's state, the tabs, the strip and the pills, Move up and down and a drag,
 * the picker, the dates and Paste links dialogs, the save bar's words, Discard and
 * the conflict, the Dashboard's card and its "Nothing", and `useFeatured`. Every
 * answer comes from a fetch that answers by method and path.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "@/kernel/testing";

import type { AdminPlacement, AdminSlot, FullSlot, Row } from "../../web/api";
import { changesOf, datesWords, day, dayTime, intro, liveLine, oneOf, rowOf, singular, statesOf, stripOf } from "../../web/api";
import { isoOf, localOf } from "../../web/components/DatesDialog";
import { keyOf } from "../../web/components/SlotSettings";
import featured from "../../web/module.web";
import { useFeatured } from "../../web/public";
import { cardOf } from "../../web/widgets/SpotlightCard";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const HOUR = 3600_000;
const now = Date.now();
const at = (hours: number) => new Date(now + hours * HOUR).toISOString();
const TRACK = "discography.track";
const TYPES = [{ type: TRACK, label: "Tracks" }];
const ids = { catalyst: "11111111-1111-4111-8111-111111111111", gather: "21111111-1111-4111-8111-111111111111", hook: "31111111-1111-4111-8111-111111111111" };

function ref(id: string, title: string, live = true) {
  return { type: TRACK, id, title, line: "Unified Vibration, Vibrant Mindz", image: "https://files.test/uv.jpg", path: live ? `/music/uv/${id}` : null, live };
}

function placement(id: string, title: string, state: AdminPlacement["state"], starts: string | null = null, ends: string | null = null): AdminPlacement {
  return { id: `p-${id}`, item: { type: TRACK, id }, ref: ref(id, title), removed: false, link: null, starts_at: starts, ends_at: ends, state };
}

const SPOTLIGHT: FullSlot = {
  key: "spotlight",
  label: "Spotlight",
  accepts: [TRACK],
  kinds: [],
  on_dashboard: true,
  version: 4,
  counts: { live: 1, scheduled: 1 },
  now: { title: "Catalyst (full album)", starts_at: at(-120), ends_at: at(48) },
  items: [placement(ids.catalyst, "Catalyst (full album)", "live", at(-120), at(48)), placement(ids.gather, "Gather Around", "next", at(48))],
};
const VIDEOS: FullSlot = {
  key: "videos",
  label: "Videos",
  accepts: ["youtube"],
  kinds: [
    { key: "music-video", label: "Music video" },
    { key: "poetry", label: "Poetry" },
  ],
  on_dashboard: false,
  version: 2,
  counts: { live: 1, scheduled: 0 },
  now: { title: "Boom Bap Piff", starts_at: null, ends_at: null },
  items: [
    {
      id: "p-video",
      item: null,
      ref: null,
      removed: false,
      link: { url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", video_id: "dQw4w9WgXcQ", title: "Boom Bap Piff", kind: "music-video" },
      starts_at: null,
      ends_at: null,
      state: "live",
    },
  ],
};
const summary = (full: FullSlot): AdminSlot => ({ key: full.key, label: full.label, accepts: full.accepts, kinds: full.kinds, on_dashboard: full.on_dashboard, version: full.version, counts: full.counts, now: full.now });
const SLOTS = { items: [summary(SPOTLIGHT), summary(VIDEOS)], types: TYPES };

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = {
        "GET /api/featured/admin/slots": { status: 200, body: SLOTS },
        "GET /api/featured/admin/slots/spotlight": { status: 200, body: SPOTLIGHT },
        "GET /api/featured/admin/slots/videos": { status: 200, body: VIDEOS },
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
  return { status, body: { type: `urn:mechframe:problem:${code}`, title: "Refused", status, detail: "Someone saved this player since you opened it.", code, ...extra } };
}

const editor = testUser({ roles: ["member", "editor"], second_factor: true, permissions: ["featured.placement.manage"] });
const admin = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["featured.placement.manage", "featured.slot.manage"] });

async function players(session = editor, path = "/admin/featured", list = "The Spotlight, in order") {
  renderApp({ path, modules: [featured], session });
  return screen.findByRole("list", { name: list });
}

// --- the words --------------------------------------------------------------------------------

describe("featured's words", () => {
  it("says a row's dates as the board does", () => {
    const starts = at(-120);
    const ends = at(48);
    expect(datesWords(starts, ends)).toBe(`${day(starts)} to ${day(ends)}`);
    expect(datesWords(at(48), null)).toBe(`Starts ${dayTime(at(48))}`);
    expect(datesWords(at(-48), null)).toBe("No end date");
    expect(datesWords(null, ends)).toBe(`Until ${day(ends)}`);
    expect(datesWords(null, null)).toBe("Always");
  });

  it("names one of a type, and what a tab takes", () => {
    expect([singular("Tracks"), singular("Stories"), singular("Press"), oneOf("Albums"), oneOf("Tracks")]).toEqual(["track", "story", "press", "an album", "a track"]);
    expect(intro(SPOTLIGHT, TYPES)).toBe("Tracks, in order. Give a track dates to schedule it.");
    expect(intro(VIDEOS, TYPES)).toBe("YouTube links, in order. Paste one or several links at once; titles fill in from YouTube. Give each video one of this player's kinds.");
    expect(intro({ accepts: [TRACK, "discography.release", "youtube"], kinds: [] }, [...TYPES, { type: "discography.release", label: "Albums" }])).toBe(
      "Tracks, albums and YouTube links, in order. Give a track dates to schedule it. Paste one or several links at once; titles fill in from YouTube.",
    );
  });

  it("works out each row's state as the server does, the soonest to start next", () => {
    const rows: Row[] = [
      { ...rowOf(SPOTLIGHT.items[0] as AdminPlacement), starts_at: null, ends_at: null },
      { ...rowOf(SPOTLIGHT.items[0] as AdminPlacement), ends_at: new Date(now - 1).toISOString() },
      { ...rowOf(SPOTLIGHT.items[1] as AdminPlacement), starts_at: at(72) },
      { ...rowOf(SPOTLIGHT.items[1] as AdminPlacement), starts_at: at(24) },
      { ...rowOf(SPOTLIGHT.items[0] as AdminPlacement), ref: ref(ids.hook, "A draft", false) },
      { ...rowOf(SPOTLIGHT.items[0] as AdminPlacement), ref: null, removed: true },
      { ...rowOf(SPOTLIGHT.items[0] as AdminPlacement), ref: null, removed: false },
    ];
    expect(statesOf(rows, now)).toEqual(["live", "ended", "scheduled", "next", "hidden", "removed", "hidden"]);
  });

  it("says what changed, what's added first", () => {
    const saved = SPOTLIGHT.items.map(rowOf);
    const added: Row = { ...rowOf(placement(ids.hook, "Hook It Up", "live")), id: null, key: "new-1" };
    const rows = [saved[0] as Row, { ...(saved[1] as Row), starts_at: at(30) }, added];
    expect(changesOf(saved, rows)).toEqual(["Hook It Up added", "Gather Around scheduled"]);
    expect(changesOf(saved, [saved[1] as Row, saved[0] as Row])).toEqual(["The order changed"]);
    expect(changesOf(saved, [saved[1] as Row])).toEqual(["Catalyst (full album) removed"]);
    expect(changesOf(saved, saved)).toEqual([]);
  });

  it("writes the strip and the card's line", () => {
    expect(stripOf(SPOTLIGHT)).toEqual({ now: `Catalyst (full album), until ${day(at(48))}`, next: `Up next: Gather Around on ${day(at(48))}` });
    expect(stripOf({ ...SPOTLIGHT, items: [] })).toEqual({ now: "Nothing live", next: "Nothing scheduled" });
    const video = VIDEOS.items[0] as AdminPlacement;
    const two = { ...VIDEOS, items: [video, { ...video, id: "p-2", link: { url: "https://www.youtube.com/watch?v=abcdefghijk", video_id: "abcdefghijk", title: "All Natural", kind: null } }] };
    expect(stripOf(two).now).toBe("Boom Bap Piff, then All Natural");
    expect(liveLine(summary(SPOTLIGHT))).toBe(`Live since ${day(at(-120))}, with 1 more queued`);
    expect(liveLine(summary(VIDEOS))).toBe("Live now");
    expect(cardOf(summary(SPOTLIGHT))).toMatchObject({ label: "Now in the spotlight", value: "Catalyst (full album)", state: { tone: "success", label: "Live" }, link: { label: "Players", to: "/admin/featured?slot=spotlight" } });
    expect(cardOf({ ...summary(SPOTLIGHT), now: null, counts: { live: 0, scheduled: 0 } })).toMatchObject({ value: "Nothing", line: "The Spotlight is empty on the site", state: { tone: "warning", label: "Not live" } });
  });

  it("makes keys from words, and a local time and back", () => {
    expect(keyOf("  Music Vidéo!! ")).toBe("music-video");
    const local = localOf("2026-11-17T05:00:00.000Z");
    expect(isoOf(local)).toBe("2026-11-17T05:00:00.000Z");
    expect(isoOf("")).toBeNull();
  });
});

// --- Players ----------------------------------------------------------------------------------

describe("Players", () => {
  it("draws the tabs with their counts, the strip, the rows and their pills", async () => {
    routed({});
    const list = await players();
    expect(screen.getByRole("heading", { level: 1, name: "Players" })).toBeInTheDocument();
    expect(screen.getByText("Choose what plays in the homepage's players, in what order, and when.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open homepage/ })).toHaveAttribute("href", "/");
    expect(screen.getByRole("tab", { name: "Spotlight 2" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Videos 1" })).toBeInTheDocument();
    expect(screen.getByText(`Catalyst (full album), until ${day(at(48))}`)).toBeInTheDocument();
    expect(screen.getByText(`Up next: Gather Around on ${day(at(48))}`)).toBeInTheDocument();
    const rows = within(list).getAllByRole("listitem");
    expect(within(rows[0] as HTMLElement).getByText("Live now")).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByText("Up next")).toBeInTheDocument();
    expect(within(rows[1] as HTMLElement).getByRole("button", { name: `Dates of Gather Around: Starts ${dayTime(at(48))}` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add track" })).toBeInTheDocument();
    // An editor makes no players.
    expect(screen.queryByRole("button", { name: "New player" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Spotlight settings" })).toBeNull();
  });

  it("shows a video with YouTube's mark and its kind, and loads nothing from YouTube", async () => {
    routed({});
    const list = await players(editor, "/admin/featured?slot=videos", "The Videos, in order");
    expect(within(list).getByRole("img", { name: "YouTube" })).toBeInTheDocument();
    expect(within(list).getByRole("combobox", { name: "Kind of Boom Bap Piff" })).toHaveValue("music-video");
    expect(screen.getByRole("button", { name: "Paste links" })).toBeInTheDocument();
    for (const image of document.querySelectorAll("img")) expect(image.getAttribute("src") ?? "").not.toMatch(/youtube|ytimg/);
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("moves rows with the buttons and by dragging, and the save bar says so; Discard puts them back", async () => {
    routed({});
    const list = await players();
    await userEvent.click(within(list).getByRole("button", { name: "Move Gather Around up" }));
    const titles = () => within(list).getAllByRole("listitem").map((row) => row.querySelector(".mf-featured-title")?.textContent);
    expect(titles()).toEqual(["Gather Around", "Catalyst (full album)"]);
    expect(screen.getByRole("region", { name: "Changes not saved" })).toHaveTextContent("1 change not saved: The order changed");
    const [first, second] = within(list).getAllByRole("listitem") as [HTMLElement, HTMLElement];
    fireEvent.dragStart(second, { dataTransfer: { effectAllowed: "", setData: vi.fn() } });
    fireEvent.dragOver(first);
    fireEvent.drop(first);
    expect(titles()).toEqual(["Catalyst (full album)", "Gather Around"]);
    expect(screen.queryByRole("region", { name: "Changes not saved" })).toBeNull();
    await userEvent.click(within(list).getByRole("button", { name: "Remove Catalyst (full album)" }));
    expect(screen.getByRole("region", { name: "Changes not saved" })).toHaveTextContent("Catalyst (full album) removed");
    await userEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(titles()).toEqual(["Catalyst (full album)", "Gather Around"]);
  });

  it("adds a track from the picker, dates a row, and saves the list live", async () => {
    const saved: FullSlot = { ...SPOTLIGHT, version: 5 };
    const sent = routed({
      "GET /api/featured/admin/slots/spotlight/pick": (request) => {
        const query = new URL(request.url).searchParams;
        return query.get("cursor")
          ? { status: 200, body: { items: [ref("41111111-1111-4111-8111-111111111111", "Pray For You", false)], next_cursor: null } }
          : { status: 200, body: { items: [ref(ids.catalyst, "Catalyst (full album)"), ref(ids.hook, "Hook It Up")], next_cursor: "page-2" } };
      },
      "PUT /api/featured/admin/slots/spotlight/placements": { status: 200, body: saved },
    });
    const list = await players();
    await userEvent.click(screen.getByRole("button", { name: "Add track" }));
    const picker = await screen.findByRole("dialog", { name: "Add track" });
    expect(await within(picker).findByRole("button", { name: "Catalyst (full album) is in the list" })).toBeDisabled();
    await userEvent.click(within(picker).getByRole("button", { name: "Load more" }));
    expect(await within(picker).findByText(/Not on the site yet/)).toBeInTheDocument();
    await userEvent.type(within(picker).getByRole("searchbox", { name: "Search tracks" }), "hook");
    await userEvent.click(within(picker).getByRole("button", { name: "Search" }));
    await waitFor(() => {
      expect(sent.some((request) => new URL(request.url).searchParams.get("q") === "hook")).toBe(true);
    });
    await userEvent.click(await within(picker).findByRole("button", { name: "Add Hook It Up" }));
    await userEvent.click(within(picker).getByRole("button", { name: "Done" }));
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);

    await userEvent.click(within(list).getByRole("button", { name: /^Dates of Gather Around/ }));
    const dates = await screen.findByRole("dialog", { name: "Dates of Gather Around" });
    fireEvent.change(within(dates).getByLabelText("Ends", { exact: false }), { target: { value: localOf(at(10)) } });
    expect(within(dates).getByText("The end has to be after the start.")).toBeInTheDocument();
    fireEvent.change(within(dates).getByLabelText("Ends", { exact: false }), { target: { value: localOf(at(96)) } });
    await userEvent.click(within(dates).getByRole("button", { name: "Set the dates" }));

    const bar = screen.getByRole("region", { name: "Changes not saved" });
    expect(bar).toHaveTextContent("2 changes not saved: Hook It Up added, Gather Around scheduled");
    await userEvent.click(within(bar).getByRole("button", { name: "Save and go live" }));
    await waitFor(() => {
      expect(screen.queryByRole("region", { name: "Changes not saved" })).toBeNull();
    });
    const put = sent.find((request) => request.method === "PUT");
    const body = (await put?.json()) as { version: number; items: Record<string, unknown>[] };
    expect(body.version).toBe(4);
    expect(body.items).toEqual([
      { id: `p-${ids.catalyst}`, ref: { type: TRACK, id: ids.catalyst }, starts_at: at(-120), ends_at: at(48) },
      { id: `p-${ids.gather}`, ref: { type: TRACK, id: ids.gather }, starts_at: at(48), ends_at: isoOf(localOf(at(96))) },
      { ref: { type: TRACK, id: ids.hook }, starts_at: null, ends_at: null },
    ]);
    expect(await screen.findByText("Saved. It's live on the site.")).toBeInTheDocument();
  });

  it("holds the list still while its save is on its way, so no edit is lost (Codex on #157)", async () => {
    let answer: (value: Answer) => void = () => undefined;
    routed({
      "PUT /api/featured/admin/slots/spotlight/placements": () =>
        new Promise<Answer>((resolve) => {
          answer = resolve;
        }),
    });
    const list = await players();
    await userEvent.click(within(list).getByRole("button", { name: "Move Gather Around up" }));
    await userEvent.click(screen.getByRole("button", { name: "Save and go live" }));
    await waitFor(() => {
      expect(within(list).getByRole("button", { name: "Remove Gather Around" })).toBeDisabled();
    });
    expect(within(list).getByRole("button", { name: "Move Catalyst (full album) up" })).toBeDisabled();
    expect(within(list).getByRole("button", { name: /^Dates of Gather Around/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Add track" })).toBeDisabled();
    expect(within(list).getAllByRole("listitem")[0]).toHaveAttribute("draggable", "false");
    answer({ status: 200, body: { ...SPOTLIGHT, version: 5, items: [SPOTLIGHT.items[1], SPOTLIGHT.items[0]] } });
    await waitFor(() => {
      expect(within(list).getByRole("button", { name: "Remove Gather Around" })).toBeEnabled();
    });
    expect(screen.queryByRole("region", { name: "Changes not saved" })).toBeNull();
  });

  it("asks theirs or mine when someone saved first, and saves mine at their version", async () => {
    const theirs: FullSlot = { ...SPOTLIGHT, version: 6, items: [SPOTLIGHT.items[1] as AdminPlacement] };
    let puts = 0;
    const sent = routed({
      "PUT /api/featured/admin/slots/spotlight/placements": () => {
        puts += 1;
        return puts === 1 ? problem(409, "featured.changed", { slot: theirs }) : { status: 200, body: { ...theirs, version: 7 } };
      },
    });
    const list = await players();
    await userEvent.click(within(list).getByRole("button", { name: "Move Gather Around up" }));
    await userEvent.click(screen.getByRole("button", { name: "Save and go live" }));
    const asked = await screen.findByRole("group", { name: "Saved by someone else since you opened it" });
    expect(within(asked).getByText("The Spotlight's list")).toBeInTheDocument();
    await userEvent.click(within(asked).getByRole("radio", { name: /Keep mine/ }));
    await userEvent.click(within(asked).getByRole("button", { name: /Save with these choices/ }));
    await waitFor(() => {
      expect(puts).toBe(2);
    });
    const again = (await sent.filter((request) => request.method === "PUT")[1]?.json()) as { version: number; items: { id?: string }[] };
    expect(again.version).toBe(6);
    // Catalyst was removed by them: it's added again as new.
    expect(again.items.map((each) => each.id ?? null)).toEqual([`p-${ids.gather}`, null]);
  });

  it("says why a save was refused, naming the row", async () => {
    routed({
      "PUT /api/featured/admin/slots/videos/placements": problem(422, "featured.no_title", { detail: "A video needs a title.", errors: { "items.0.link.title": ["A video needs a title of 1 to 200 characters."] } }),
    });
    const list = await players(editor, "/admin/featured?slot=videos", "The Videos, in order");
    await userEvent.selectOptions(within(list).getByRole("combobox", { name: "Kind of Boom Bap Piff" }), "poetry");
    expect(screen.getByRole("region", { name: "Changes not saved" })).toHaveTextContent("Boom Bap Piff's kind changed");
    await userEvent.click(screen.getByRole("button", { name: "Save and go live" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Boom Bap Piff: A video needs a title of 1 to 200 characters.");
  });

  it("pastes links, titled by YouTube, with the ones that aren't refused and a title to type", async () => {
    routed({
      "POST /api/featured/admin/youtube": {
        status: 200,
        body: {
          items: [
            { url: "https://www.youtube.com/watch?v=abcdefghijk", video_id: "abcdefghijk", title: "Hook It Up (Official Video)" },
            { url: "https://www.youtube.com/watch?v=bcdefghijkl", video_id: "bcdefghijkl", title: null },
          ],
          refused: [{ url: "https://vimeo.com/1", reason: "featured.not_youtube" }],
        },
      },
    });
    await players(editor, "/admin/featured?slot=videos", "The Videos, in order");
    await userEvent.click(screen.getByRole("button", { name: "Paste links" }));
    const dialog = await screen.findByRole("dialog", { name: "Paste links" });
    await userEvent.type(within(dialog).getByRole("textbox", { name: "YouTube links" }), "https://youtu.be/abcdefghijk https://youtu.be/bcdefghijkl https://vimeo.com/1");
    await userEvent.click(within(dialog).getByRole("button", { name: "Read the links" }));
    expect(await within(dialog).findByText("https://vimeo.com/1")).toBeInTheDocument();
    expect(within(dialog).getByRole("textbox", { name: "Title of youtu.be/abcdefghijk" })).toHaveValue("Hook It Up (Official Video)");
    const add = within(dialog).getByRole("button", { name: "Add 2 videos" });
    expect(add).toBeDisabled();
    await userEvent.type(within(dialog).getByRole("textbox", { name: "Title of youtu.be/bcdefghijkl" }), "Real Talk");
    await userEvent.click(add);
    const list = screen.getByRole("list", { name: "The Videos, in order" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByRole("region", { name: "Changes not saved" })).toHaveTextContent("2 changes not saved: Hook It Up (Official Video) added, Real Talk added");
  });

  it("lets an admin make a player, and says when there are none", async () => {
    const made: FullSlot = { ...SPOTLIGHT, key: "releases", label: "Releases", version: 1, items: [], now: null, counts: { live: 0, scheduled: 0 }, on_dashboard: false };
    const sent = routed({
      "GET /api/featured/admin/slots": { status: 200, body: { items: [], types: TYPES } },
      "POST /api/featured/admin/slots": { status: 201, body: made },
    });
    renderApp({ path: "/admin/featured", modules: [featured], session: admin });
    expect(await screen.findByText("No players yet")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Make the first player" }));
    const dialog = await screen.findByRole("dialog", { name: "New player" });
    await userEvent.type(within(dialog).getByRole("textbox", { name: "Name" }), "Releases");
    expect(within(dialog).getByRole("textbox", { name: "Key" })).toHaveValue("releases");
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Tracks" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Make the player" }));
    await waitFor(() => {
      expect(sent.some((request) => request.method === "POST")).toBe(true);
    });
    const body = (await sent.find((request) => request.method === "POST")?.json()) as Record<string, unknown>;
    expect(body).toEqual({ key: "releases", label: "Releases", accepts: [TRACK], kinds: [], on_dashboard: false });
  });

  it("puts Players under the sidebar's Homepage for those who place things", async () => {
    routed({ "GET /api/kernel/admin/dashboard": { status: 200, body: { attention: [], setup: [] } } });
    renderApp({ path: "/admin/featured", modules: [featured], session: editor });
    expect(await screen.findByRole("link", { name: "Players" })).toHaveAttribute("href", "/admin/featured");
  });
});

// --- useFeatured -------------------------------------------------------------------------------

describe("useFeatured", () => {
  it("reads a player's live list", async () => {
    routed({
      "GET /api/featured/slots/spotlight": {
        status: 200,
        body: { key: "spotlight", label: "Spotlight", kinds: [], items: [{ id: "p-1", ref: { type: TRACK, id: ids.catalyst, title: "Catalyst (full album)", line: "Catalyst", image: null, path: "/music/catalyst" }, link: null }] },
      },
    });
    function Spotlight() {
      const found = useFeatured("spotlight");
      return <p>{found.data?.items.map((each) => each.ref?.title).join(", ") ?? "…"}</p>;
    }
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Spotlight />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Catalyst (full album)")).toBeInTheDocument();
  });
});
