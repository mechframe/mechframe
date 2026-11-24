/**
 * The pages' web (`dev plans/contracts/pages.md`): a live page at its address,
 * the menus it loads into the header and the footer (decision 0056), the
 * admin's list and the editor. Every answer comes from a fetch that answers
 * by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "@/kernel/testing";

import type { Full, Listed } from "../../web/api";
import pages from "../../web/module.web";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const MENU = "GET /api/pages/menu";
const LIST = "GET /api/pages/admin/pages";
const ID = "11111111-1111-4111-8111-111111111111";
const ONE = `/api/pages/admin/pages/${ID}`;

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = { [MENU]: { status: 200, body: { items: [] } }, ...answers };
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
    title: "About",
    address: "/about",
    status: "draft",
    in_header: false,
    in_footer: true,
    menu_order: 0,
    publish_at: null,
    updated_at: "2026-11-22T12:00:00+00:00",
    updated_by: "Pat",
    body: "We make music.",
    search_title: null,
    search_description: null,
    published_at: null,
    version: 1,
    moves: [],
    ...overrides,
  };
}

function listed(page: Full): Listed {
  const { id, title, address, status, in_header, in_footer, menu_order, publish_at, updated_at, updated_by } = page;
  return { id, title, address, status, in_header, in_footer, menu_order, publish_at, updated_at, updated_by };
}

const editor = testUser({
  roles: ["member", "editor"],
  second_factor: true,
  permissions: ["pages.page.write", "pages.page.publish"],
});

async function json(request: Request): Promise<Record<string, unknown>> {
  return (await request.json()) as Record<string, unknown>;
}

describe("a live page", () => {
  it("draws its title and its body, and keeps the head's words", async () => {
    routed({
      "GET /api/pages/page": {
        status: 200,
        body: {
          title: "About",
          address: "/about",
          html: "<h2>Who we are</h2><p>A crew from <strong>Boston</strong>.</p>",
          search_title: "About · Test Site",
          search_description: "Who we are A crew from Boston.",
          updated_at: "2026-11-22T12:00:00+00:00",
        },
      },
    });
    renderApp({ path: "/about", modules: [pages] });

    expect(await screen.findByRole("heading", { level: 1, name: "About" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Who we are" })).toBeInTheDocument();
    expect(screen.getByText("Boston")).toBeInTheDocument();
    // When it last changed, under its title, as the server copy says it (pages 0.1.1).
    const updated = screen.getByText(/^Updated/);
    expect(updated.previousElementSibling).toBe(screen.getByRole("heading", { level: 1, name: "About" }));
    expect(updated.querySelector("time")).toHaveAttribute("datetime", "2026-11-22T12:00:00+00:00");
    expect(updated.querySelector("time")?.textContent).toContain("2026");
    await waitFor(() => {
      expect(document.title).toBe("About · Test Site");
    });
  });

  it("is the 404 page where there's none", async () => {
    routed({ "GET /api/pages/page": problem(404, "pages.page_not_found") });
    renderApp({ path: "/nowhere", modules: [pages] });
    expect(await screen.findByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });

  it("moves on from an address a live page left, its query kept", async () => {
    routed({
      "GET /api/pages/page": (request) =>
        new URL(request.url).searchParams.get("address") === "/old"
          ? { status: 200, body: { moved: "/new" } }
          : {
              status: 200,
              body: { title: "New", address: "/new", html: "<p>Here now.</p>", search_title: "New", search_description: "", updated_at: "2026-11-22T12:00:00+00:00" },
            },
    });
    const { router } = renderApp({ path: "/old?from=mail", modules: [pages] });
    expect(await screen.findByRole("heading", { level: 1, name: "New" })).toBeInTheDocument();
    expect(`${router.state.location.pathname}${router.state.location.search}`).toBe("/new?from=mail");
  });
});

describe("the menus (decision 0056)", () => {
  it("puts the header's pages in the site's navigation and the footer's in the footer's", async () => {
    const sent = routed({
      [MENU]: (request) =>
        new URL(request.url).searchParams.get("place") === "header"
          ? { status: 200, body: { items: [{ title: "Press kit", address: "/press-kit" }] } }
          : { status: 200, body: { items: [{ title: "Credits", address: "/credits" }] } },
      "GET /api/pages/page": problem(404, "pages.page_not_found"),
    });
    renderApp({ path: "/nowhere", modules: [pages] });

    const header = screen.getByRole("navigation", { name: "Site" });
    expect(await within(header).findByRole("link", { name: "Press kit" })).toHaveAttribute("href", "/press-kit");
    const footer = await screen.findByRole("navigation", { name: "Footer" });
    expect(within(footer).getByRole("link", { name: "Credits" })).toHaveAttribute("href", "/credits");
    expect(sent.filter((each) => each.url.includes("/api/pages/menu"))).toHaveLength(2);
  });
});

describe("the admin's list", () => {
  it("shows each page with its address, its state and its menus, and asks for a privacy page", async () => {
    routed({
      [LIST]: { status: 200, body: { items: [listed(full({ status: "published" })), listed(full({ id: "2", title: "Press kit", address: "/press-kit", in_footer: false }))] } },
    });
    renderApp({ path: "/admin/pages", modules: [pages], session: editor });

    expect(await screen.findByRole("heading", { level: 1, name: "Pages" })).toBeInTheDocument();
    const about = (await screen.findByText("/about")).closest("tr");
    expect(about).not.toBeNull();
    expect(within(about as HTMLElement).getByText("Live")).toBeInTheDocument();
    expect(within(about as HTMLElement).getByText("Footer")).toBeInTheDocument();
    const press = screen.getByText("/press-kit").closest("tr") as HTMLElement;
    expect(within(press).getByText("Draft")).toBeInTheDocument();
    expect(within(press).getByText("Not in a menu")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Edit Press kit" })).toHaveAttribute("href", "/admin/pages/2");
    expect(screen.getByText("There's no privacy page yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Write it" })).toHaveAttribute("href", "/admin/pages/new?address=privacy");
    expect(screen.getByRole("link", { name: "New page" })).toHaveAttribute("href", "/admin/pages/new");
  });

  it("says nothing of privacy once its page is live", async () => {
    routed({ [LIST]: { status: 200, body: { items: [listed(full({ title: "Privacy", address: "/privacy", status: "published" }))] } } });
    renderApp({ path: "/admin/pages", modules: [pages], session: editor });
    expect(await screen.findByText("/privacy")).toBeInTheDocument();
    expect(screen.queryByText("There's no privacy page yet")).toBeNull();
  });
});

describe("the editor", () => {
  it("saves only what changed, with the version it read, and says how many changes wait", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: async (request) => {
        const body = await json(request);
        return { status: 200, body: full({ title: String(body.title), version: 2 }) };
      },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    expect(screen.getByText("Saved as a draft. Nothing changes on the site until you publish.")).toBeInTheDocument();
    await userEvent.clear(title);
    await userEvent.type(title, "About us");
    expect(screen.getByText("1 change not saved")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    const patch = sent.find((each) => each.method === "PATCH") as Request;
    expect(await json(patch)).toEqual({ version: 1, title: "About us" });
    await waitFor(() => {
      expect(screen.queryByText(/not saved/)).toBeNull();
    });
  });

  it("says Live and Update for a live page, and Unpublish takes it down", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full({ status: "published", published_at: "2026-11-20T12:00:00+00:00" }) },
      [`POST ${ONE}/unpublish`]: { status: 200, body: full() },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    expect(await screen.findByText("Live. Saving changes the page on the site at once.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View on the site" })).toHaveAttribute("href", "/about");
    expect(screen.getAllByRole("button", { name: "Update" }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Unpublish" }));
    expect(await screen.findByText("Saved as a draft. Nothing changes on the site until you publish.")).toBeInTheDocument();
    expect(sent.some((each) => each.method === "POST" && each.url.endsWith("/unpublish"))).toBe(true);
  });

  it("writes a new page, its address from its title, and opens it once it's saved", async () => {
    const sent = routed({
      "POST /api/pages/admin/pages": async (request) => {
        const body = await json(request);
        return { status: 201, body: full({ title: String(body.title), address: String(body.address), body: "" }) };
      },
      [`GET ${ONE}`]: { status: 200, body: full({ title: "Press kit", address: "/press-kit", body: "" }) },
    });
    const { router } = renderApp({ path: "/admin/pages/new", modules: [pages], session: editor });

    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "Press kit");
    expect(screen.getByRole("textbox", { name: "Address" })).toHaveValue("/press-kit");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/admin/pages/${ID}`);
    });
    const made = sent.find((each) => each.method === "POST") as Request;
    expect(await json(made)).toMatchObject({ title: "Press kit", address: "/press-kit", in_header: false, in_footer: false });
    // The editor draws again under the page's id: the heading is the new one's.
    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1, name: "Edit page" })).toBeInTheDocument();
    });
  });

  it("publishes a new page in one go: saved, then live, in the same editor", async () => {
    const drawn: { app?: ReturnType<typeof renderApp> } = {};
    routed({
      "POST /api/pages/admin/pages": { status: 201, body: full({ title: "Credits", address: "/credits", body: "" }) },
      // As over a network: the editor is at the page's own address before the publish answers.
      [`POST ${ONE}/publish`]: async () => {
        await waitFor(() => {
          expect(drawn.app?.router.state.location.pathname).toBe(`/admin/pages/${ID}`);
        });
        await new Promise((resolve) => setTimeout(resolve, 50));
        return { status: 200, body: full({ title: "Credits", address: "/credits", body: "", status: "published" }) };
      },
    });
    drawn.app = renderApp({ path: "/admin/pages/new", modules: [pages], session: editor });
    const { router } = drawn.app;

    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "Credits");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));

    expect(await screen.findByText("Live. Saving changes the page on the site at once.")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/admin/pages/${ID}`);
  });

  it("starts the privacy page Needs you asks for with a few headings to fill", async () => {
    routed({});
    renderApp({ path: "/admin/pages/new?address=privacy", modules: [pages], session: editor });
    expect(await screen.findByRole("textbox", { name: "Title" })).toHaveValue("Privacy");
    expect(screen.getByRole("textbox", { name: "Address" })).toHaveValue("/privacy");
    expect(screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Page body" }).value).toContain("## What we collect");
  });

  it("refuses an address out of the rule before anything is sent", async () => {
    const sent = routed({ [`GET ${ONE}`]: { status: 200, body: full() } });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });
    const address = await screen.findByRole("textbox", { name: "Address" });
    await userEvent.clear(address);
    await userEvent.type(address, "/About Us");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    expect(await screen.findByText(/An address is a slash, then lowercase letters/)).toBeInTheDocument();
    expect(sent.some((each) => each.method === "PATCH")).toBe(false);
  });

  it("asks field by field when someone saved first, and saves again with the choice", async () => {
    let patches = 0;
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: async (request) => {
        patches += 1;
        if (patches === 1) {
          return problem(409, "pages.changed", { page: full({ title: "Their title", body: "Their words.", version: 2 }) });
        }
        const body = await json(request);
        return { status: 200, body: full({ title: typeof body.title === "string" ? body.title : "Their title", body: "Their words.", version: 3 }) };
      },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

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
    // Their body stays theirs: only the title, at their version.
    expect(await json(second)).toEqual({ version: 2, title: "My title" });
  });

  it("keeps what's typed while a save is on its way (Codex on #121)", async () => {
    let answer: (value: Answer) => void = () => undefined;
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: () =>
        new Promise<Answer>((resolve) => {
          answer = resolve;
        }),
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "About us");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    const body = screen.getByRole("textbox", { name: "Page body" });
    await userEvent.type(body, " More.");
    answer({ status: 200, body: full({ title: "About us", version: 2 }) });

    await waitFor(() => {
      expect(screen.getByText("1 change not saved")).toBeInTheDocument();
    });
    expect(body).toHaveValue("We make music. More.");
    expect(title).toHaveValue("About us");
  });

  it("keeps a field typed back to its saved value while the save waits, and asks about it (pages 0.1.1)", async () => {
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
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "B");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(patches).toBe(1);
    });
    await userEvent.clear(title);
    await userEvent.type(title, "A");
    answer(problem(409, "pages.changed", { page: full({ title: "B", version: 2 }) }));

    // Theirs is B and yours is A again: that's a choice, not theirs by default.
    expect(await screen.findByRole("radio", { name: "Keep mine" })).toBeInTheDocument();
    expect(title).toHaveValue("A");
  });

  it("still asks about a field typed back to its saved value when a retry meets another save (CodeRabbit on #138)", async () => {
    let answer: (value: Answer) => void = () => undefined;
    let patches = 0;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full({ title: "A" }) },
      [`PATCH ${ONE}`]: () => {
        patches += 1;
        if (patches === 1) {
          return new Promise<Answer>((resolve) => {
            answer = resolve;
          });
        }
        // The retry meets a third save, which changed the title.
        if (patches === 2) return problem(409, "pages.changed", { page: full({ title: "C", in_header: true, version: 3 }) });
        return { status: 200, body: full({ title: "C", in_header: true, body: "We make music. More.", version: 4 }) };
      },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "B");
    await userEvent.type(screen.getByRole("textbox", { name: "Page body" }), " More.");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(patches).toBe(1);
    });
    await userEvent.clear(title);
    await userEvent.type(title, "A");
    // Someone else changed only the menu: no question, so the save goes again with the body.
    answer(problem(409, "pages.changed", { page: full({ title: "A", in_header: true, version: 2 }) }));

    // Your A is still yours when the retry meets their C: a choice, not theirs by default.
    expect(await screen.findByRole("radio", { name: "Keep mine" })).toBeInTheDocument();
    expect(title).toHaveValue("A");
    expect(patches).toBe(2);
  });

  it("keeps what's typed while the save waits through the conflict's choice (pages 0.1.1)", async () => {
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
          : { status: 200, body: full({ title: "My title", body: "We make music. More.", version: 3 }) };
      },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "My title");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(patches).toBe(1);
    });
    const body = screen.getByRole("textbox", { name: "Page body" });
    await userEvent.type(body, " More.");
    answer(problem(409, "pages.changed", { page: full({ title: "Their title", version: 2 }) }));

    await userEvent.click(await screen.findByRole("radio", { name: "Keep mine" }));
    await userEvent.click(screen.getByRole("button", { name: /Save with these choices/ }));
    await waitFor(() => {
      expect(patches).toBe(2);
    });
    const second = sent.filter((each) => each.method === "PATCH")[1] as Request;
    expect(await json(second)).toEqual({ version: 2, title: "My title", body: "We make music. More." });
    expect(body).toHaveValue("We make music. More.");
  });

  it("shows a page as live once its publish lands, even while it asks about a field (pages 0.1.1)", async () => {
    let answer: (value: Answer) => void = () => undefined;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`POST ${ONE}/publish`]: () =>
        new Promise<Answer>((resolve) => {
          answer = resolve;
        }),
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    // Typed while the publish is on its way, and someone else saved the title too.
    await userEvent.type(title, "!");
    answer({ status: 200, body: full({ title: "Their title", status: "published", published_at: "2026-11-23T12:00:00+00:00", version: 2 }) });

    expect(await screen.findByText("Their title")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Back to the form" }));
    expect(await screen.findByText("Live. Saving changes the page on the site at once.")).toBeInTheDocument();
    expect(title).toHaveValue("About!");
  });

  it("takes in someone else's save an Unpublish answers with, keeping your changes (Codex on #121)", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full({ status: "published", published_at: "2026-11-20T12:00:00+00:00" }) },
      [`POST ${ONE}/unpublish`]: { status: 200, body: full({ title: "Their title", version: 2 }) },
      [`PATCH ${ONE}`]: { status: 200, body: full({ title: "Their title", body: "We make music. More.", version: 3 }) },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const body = await screen.findByRole("textbox", { name: "Page body" });
    await userEvent.type(body, " More.");
    await userEvent.click(screen.getByRole("button", { name: "Unpublish" }));

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Title" })).toHaveValue("Their title");
    });
    expect(body).toHaveValue("We make music. More.");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await waitFor(() => {
      expect(sent.some((each) => each.method === "PATCH")).toBe(true);
    });
    // Their title stays theirs: only the body, at their version.
    expect(await json(sent.find((each) => each.method === "PATCH") as Request)).toEqual({ version: 2, body: "We make music. More." });
  });

  it("asks field by field when an Unpublish answers with someone else's change to a field you changed too", async () => {
    routed({
      [`GET ${ONE}`]: { status: 200, body: full({ status: "published", published_at: "2026-11-20T12:00:00+00:00" }) },
      [`POST ${ONE}/unpublish`]: { status: 200, body: full({ title: "Their title", version: 2 }) },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "My title");
    await userEvent.click(screen.getByRole("button", { name: "Unpublish" }));

    expect(await screen.findByText("Their title")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Keep mine" })).toBeInTheDocument();
    expect(title).toHaveValue("My title");
  });

  it("closes the question once every field is kept as theirs, sending nothing more (CodeRabbit on #121)", async () => {
    let patches = 0;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: () => {
        patches += 1;
        return problem(409, "pages.changed", { page: full({ title: "Their title", version: 2 }) });
      },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "My title");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);
    await userEvent.click(await screen.findByRole("radio", { name: "Use theirs" }));
    await userEvent.click(screen.getByRole("button", { name: /Save with these choices/ }));

    await waitFor(() => {
      expect(screen.queryByRole("radio", { name: "Use theirs" })).toBeNull();
    });
    expect(title).toHaveValue("Their title");
    expect(patches).toBe(1);
  });

  it("shows their change to a field you didn't touch once a save is merged with theirs (CodeRabbit on #121)", async () => {
    let patches = 0;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full({ title: "A", body: "X" }) },
      [`PATCH ${ONE}`]: () => {
        patches += 1;
        return problem(409, "pages.changed", { page: full({ title: "B", body: "Y", version: 2 }) });
      },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.clear(title);
    await userEvent.type(title, "B");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Page body" })).toHaveValue("Y");
    });
    expect(title).toHaveValue("B");
    expect(screen.queryByText(/not saved/)).toBeNull();
    expect(patches).toBe(1); // theirs already says what you meant: nothing more to send
  });

  it("has the site's menus read again after a save (CodeRabbit on #121)", async () => {
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: { status: 200, body: full({ title: "About us", version: 2 }) },
    });
    const { queryClient } = renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });
    const menu = ["kernel", "slot-links", "pages", "nav.footer"];
    queryClient.setQueryData(menu, [{ label: "About", to: "/about" }]);

    const title = await screen.findByRole("textbox", { name: "Title" });
    await userEvent.type(title, " us");
    await userEvent.click(screen.getAllByRole("button", { name: "Save draft" })[0] as HTMLElement);

    await waitFor(() => {
      expect(queryClient.getQueryState(menu)?.isInvalidated).toBe(true);
    });
  });

  it("asks before leaving with changes", async () => {
    routed({ [`GET ${ONE}`]: { status: 200, body: full() }, [LIST]: { status: 200, body: { items: [] } } });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });
    await userEvent.type(await screen.findByRole("textbox", { name: "Title" }), "!");
    await userEvent.click(within(screen.getByRole("navigation", { name: "Admin" })).getByRole("link", { name: "Pages" }));
    expect(await screen.findByRole("dialog", { name: "You have changes that aren't saved" })).toBeInTheDocument();
  });

  it("shows the body as the site would draw it under Preview", async () => {
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      "POST /api/pages/admin/preview": { status: 200, body: { html: "<p>We make <strong>music</strong>.</p>" } },
    });
    renderApp({ path: `/admin/pages/${ID}`, modules: [pages], session: editor });
    await screen.findByRole("textbox", { name: "Title" });
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(await screen.findByText("music")).toBeInTheDocument();
  });
});
