/**
 * The blog's web (`dev plans/contracts/blog.md`): the blog and a live post on
 * the site, the admin's board with its Categories card, and the editor. Every
 * answer comes from a fetch that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "@/kernel/testing";

import type { Card, Full, Listed, LivePost } from "../../web/api";
import { slugFor } from "../../web/editing";
import blog from "../../web/module.web";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const LIST = "GET /api/blog/admin/posts";
const ID = "11111111-1111-4111-8111-111111111111";
const ONE = `/api/blog/admin/posts/${ID}`;
const ME = "00000000-0000-4000-8000-000000000001";
const CATEGORIES = {
  items: [
    { id: "21111111-1111-4111-8111-111111111111", slug: "news", label: "News", position: 0, posts: 4 },
    { id: "31111111-1111-4111-8111-111111111111", slug: "poetry", label: "Poetry", position: 1, posts: 1 },
  ],
};
const AUTHORS = { items: [{ id: ME, name: "Pat Writer" }, { id: "41111111-1111-4111-8111-111111111111", name: "Sam" }] };

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = {
        "GET /api/blog/admin/categories": { status: 200, body: CATEGORIES },
        "GET /api/blog/admin/authors": { status: 200, body: AUTHORS },
        "GET /api/blog/categories": { status: 200, body: { items: [] } },
        ...answers,
      };
      const found = all[`${request.method} ${new URL(request.url).pathname}`];
      if (!found) throw new TypeError("Failed to fetch");
      const answer = typeof found === "function" ? await found(request) : found;
      const type = answer.status >= 400 ? "application/problem+json" : "application/json";
      return new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
        status: answer.status,
        headers: { "content-type": type },
      });
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

function full(overrides: Partial<Full> = {}): Full {
  return {
    id: ID,
    title: "Ten years",
    slug: "ten-years",
    status: "draft",
    category: { slug: "news", label: "News" },
    author: { id: ME, name: "Pat Writer" },
    publish_at: null,
    published_at: null,
    updated_at: "2026-11-22T12:00:00+00:00",
    has_cover: false,
    summary: "A decade of shows.",
    body: "We booked a room.",
    cover_id: null,
    cover: null,
    search_title: null,
    search_description: null,
    allow_comments: true,
    post_to_community: false,
    email_subscribers: false,
    version: 1,
    moves: [],
    related: [],
    ...overrides,
  };
}

function listed(post: Full): Listed {
  const { id, title, slug, status, category, author, publish_at, published_at, updated_at, has_cover } = post;
  return { id, title, slug, status, category, author, publish_at, published_at, updated_at, has_cover };
}

function card(overrides: Partial<Card> = {}): Card {
  return {
    title: "Ten years",
    slug: "ten-years",
    summary: "A decade of shows.",
    cover: null,
    category: { slug: "news", label: "News" },
    author: "Pat Writer",
    published_at: "2026-11-20T12:00:00+00:00",
    reading_minutes: 3,
    ...overrides,
  };
}

const editor = testUser({
  roles: ["member", "editor"],
  second_factor: true,
  permissions: ["blog.post.write", "blog.post.publish", "kernel.taxonomy.manage", "media.image.upload"],
});

async function json(request: Request): Promise<Record<string, unknown>> {
  return (await request.json()) as Record<string, unknown>;
}

describe("the blog", () => {
  it("shows the latest post larger, then the rest, and Older posts loads the next page", async () => {
    const sent = routed({
      "GET /api/blog/posts": (request) =>
        new URL(request.url).searchParams.get("cursor")
          ? { status: 200, body: { items: [card({ title: "An old one", slug: "an-old-one" })], next_cursor: null } }
          : { status: 200, body: { items: [card(), card({ title: "Salt", slug: "salt", category: { slug: "poetry", label: "Poetry" }, author: null })], next_cursor: "c1" } },
    });
    renderApp({ path: "/blog", modules: [blog] });

    expect(await screen.findByRole("heading", { level: 2, name: "Ten years" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Salt" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ten years" })).toHaveAttribute("href", "/blog/ten-years");
    expect(screen.getAllByText("3 min read").length).toBe(2);
    await userEvent.click(screen.getByRole("button", { name: "Older posts" }));
    expect(await screen.findByRole("heading", { level: 3, name: "An old one" })).toBeInTheDocument();
    expect(sent.some((each) => new URL(each.url).searchParams.get("cursor") === "c1")).toBe(true);
    await waitFor(() => {
      expect(document.title).toBe("Blog · Test Site");
    });
  });

  it("filters by category, and says when there's nothing", async () => {
    const sent = routed({
      "GET /api/blog/categories": {
        status: 200,
        body: { items: [{ slug: "news", label: "News", posts: 2 }, { slug: "poetry", label: "Poetry", posts: 1 }, { slug: "empty", label: "Empty", posts: 0 }] },
      },
      "GET /api/blog/posts": (request) =>
        new URL(request.url).searchParams.get("category") === "poetry"
          ? { status: 200, body: { items: [], next_cursor: null } }
          : { status: 200, body: { items: [card()], next_cursor: null } },
    });
    const { router } = renderApp({ path: "/blog", modules: [blog] });

    expect(await screen.findByRole("button", { name: "All posts", pressed: true })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Empty" })).toBeNull(); // a category with no posts isn't offered
    await userEvent.click(screen.getByRole("button", { name: "Poetry" }));
    expect(await screen.findByText("Nothing's posted in Poetry yet.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Blog: Poetry" })).toBeInTheDocument();
    expect(router.state.location.search).toBe("?category=poetry");
    expect(sent.some((each) => new URL(each.url).searchParams.get("category") === "poetry")).toBe(true);
  });
});

describe("a live post", () => {
  const live: LivePost = {
    ...card(),
    html: "<h2>Then</h2><p>A <strong>room</strong>.</p>",
    updated_at: "2026-11-21T12:00:00+00:00",
    search_title: "Ten years · Test Site",
    search_description: "A decade of shows.",
    related: [{ title: "Salt", slug: "salt" }],
    allow_comments: true,
    cover: { id: "51111111-1111-4111-8111-111111111111", url: "https://files.test/c.png", srcset: "https://files.test/c.png 1200w", width: 1200, height: 630, alt: "The crowd", decorative: false },
  };

  it("draws its category, title, byline, cover, body and related posts", async () => {
    routed({ "GET /api/blog/posts/ten-years": { status: 200, body: live } });
    renderApp({ path: "/blog/ten-years", modules: [blog] });

    expect(await screen.findByRole("heading", { level: 1, name: "Ten years" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "News" })).toHaveAttribute("href", "/blog?category=news");
    expect(screen.getByText("Pat Writer")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "The crowd" })).toHaveAttribute("src", "https://files.test/c.png");
    expect(screen.getByRole("heading", { level: 2, name: "Then" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Salt" })).toHaveAttribute("href", "/blog/salt");
    await waitFor(() => {
      expect(document.title).toBe("Ten years · Test Site");
    });
    expect(document.querySelector('meta[property="og:image"]')).toHaveAttribute("content", "https://files.test/c.png");
  });

  it("is the 404 page where there's none, and moves on from a slug a post left", async () => {
    routed({
      "GET /api/blog/posts/gone": problem(404, "blog.post_not_found"),
      "GET /api/blog/posts/old": { status: 200, body: { moved: "/blog/ten-years" } },
      "GET /api/blog/posts/ten-years": { status: 200, body: live },
    });
    const missing = renderApp({ path: "/blog/gone", modules: [blog] });
    expect(await screen.findByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
    missing.unmount();

    const { router } = renderApp({ path: "/blog/old?from=mail", modules: [blog] });
    expect(await screen.findByRole("heading", { level: 1, name: "Ten years" })).toBeInTheDocument();
    expect(`${router.state.location.pathname}${router.state.location.search}`).toBe("/blog/ten-years?from=mail");
  });
});

describe("the board", () => {
  it("lists posts with their category, author, state and when, and the note for a coverless scheduled one", async () => {
    routed({
      [LIST]: {
        status: 200,
        body: {
          items: [
            listed(full()),
            listed(full({ id: "2", title: "Spring tour", status: "scheduled", publish_at: "2026-12-01T12:00:00+00:00", author: null })),
            listed(full({ id: "3", title: "Salt", status: "published", published_at: "2026-11-20T12:00:00+00:00" })),
          ],
          next_cursor: null,
          needs_cover: { id: "2", title: "Spring tour", publish_at: "2026-12-01T12:00:00+00:00" },
        },
      },
    });
    renderApp({ path: "/admin/blog", modules: [blog], session: editor });

    const table = await screen.findByRole("table", { name: "Posts" });
    expect(within(table).getByText("Not published")).toBeInTheDocument();
    expect(within(table).getByText("No one named")).toBeInTheDocument();
    expect(within(table).getAllByText("Pat Writer").length).toBe(2);
    expect(within(table).getByText("Live")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit Salt" })).toHaveAttribute("href", "/admin/blog/3");
    expect(screen.getByText("A scheduled post has no cover image")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Add a cover" })).toHaveAttribute("href", "/admin/blog/2");
    expect(screen.getByRole("link", { name: "New post" })).toHaveAttribute("href", "/admin/blog/new");
    expect(screen.getByText("4 posts")).toBeInTheDocument();
    expect(screen.getByText("1 post")).toBeInTheDocument();
  });

  it("asks for one state and for words", async () => {
    const sent = routed({ [LIST]: { status: 200, body: { items: [], next_cursor: null, needs_cover: null } } });
    renderApp({ path: "/admin/blog", modules: [blog], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Drafts" }));
    await waitFor(() => {
      expect(sent.some((each) => new URL(each.url).searchParams.get("status") === "draft")).toBe(true);
    });
    await userEvent.type(screen.getByRole("searchbox", { name: "Search posts" }), "tour");
    await waitFor(() => {
      expect(sent.some((each) => new URL(each.url).searchParams.get("q") === "tour")).toBe(true);
    });
    expect(await screen.findByText("No posts match. Try other words, or show all.")).toBeInTheDocument();
  });

  it("adds, renames and deletes categories through the kernel's terms", async () => {
    const sent = routed({
      [LIST]: { status: 200, body: { items: [], next_cursor: null, needs_cover: null } },
      "POST /api/kernel/admin/terms": { status: 201, body: { id: "6", vocabulary: "blog_category", slug: "rap-battles", label: "Rap battles", parent_id: null, position: 2 } },
      [`PATCH /api/kernel/admin/terms/${CATEGORIES.items[0]?.id ?? ""}`]: { status: 200, body: {} },
      [`DELETE /api/kernel/admin/terms/${CATEGORIES.items[1]?.id ?? ""}`]: { status: 204 },
    });
    renderApp({ path: "/admin/blog", modules: [blog], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Edit categories" }));
    const dialog = await screen.findByRole("dialog", { name: "Edit categories" });
    await userEvent.type(within(dialog).getByRole("textbox", { name: "New category" }), "Rap battles");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add" }));
    await waitFor(() => {
      expect(sent.some((each) => each.method === "POST")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "POST") as Request)).toEqual({ vocabulary: "blog_category", slug: "rap-battles", label: "Rap battles", position: 2 });

    const news = within(dialog).getByRole("textbox", { name: "Name of News" });
    await userEvent.clear(news);
    await userEvent.type(news, "Updates");
    await userEvent.click(within(dialog).getAllByRole("button", { name: "Rename" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ label: "Updates" });

    await userEvent.click(within(dialog).getAllByRole("button", { name: "Delete" })[1] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "DELETE")).toBe(true);
    });
  });

  it("offers no Edit to someone who can't manage the terms", async () => {
    routed({ [LIST]: { status: 200, body: { items: [], next_cursor: null, needs_cover: null } } });
    const writer = testUser({ roles: ["member", "writer"], second_factor: true, permissions: ["blog.post.write"] });
    renderApp({ path: "/admin/blog", modules: [blog], session: writer });
    expect(await screen.findByText("4 posts")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit categories" })).toBeNull();
  });
});

describe("the editor", () => {
  it("saves only what changed, with the version it read", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: async (request) => {
        const body = await json(request);
        return { status: 200, body: full({ category: { slug: "poetry", label: "Poetry" }, summary: String(body.summary), version: 2 }) };
      },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    const summary = await screen.findByRole("textbox", { name: "Summary" });
    await userEvent.clear(summary);
    await userEvent.type(summary, "Ten years of shows.");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Category" }), "poetry");
    expect(screen.getByText("2 changes not saved")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 1, summary: "Ten years of shows.", category: "poetry" });
    await waitFor(() => {
      expect(screen.queryByText(/not saved/)).toBeNull();
    });
  });

  it("writes a new post, its address from its title and its author the writer", async () => {
    const sent = routed({
      "POST /api/blog/admin/posts": async (request) => {
        const body = await json(request);
        return { status: 201, body: full({ title: String(body.title), slug: String(body.slug) }) };
      },
      [`GET ${ONE}`]: { status: 200, body: full({ title: "Don't stop", slug: "dont-stop" }) },
    });
    const { router } = renderApp({ path: "/admin/blog/new", modules: [blog], session: editor });

    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "Don't stop");
    expect(screen.getByRole("textbox", { name: "Address" })).toHaveValue("dont-stop");
    expect(screen.getByRole("combobox", { name: "Author" })).toHaveValue(ME);
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/admin/blog/${ID}`);
    });
    const made = sent.find((each) => each.method === "POST" && each.url.endsWith("/admin/posts")) as Request;
    const sentBody = await json(made);
    expect(sentBody).toMatchObject({ title: "Don't stop", author_id: ME, category: null, cover_id: null, related: [] });
    // An address that followed the title is the server's to make, numbered when taken (CodeRabbit on #123).
    expect(sentBody).not.toHaveProperty("slug");
    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1, name: "Edit post" })).toBeInTheDocument();
    });
  });

  it("places a cover from the library, and Remove takes it off", async () => {
    const image = {
      id: "51111111-1111-4111-8111-111111111111",
      url: "https://files.test/media/c.png",
      srcset: "https://files.test/media/c.png 1000w",
      width: 1000,
      height: 600,
      bytes: 1000,
      content_type: "image/png",
      filename: "crowd.png",
      alt: "The crowd",
      decorative: false,
      uploaded_by: "Pat",
      created_at: "2026-11-21T12:00:00+00:00",
      version: 1,
    };
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      "GET /api/media/admin/images": { status: 200, body: { items: [image], next_cursor: null, missing_alt: 0 } },
      [`PATCH ${ONE}`]: { status: 200, body: full({ version: 2 }) },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    await userEvent.click(await screen.findByRole("button", { name: "Choose a cover" }));
    const dialog = await screen.findByRole("dialog", { name: "Choose a cover image" });
    await userEvent.click(await within(dialog).findByRole("button", { name: "The crowd, 1000 × 600" }));
    expect(await screen.findByRole("img", { name: "The crowd" })).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 1, cover_id: image.id });
  });

  it("adds a live post to the related posts, and sends them in order", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full({ related: [{ id: "7", title: "Salt", slug: "salt" }] }) },
      [LIST]: (request) => ({
        status: 200,
        body: {
          items: new URL(request.url).searchParams.get("status") === "published" ? [listed(full({ id: "8", title: "Spring tour", slug: "spring-tour", status: "published" }))] : [],
          next_cursor: null,
          needs_cover: null,
        },
      }),
      [`PATCH ${ONE}`]: { status: 200, body: full({ version: 2 }) },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    await userEvent.type(await screen.findByRole("searchbox", { name: "Find a live post" }), "spring");
    await userEvent.click(await screen.findByRole("button", { name: "Add Spring tour" }));
    await userEvent.click(screen.getByRole("button", { name: "Move Spring tour up" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 1, related: ["8", "7"] });
  });

  it("says what After publishing waits for while the modules are off", async () => {
    routed({ [`GET ${ONE}`]: { status: 200, body: full() } });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });
    expect(await screen.findByText("Kept for when the site has comments.")).toBeInTheDocument();
    expect(screen.getByText("Kept for when the site has Community.")).toBeInTheDocument();
    expect(screen.getByText("Kept for when the site has a newsletter.")).toBeInTheDocument();
  });

  it("says Live and Update for a live post, and Unpublish takes it down", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full({ status: "published", published_at: "2026-11-20T12:00:00+00:00" }) },
      [`POST ${ONE}/unpublish`]: { status: 200, body: full() },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    expect(await screen.findByText("Live. Saving changes the post on the site at once.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on the site" })).toHaveAttribute("href", "/blog/ten-years");
    await userEvent.click(screen.getByRole("button", { name: "Unpublish" }));
    expect(await screen.findByText("Saved as a draft. Nothing changes on the site until you publish.")).toBeInTheDocument();
    expect(sent.some((each) => each.method === "POST" && each.url.endsWith("/unpublish"))).toBe(true);
  });

  it("asks field by field when someone saved first, and saves again with the choice", async () => {
    let patches = 0;
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: async (request) => {
        patches += 1;
        if (patches === 1) return problem(409, "blog.changed", { post: full({ title: "Their title", body: "Their words.", version: 2 }) });
        const body = await json(request);
        return { status: 200, body: full({ title: typeof body.title === "string" ? body.title : "Their title", body: "Their words.", version: 3 }) };
      },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "My title");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    expect(await screen.findByText("Their title")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Keep mine" }));
    await userEvent.click(screen.getByRole("button", { name: /Save with these choices/ }));
    await waitFor(() => {
      expect(patches).toBe(2);
    });
    const second = sent.filter((each) => each.method === "PATCH")[1] as Request;
    expect(await json(second)).toEqual({ version: 2, title: "My title" });
  });

  it("refuses an address out of the rule before anything is sent", async () => {
    const sent = routed({ [`GET ${ONE}`]: { status: 200, body: full() } });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });
    const address = await screen.findByRole("textbox", { name: "Address" });
    await userEvent.clear(address);
    await userEvent.type(address, "Ten Years");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    expect(await screen.findByText(/An address is lowercase letters, digits and single hyphens/)).toBeInTheDocument();
    expect(sent.some((each) => each.method === "PATCH")).toBe(false);
  });
});

describe("the editor's Write with AI (blog 0.1.2, decision 0058)", () => {
  const writer = testUser({ ...editor, permissions: [...editor.permissions, "kernel.ai.write"] });

  it("fills the post's title and search words from what the AI suggests", async () => {
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      "GET /api/kernel/ai": { status: 200, body: { ready: true, unreadable: false, styles: [] } },
      "POST /api/kernel/ai/titles": { status: 200, body: { titles: ["Ten years on stage"] } },
      "POST /api/kernel/ai/search": { status: 200, body: { title: "Ten years on stage", description: "Our shows, year by year." } },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: writer });

    await userEvent.click(await screen.findByRole("button", { name: "Write with AI" }));
    let dialog = within(await screen.findByRole("dialog", { name: "Write with AI" }));
    expect(dialog.getAllByRole("button").map((button) => button.textContent)).toEqual(
      expect.arrayContaining(["Draft", "Rewrite", "Titles", "Summary", "Search words"]),
    );
    await userEvent.click(dialog.getByRole("button", { name: "Titles" }));
    await userEvent.click(dialog.getByRole("button", { name: "Suggest titles" }));
    await userEvent.click(await dialog.findByRole("button", { name: "Use" }));
    expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Ten years on stage");

    await userEvent.click(screen.getByRole("button", { name: "Write with AI" }));
    dialog = within(await screen.findByRole("dialog", { name: "Write with AI" }));
    await userEvent.click(dialog.getByRole("button", { name: "Search words" }));
    await userEvent.click(dialog.getByRole("button", { name: "Write search words" }));
    await userEvent.click(await dialog.findByRole("button", { name: "Use these" }));
    expect(screen.getByRole("textbox", { name: "Title in search results" })).toHaveValue("Ten years on stage");
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue("Our shows, year by year.");
  });
});

describe("the review on #123 (CodeRabbit)", () => {
  it("sends a new post's address once the writer has typed it", async () => {
    const sent = routed({
      "POST /api/blog/admin/posts": { status: 201, body: full({ slug: "my-own" }) },
      [`GET ${ONE}`]: { status: 200, body: full({ slug: "my-own" }) },
    });
    renderApp({ path: "/admin/blog/new", modules: [blog], session: editor });
    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "Ten years");
    const address = screen.getByRole("textbox", { name: "Address" });
    await userEvent.clear(address);
    await userEvent.type(address, "my-own");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "POST")).toBe(true);
    });
    expect(await json(sent.find((each) => each.method === "POST") as Request)).toMatchObject({ slug: "my-own" });
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
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "B");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(patches).toBe(1);
    });
    await userEvent.clear(title);
    await userEvent.type(title, "A");
    answer(problem(409, "blog.changed", { post: full({ title: "B", version: 2 }) }));

    // Theirs is B and yours is A again: that's a choice, not theirs by default.
    expect(await screen.findByRole("radio", { name: "Keep mine" })).toBeInTheDocument();
    expect(title).toHaveValue("A");
  });

  it("keeps what's typed while the save waits through the conflict's choice", async () => {
    let answer: (value: Answer) => void = () => undefined;
    let patches = 0;
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: () => {
        patches += 1;
        return patches === 1
          ? new Promise<Answer>((resolve) => {
              answer = resolve;
            })
          : { status: 200, body: full({ title: "My title", summary: "Typed while it waited.", version: 3 }) };
      },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "My title");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(patches).toBe(1);
    });
    const summary = screen.getByRole("textbox", { name: "Summary" });
    await userEvent.clear(summary);
    await userEvent.type(summary, "Typed while it waited.");
    answer(problem(409, "blog.changed", { post: full({ title: "Their title", version: 2 }) }));

    await userEvent.click(await screen.findByRole("radio", { name: "Keep mine" }));
    await userEvent.click(screen.getByRole("button", { name: /Save with these choices/ }));
    await waitFor(() => {
      expect(patches).toBe(2);
    });
    const second = sent.filter((each) => each.method === "PATCH")[1] as Request;
    expect(await json(second)).toEqual({ version: 2, title: "My title", summary: "Typed while it waited." });
  });

  it("shows a post as live once its publish lands, even while it asks about a field", async () => {
    let answer: (value: Answer) => void = () => undefined;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`POST ${ONE}/publish`]: () =>
        new Promise<Answer>((resolve) => {
          answer = resolve;
        }),
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    // Typed while the publish is on its way, and someone else saved the title too.
    await userEvent.type(title, "!");
    answer({ status: 200, body: full({ title: "Their title", status: "published", published_at: "2026-11-22T12:00:00+00:00", version: 2 }) });
    expect(await screen.findByText("Their title")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Back to the form" }));
    expect(await screen.findByText("Live. Saving changes the post on the site at once.")).toBeInTheDocument();
  });

  it("keeps All posts while a filter is on, with one category or none", async () => {
    routed({
      "GET /api/blog/categories": { status: 200, body: { items: [{ slug: "news", label: "News", posts: 2 }] } },
      "GET /api/blog/posts": { status: 200, body: { items: [card()], next_cursor: null } },
    });
    const { router } = renderApp({ path: "/blog?category=news", modules: [blog] });
    await userEvent.click(await screen.findByRole("button", { name: "All posts", pressed: false }));
    await waitFor(() => {
      expect(router.state.location.search).toBe("");
    });
  });

  it("fixes the announcement's switches once a post has gone live", async () => {
    routed({ [`GET ${ONE}`]: { status: 200, body: full({ status: "published", published_at: "2026-11-20T12:00:00+00:00" }) } });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: editor });
    expect(await screen.findByRole("switch", { name: "Post it in Community" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Email it to subscribers" })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Allow comments" })).toBeEnabled();
    expect(screen.getAllByText("Sent when it first went live.").length).toBe(2);
  });
});

describe("a slug from a title", () => {
  it.each([
    ["Don't stop the music!", "dont-stop-the-music"],
    ["Café Ñandú", "cafe-nandu"],
    ["  --  ", ""],
  ])("spells %s as the server does", (title, made) => {
    expect(slugFor(title)).toBe(made);
  });
});
