/**
 * portfolio's web (`dev plans/contracts/portfolio.md` §2, §7): Collective ›
 * Portfolio with its note, chips, tiles and editor, for staff who manage and
 * for an artist; the Art page with its chips as addresses, the grid and a
 * piece's panel; and the Settings section. Every answer comes from a fetch
 * that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "@/kernel/testing";

import { joined, lineOf, type AdminPiece, type Card, type LivePiece } from "../../web/api";
import { blank, problems, slugFor } from "../../web/editing";
import portfolio from "../../web/module.web";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const LIST = "GET /api/portfolio/admin/pieces";
const ID = "11111111-1111-4111-8111-111111111111";
const ONE = `/api/portfolio/admin/pieces/${ID}`;
const ME = "00000000-0000-4000-8000-000000000001";
const PICTURE = {
  id: "51111111-1111-4111-8111-111111111111",
  url: "https://files.test/media/harbour.png",
  srcset: "https://files.test/media/harbour.png 1200w",
  width: 1200,
  height: 900,
  alt: "Boats at dusk",
  decorative: false,
};
const DISCIPLINES = {
  items: [
    { id: "21111111-1111-4111-8111-111111111111", slug: "paintings", label: "Paintings", position: 0, pieces: 3 },
    { id: "31111111-1111-4111-8111-111111111111", slug: "graphic-design", label: "Graphic design", position: 1, pieces: 5 },
    { id: "41111111-1111-4111-8111-111111111111", slug: "video", label: "Video", position: 2, pieces: 0 },
  ],
};
const ARTISTS = { items: [{ id: ME, name: "Big Haas" }, { id: "61111111-1111-4111-8111-111111111111", name: "petro" }] };

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = {
        "GET /api/portfolio/admin/disciplines": { status: 200, body: DISCIPLINES },
        "GET /api/portfolio/admin/artists": { status: 200, body: ARTISTS },
        "GET /api/portfolio/art": { status: 200, body: { lead: "", commission_link: "" } },
        "GET /api/portfolio/disciplines": { status: 200, body: { items: [] } },
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
  return { status, body: { type: `urn:mechframe:problem:${code}`, title: "Refused", status, detail: "Someone saved this piece since you opened it. Here is how it reads now.", code, ...extra } };
}

function piece(overrides: Partial<AdminPiece> = {}): AdminPiece {
  return {
    id: ID,
    title: "Harbour at dusk",
    slug: "harbour-at-dusk",
    discipline: { slug: "paintings", label: "Paintings" },
    artist: { id: ME, name: "Big Haas" },
    year: 2025,
    about: "Oil on canvas.",
    image_id: PICTURE.id,
    picture: PICTURE,
    video: null,
    status: "draft",
    publish_at: null,
    published_at: null,
    version: 1,
    updated_at: "2026-11-28T12:00:00+00:00",
    path: null,
    ...overrides,
  };
}

function card(overrides: Partial<Card> = {}): Card {
  return {
    id: ID,
    title: "Harbour at dusk",
    slug: "harbour-at-dusk",
    discipline: { slug: "paintings", label: "Paintings" },
    artist: "petro",
    year: 2025,
    picture: PICTURE,
    has_video: false,
    path: "/art/piece/harbour-at-dusk",
    ...overrides,
  };
}

const editor = testUser({
  name: "Big Haas",
  roles: ["member", "editor"],
  second_factor: true,
  permissions: ["portfolio.piece.add", "portfolio.piece.manage", "kernel.taxonomy.manage", "media.image.upload"],
});
const artist = testUser({
  id: "71111111-1111-4111-8111-111111111111",
  name: "J Tone",
  roles: ["member", "artist"],
  second_factor: true,
  permissions: ["portfolio.piece.add", "media.image.upload"],
});

async function json(request: Request): Promise<Record<string, unknown>> {
  return (await request.json()) as Record<string, unknown>;
}

describe("the helpers", () => {
  it("joins the disciplines as the board's lead says them", () => {
    expect(joined(["Paintings", "Graphic design", "Animation", "Video"])).toBe("Paintings, graphic design, animation and video");
    expect(joined(["Paintings"])).toBe("Paintings");
    expect(joined([])).toBe("");
  });

  it("says a piece's line, leaving out what it hasn't got", () => {
    expect(lineOf(card())).toBe("Paintings, by petro, 2025");
    expect(lineOf(card({ artist: null, year: null }))).toBe("Paintings");
  });

  it("checks a piece before a save, as the server would", () => {
    expect(slugFor("Don't stop: the mural")).toBe("dont-stop-the-mural");
    const found = problems({ ...blank(null, ME), year: "999" }, true, new Date("2026-11-28"));
    expect(Object.keys(found).sort()).toEqual(["discipline", "picture", "title", "year"]);
    expect(problems({ ...blank(PICTURE, ME), title: "A", discipline: "paintings", year: "2027" }, true, new Date("2026-11-28"))).toEqual({});
  });
});

describe("Collective › Portfolio", () => {
  it("shows the pieces with their pills, and the note while some have no artist", async () => {
    routed({
      [LIST]: {
        status: 200,
        body: {
          items: [piece(), piece({ id: "2", title: "Sticker", artist: null, status: "published", path: "/art/piece/sticker" }), piece({ id: "3", title: "Mural", status: "published" })],
          next_cursor: null,
          no_artist: 1,
        },
      },
    });
    renderApp({ path: "/admin/portfolio", modules: [portfolio], session: editor });

    const grid = await screen.findByRole("list", { name: "Pieces" });
    expect(within(grid).getByRole("button", { name: /^Edit ?Harbour at dusk/ })).toHaveTextContent("Draft");
    expect(within(grid).getByRole("button", { name: /^Edit ?Sticker/ })).toHaveTextContent("No artist");
    expect(within(grid).getByRole("button", { name: /^Edit ?Mural/ })).not.toHaveTextContent(/Draft|No artist|Scheduled/);
    expect(screen.getByText("1 piece has no artist")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Credit the first" })).toHaveAttribute("href", "/admin/portfolio/2");
    expect(screen.getByText("Paintings, graphic design and video. Everything live here shows on the Art page.")).toBeInTheDocument();
  });

  it("asks for one discipline when its chip is pressed", async () => {
    const sent = routed({ [LIST]: { status: 200, body: { items: [], next_cursor: null, no_artist: 0 } } });
    renderApp({ path: "/admin/portfolio", modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Graphic design" }));
    await waitFor(() => {
      expect(sent.some((each) => new URL(each.url).searchParams.get("discipline") === "graphic-design")).toBe(true);
    });
    expect(await screen.findByText("No pieces in this discipline yet.")).toBeInTheDocument();
  });

  it("opens a piece in the editor, and a save sends what changed with its version", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [piece()], next_cursor: null, no_artist: 0 } },
      [`GET ${ONE}`]: { status: 200, body: piece() },
      [`PATCH ${ONE}`]: { status: 200, body: piece({ version: 2, year: 2024, artist: { id: ARTISTS.items[1]?.id ?? "", name: "petro" } }) },
    });
    renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: editor });

    const year = await screen.findByRole("textbox", { name: "Year" });
    await userEvent.clear(year);
    await userEvent.type(year, "2024");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "By" }), "petro");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 1, year: 2024, artist_id: ARTISTS.items[1]?.id });
  });

  it("asks which to keep when someone saved the same field first, and saves the choice", async () => {
    let calls = 0;
    const sent = routed({
      [LIST]: { status: 200, body: { items: [piece()], next_cursor: null, no_artist: 0 } },
      [`GET ${ONE}`]: { status: 200, body: piece() },
      [`PATCH ${ONE}`]: () => {
        calls += 1;
        return calls === 1 ? problem(409, "portfolio.changed", { piece: piece({ version: 2, title: "Harbour, theirs" }) }) : { status: 200, body: piece({ version: 3, title: "Harbour, mine" }) };
      },
    });
    renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "Harbour, mine");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    const asking = await screen.findByRole("group", { name: "Saved by someone else since you opened it" });
    expect(within(asking).getByText("Harbour, theirs")).toBeInTheDocument();
    await userEvent.click(within(asking).getByRole("radio", { name: "Keep mine" }));
    await userEvent.click(within(asking).getByRole("button", { name: "Save with these choices" }));
    await waitFor(() => {
      expect(sent.filter((each) => each.method === "PATCH").length).toBe(2);
    });
    expect(await json(sent.filter((each) => each.method === "PATCH")[1] as Request)).toEqual({ version: 2, title: "Harbour, mine" });
  });

  it("takes a scheduled piece back to a draft (cubic on #171)", async () => {
    const scheduled = piece({ status: "scheduled", publish_at: "2026-12-01T09:00:00+00:00" });
    const sent = routed({
      [LIST]: { status: 200, body: { items: [scheduled], next_cursor: null, no_artist: 0 } },
      [`GET ${ONE}`]: { status: 200, body: scheduled },
      [`POST ${ONE}/unpublish`]: { status: 200, body: piece() },
    });
    renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Back to a draft" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "POST" && new URL(each.url).pathname.endsWith("/unpublish"))).toBe(true);
    });
    expect(await screen.findByText("A draft. Nothing shows on the Art page until you publish it.")).toBeInTheDocument();
  });

  it("never says no piece has an artist from one discipline's list (cubic on #171)", async () => {
    routed({
      [LIST]: {
        status: 200,
        body: { items: [piece({ artist: null }), piece({ id: "2", title: "Sticker", artist: null })], next_cursor: null, no_artist: 2 },
      },
    });
    renderApp({ path: "/admin/portfolio?discipline=paintings", modules: [portfolio], session: editor });

    expect(await screen.findByText("2 pieces have no artist")).toBeInTheDocument();
    expect(screen.queryByText("No piece has an artist yet")).not.toBeInTheDocument();
  });

  it("publishes a new piece, and moves on to it only once it's live (cubic on #171)", async () => {
    const image = { ...PICTURE, bytes: 1000, content_type: "image/png", filename: "harbour.png", uploaded_by: "Big Haas", created_at: "2026-11-28T12:00:00+00:00", version: 1 };
    const published = piece({ status: "published", path: "/art/piece/harbour-at-dusk", published_at: "2026-11-28T12:00:00+00:00" });
    let live = false;
    const sent = routed({
      [LIST]: { status: 200, body: { items: [], next_cursor: null, no_artist: 0 } },
      "GET /api/media/admin/images": { status: 200, body: { items: [image], next_cursor: null, missing_alt: 0 } },
      "POST /api/portfolio/admin/pieces": { status: 201, body: piece() },
      // Answered late, as a busy server would: a page that moved on before it never shows it live.
      [`POST ${ONE}/publish`]: async () => {
        await new Promise((done) => setTimeout(done, 300));
        live = true;
        return { status: 200, body: published };
      },
      [`GET ${ONE}`]: () => ({ status: 200, body: live ? published : piece() }),
    });
    const { router } = renderApp({ path: "/admin/portfolio", modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Add a piece" }));
    const picker = await screen.findByRole("dialog", { name: "Choose the new piece's picture" });
    await userEvent.click(await within(picker).findByRole("button", { name: "Boats at dusk, 1200 × 900" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "Harbour at dusk");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Discipline" }), "paintings");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/admin/portfolio/${ID}`);
    });
    expect(live).toBe(true);
    expect(await screen.findByRole("link", { name: "View on the site" })).toHaveAttribute("href", "/art/piece/harbour-at-dusk");
    const made = sent.find((each) => each.method === "POST" && new URL(each.url).pathname === "/api/portfolio/admin/pieces") as Request;
    expect(await json(made)).toMatchObject({ title: "Harbour at dusk", discipline: "paintings", image_id: PICTURE.id });
  });

  it("keeps a new piece open while a discipline's chip is pressed (cubic on #171)", async () => {
    const image = { ...PICTURE, bytes: 1000, content_type: "image/png", filename: "harbour.png", uploaded_by: "Big Haas", created_at: "2026-11-28T12:00:00+00:00", version: 1 };
    routed({
      [LIST]: { status: 200, body: { items: [], next_cursor: null, no_artist: 0 } },
      "GET /api/media/admin/images": { status: 200, body: { items: [image], next_cursor: null, missing_alt: 0 } },
    });
    const { router } = renderApp({ path: "/admin/portfolio", modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Add a piece" }));
    const picker = await screen.findByRole("dialog", { name: "Choose the new piece's picture" });
    await userEvent.click(await within(picker).findByRole("button", { name: "Boats at dusk, 1200 × 900" }));
    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "Harbour at dusk");
    await userEvent.click(screen.getByRole("button", { name: "Graphic design" }));
    await waitFor(() => {
      expect(router.state.location.search).toBe("?discipline=graphic-design");
    });
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Harbour at dusk");
  });

  it("says a rename's failure beside the discipline renamed (cubic on #171)", async () => {
    routed({
      [LIST]: { status: 200, body: { items: [], next_cursor: null, no_artist: 0 } },
      [`PATCH /api/kernel/admin/terms/${DISCIPLINES.items[0]?.id ?? ""}`]: problem(500, "kernel.internal_error"),
    });
    renderApp({ path: "/admin/portfolio", modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Disciplines" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit disciplines" });
    const name = within(dialog).getByRole("textbox", { name: "Name of Paintings" });
    await userEvent.clear(name);
    await userEvent.type(name, "Painting");
    await userEvent.click(within(dialog).getAllByRole("button", { name: "Rename" })[0] as HTMLElement);
    await waitFor(() => {
      expect(name).toHaveAttribute("aria-invalid", "true");
    });
    expect(within(dialog).getByRole("textbox", { name: "New discipline" })).not.toHaveAttribute("aria-invalid", "true");
  });

  it("lets an artist edit their own piece, credited to them with no choice", async () => {
    const mine = piece({ artist: { id: artist.id, name: "J Tone" } });
    const sent = routed({
      [LIST]: { status: 200, body: { items: [mine], next_cursor: null, no_artist: null } },
      [`GET ${ONE}`]: { status: 200, body: mine },
    });
    renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: artist });

    const by = await screen.findByRole("textbox", { name: "By" });
    expect(by).toHaveValue("J Tone");
    expect(by).toHaveAttribute("readonly");
    expect(screen.queryByRole("combobox", { name: "By" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Disciplines" })).not.toBeInTheDocument();
    expect(screen.queryByText(/no artist/)).not.toBeInTheDocument();
    expect(sent.some((each) => new URL(each.url).pathname === "/api/portfolio/admin/artists")).toBe(false);
  });

  it("publishes a draft, and deletes a piece after asking", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [piece()], next_cursor: null, no_artist: 0 } },
      [`GET ${ONE}`]: { status: 200, body: piece() },
      [`POST ${ONE}/publish`]: { status: 200, body: piece({ status: "published", path: "/art/piece/harbour-at-dusk", published_at: "2026-11-28T12:00:00+00:00" }) },
      [`DELETE ${ONE}`]: { status: 204 },
    });
    renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Publish" }));
    expect(await screen.findByRole("link", { name: "View on the site" })).toHaveAttribute("href", "/art/piece/harbour-at-dusk");
    expect(screen.getByRole("button", { name: "Unpublish" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete Harbour at dusk?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "DELETE")).toBe(true);
    });
  });

  it("asks before another piece replaces unsaved edits (Codex on #171)", async () => {
    const other = piece({ id: "81111111-1111-4111-8111-111111111111", title: "Mural" });
    routed({
      [LIST]: { status: 200, body: { items: [piece(), other], next_cursor: null, no_artist: 0 } },
      [`GET ${ONE}`]: { status: 200, body: piece() },
      [`GET /api/portfolio/admin/pieces/${other.id}`]: { status: 200, body: other },
    });
    const { router } = renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.type(title, ", again");
    await userEvent.click(screen.getByRole("button", { name: /^Edit ?Mural/ }));
    const asking = await screen.findByRole("dialog", { name: "You have changes that aren't saved" });
    await userEvent.click(within(asking).getByRole("button", { name: "Stay" }));
    expect(router.state.location.pathname).toBe(`/admin/portfolio/${ID}`);
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Harbour at dusk, again");
  });

  it("keeps unsaved edits through Unpublish (Codex on #171)", async () => {
    const live = piece({ status: "published", path: "/art/piece/harbour-at-dusk", published_at: "2026-11-28T12:00:00+00:00" });
    routed({
      [LIST]: { status: 200, body: { items: [live], next_cursor: null, no_artist: 0 } },
      [`GET ${ONE}`]: { status: 200, body: live },
      [`POST ${ONE}/unpublish`]: { status: 200, body: piece() },
    });
    renderApp({ path: `/admin/portfolio/${ID}`, modules: [portfolio], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.type(title, ", again");
    await userEvent.click(screen.getByRole("button", { name: "Unpublish" }));
    expect(await screen.findByRole("button", { name: "Publish" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Harbour at dusk, again");
    expect(screen.getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("adds a discipline through the kernel's term routes", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [], next_cursor: null, no_artist: 0 } },
      "POST /api/kernel/admin/terms": { status: 201, body: { id: "x", slug: "animation", label: "Animation", position: 3, parent_id: null } },
    });
    renderApp({ path: "/admin/portfolio", modules: [portfolio], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Disciplines" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit disciplines" });
    await userEvent.type(within(dialog).getByRole("textbox", { name: "New discipline" }), "Animation");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "POST")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "POST") as Request)).toEqual({ vocabulary: "portfolio_discipline", slug: "animation", label: "Animation", position: 3 });
  });
});

describe("the Art page", () => {
  const LIVE: LivePiece = { ...card(), about: "Oil on canvas.\n\nPainted from the sea wall.", video: null };

  it("lists the live pieces with the disciplines as addresses", async () => {
    routed({
      "GET /api/portfolio/pieces": { status: 200, body: { items: [card(), card({ id: "2", title: "Sticker", slug: "sticker", artist: null, discipline: { slug: "graphic-design", label: "Graphic design" } })], next_cursor: null } },
      "GET /api/portfolio/disciplines": { status: 200, body: { items: [{ slug: "paintings", label: "Paintings" }, { slug: "graphic-design", label: "Graphic design" }] } },
      "GET /api/portfolio/art": { status: 200, body: { lead: "From the collective.", commission_link: "" } },
    });
    renderApp({ path: "/art", modules: [portfolio] });

    expect(await screen.findByRole("heading", { level: 1, name: "Art" })).toBeInTheDocument();
    expect(screen.getByText("From the collective.")).toBeInTheDocument();
    const chips = screen.getByRole("navigation", { name: "Show" });
    expect(within(chips).getByRole("link", { name: "All" })).toHaveAttribute("aria-current", "page");
    expect(within(chips).getByRole("link", { name: "Graphic design" })).toHaveAttribute("href", "/art/graphic-design");
    const grid = screen.getByRole("list", { name: "Artwork" });
    expect(within(grid).getByRole("link", { name: "Harbour at dusk" })).toHaveAttribute("href", "/art/piece/harbour-at-dusk");
    expect(within(grid).getByText("Paintings, by petro")).toBeInTheDocument();
    expect(within(grid).getByText("Graphic design")).toBeInTheDocument();
  });

  it("opens a piece's panel at its address, with Close back to the list", async () => {
    routed({
      "GET /api/portfolio/pieces": { status: 200, body: { items: [card()], next_cursor: null } },
      "GET /api/portfolio/pieces/harbour-at-dusk": { status: 200, body: LIVE },
      "GET /api/portfolio/art": { status: 200, body: { lead: "", commission_link: "/contact" } },
    });
    const { router } = renderApp({ path: "/art/piece/harbour-at-dusk", modules: [portfolio] });

    const heading = await screen.findByRole("heading", { level: 2, name: "Harbour at dusk" });
    await waitFor(() => {
      expect(heading).toHaveFocus();
    });
    expect(screen.getByText("By petro, 2025")).toBeInTheDocument();
    expect(screen.getByText("Painted from the sea wall.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Commission work like this" })).toHaveAttribute("href", "/contact");
    expect(screen.getByRole("img", { name: "Boats at dusk" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/art");
    });
  });

  it("hides the commission link when none is set, and plays a video only after asking", async () => {
    routed({
      "GET /api/portfolio/pieces": { status: 200, body: { items: [], next_cursor: null } },
      "GET /api/portfolio/pieces/harbour-at-dusk": { status: 200, body: { ...LIVE, has_video: true, video: { url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", video_id: "dQw4w9WgXcQ" } } },
    });
    renderApp({ path: "/art/piece/harbour-at-dusk", modules: [portfolio] });

    expect(await screen.findByRole("heading", { level: 2, name: "Harbour at dusk" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Commission work like this" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Play/ })).toBeInTheDocument();
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("says when the disciplines or the page's words couldn't be read, with Try again (cubic on #171)", async () => {
    routed({
      "GET /api/portfolio/pieces": { status: 200, body: { items: [card()], next_cursor: null } },
      "GET /api/portfolio/disciplines": problem(500, "kernel.internal_error"),
      "GET /api/portfolio/art": problem(500, "kernel.internal_error"),
    });
    renderApp({ path: "/art", modules: [portfolio] });

    expect(await screen.findByText("The disciplines couldn't be loaded.")).toBeInTheDocument();
    expect(screen.getByText("The Art page's words couldn't be loaded.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Try again" })).toHaveLength(2);
  });

  it("answers a piece that isn't live with the site's not-found page", async () => {
    routed({
      "GET /api/portfolio/pieces": { status: 200, body: { items: [], next_cursor: null } },
      "GET /api/portfolio/pieces/gone": { status: 404, body: { type: "urn:mechframe:problem:portfolio.piece_not_found", title: "Not Found", status: 404, detail: "", code: "portfolio.piece_not_found" } },
    });
    renderApp({ path: "/art/piece/gone", modules: [portfolio] });

    expect(await screen.findByRole("heading", { level: 1, name: /not found|isn't here|no page/i })).toBeInTheDocument();
  });
});

describe("the Settings section", () => {
  it("is the module's own section of Settings", () => {
    const sections = portfolio.slots?.["admin.settings.section"] ?? [];
    expect(sections.map((each) => ("title" in each ? each.title : ""))).toEqual(["Art page"]);
  });
});
