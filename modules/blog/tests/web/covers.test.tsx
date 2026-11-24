/**
 * Draw a cover in the post editor (decision 0065; `dev plans/contracts/blog-covers.md`
 * §7, and the AdminPost board at canvas version 104): the button only with a
 * working key and storage; draw, revise, then use, which fills the Cover field;
 * Custom's own fields; a failure in its words. Every answer comes from a fetch
 * that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "@/kernel/testing";

import type { Full } from "../../web/api";
import { drawnAddress, themeColours } from "../../web/components/CoverDialog";
import blog from "../../web/module.web";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const ID = "11111111-1111-4111-8111-111111111111";
const ONE = `/api/blog/admin/posts/${ID}`;
const ME = "00000000-0000-4000-8000-000000000001";
const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630"><rect width="1200" height="630" fill="#101828"/></svg>';
const FAILED = "The AI couldn't draw a cover this time. Try again, or change what you asked for.";
const COVER = {
  id: "61111111-1111-4111-8111-111111111111",
  url: "https://files.test/media/cover.png",
  srcset: "https://files.test/media/cover.png 2400w",
  width: 2400,
  height: 1260,
  alt: "A gold ring on a dark ground",
  decorative: false,
};
const READY = {
  status: 200,
  body: { ready: true, unreadable: false, styles: [] },
};

const writer = testUser({
  roles: ["member", "editor"],
  second_factor: true,
  permissions: ["blog.post.write", "blog.post.publish", "media.image.upload", "kernel.ai.write"],
});

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = {
        "GET /api/blog/admin/categories": { status: 200, body: { items: [] } },
        "GET /api/blog/admin/authors": {
          status: 200,
          body: { items: [{ id: ME, name: "Pat Writer" }] },
        },
        [`GET ${ONE}`]: { status: 200, body: full() },
        "GET /api/kernel/ai": READY,
        "GET /api/blog/admin/covers": { status: 200, body: { storage: true } },
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

function full(overrides: Partial<Full> = {}): Full {
  return {
    id: ID,
    title: "Ten years",
    slug: "ten-years",
    status: "draft",
    category: null,
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

async function bodyOf(sent: Request[], path: string, n = 0): Promise<Record<string, unknown>> {
  const found = sent.filter((each) => each.method === "POST" && new URL(each.url).pathname === path)[n];
  if (!found) throw new Error(`Nothing was sent to ${path}`);
  return (await found.json()) as Record<string, unknown>;
}

describe("Draw a cover", () => {
  it.each([
    [
      "no key works",
      {
        "GET /api/kernel/ai": {
          status: 200,
          body: { ready: false, unreadable: false, styles: [] },
        },
      },
    ],
    [
      "storage is off",
      {
        "GET /api/blog/admin/covers": { status: 200, body: { storage: false } },
      },
    ],
  ])("isn't offered while %s", async (_, answers) => {
    routed(answers);
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: writer });

    expect(await screen.findByRole("button", { name: "Choose a cover" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Draw a cover" })).toBeNull();
    });
  });

  it("isn't offered, or asked about, to someone who may not use the AI", async () => {
    const sent = routed({});
    const plain = testUser({
      ...writer,
      permissions: ["blog.post.write", "media.image.upload"],
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: plain });

    expect(await screen.findByRole("button", { name: "Choose a cover" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Draw a cover" })).toBeNull();
    expect(sent.some((each) => new URL(each.url).pathname.endsWith("/covers"))).toBe(false);
    expect(sent.some((each) => new URL(each.url).pathname === "/api/kernel/ai")).toBe(false);
  });

  it("draws a cover, changes it, then uses it, which fills the Cover field", async () => {
    let draws = 0;
    const sent = routed({
      "POST /api/blog/admin/covers/draw": () => {
        draws += 1;
        return {
          status: 200,
          body: {
            svg: SVG.replace("#101828", draws > 1 ? "#202020" : "#101828"),
            alt: "A dark field",
          },
        };
      },
      "POST /api/blog/admin/covers": { status: 201, body: { cover: COVER } },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: writer });

    const opener = await screen.findByRole("button", { name: "Draw a cover" });
    // It comes before Change (here, Choose a cover), in one row.
    expect(opener.compareDocumentPosition(screen.getByRole("button", { name: "Choose a cover" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await userEvent.click(opener);
    const dialog = within(await screen.findByRole("dialog", { name: "Draw a cover" }));
    expect(dialog.getByRole("heading", { name: "Draw a cover" })).toHaveFocus();
    expect(dialog.getByText("The post's title, large, with one accent line and quiet shapes.")).toBeInTheDocument();
    expect(dialog.queryByRole("switch", { name: "In the site's colours" })).toBeNull();
    expect(dialog.getByRole("switch", { name: "With the site's name" })).toBeChecked();

    await userEvent.click(dialog.getByRole("button", { name: "Draw" }));
    const drawn = await dialog.findByRole("img", { name: "A dark field" });
    expect(drawn).toHaveAttribute("src", drawnAddress(SVG));
    expect(dialog.getByRole("heading", { name: "Draw a cover" })).toHaveFocus();
    expect(await bodyOf(sent, "/api/blog/admin/covers/draw")).toEqual({
      title: "Ten years",
      summary: "A decade of shows.",
      body: "We booked a room.",
      style: "editorial",
      wordmark: true,
    });

    const alt = dialog.getByRole("textbox", { name: "Alt text" });
    expect(alt).toHaveValue("A dark field");
    expect(dialog.getByRole("button", { name: "Change it" })).toBeDisabled();
    await userEvent.type(dialog.getByRole("textbox", { name: "What to change" }), "Warmer.");
    await userEvent.click(dialog.getByRole("button", { name: "Change it" }));
    await waitFor(() => {
      expect(draws).toBe(2);
    });
    expect(await bodyOf(sent, "/api/blog/admin/covers/draw", 1)).toMatchObject({
      current: SVG,
      changes: "Warmer.",
    });
    await waitFor(() => {
      expect(dialog.getByRole("textbox", { name: "What to change" })).toHaveValue("");
    });

    await userEvent.clear(alt);
    await userEvent.type(alt, "  A gold ring on a dark ground ");
    await userEvent.click(dialog.getByRole("button", { name: "Use this cover" }));
    expect(await screen.findByText("The cover is in place. Save the post to keep it.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Draw a cover" })).toBeNull();
    expect(await bodyOf(sent, "/api/blog/admin/covers")).toEqual({
      svg: SVG.replace("#101828", "#202020"),
      alt: "A gold ring on a dark ground",
    });
    expect(screen.getByRole("img", { name: "A gold ring on a dark ground" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Draw a cover" })).toHaveFocus();
    expect(screen.getAllByRole("button", { name: "Save draft" }).length).toBeGreaterThan(0);
  });

  it("asks Custom what to draw, and Draw waits for words", async () => {
    const sent = routed({
      "POST /api/blog/admin/covers/draw": {
        status: 200,
        body: { svg: SVG, alt: "The sea" },
      },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: writer });

    await userEvent.click(await screen.findByRole("button", { name: "Draw a cover" }));
    const dialog = within(await screen.findByRole("dialog", { name: "Draw a cover" }));
    await userEvent.selectOptions(dialog.getByRole("combobox", { name: "Style" }), "custom");
    expect(dialog.getByText("Drawn from what you describe.")).toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "Draw" })).toBeDisabled();
    await userEvent.click(dialog.getByRole("switch", { name: "In the site's colours" }));
    await userEvent.click(dialog.getByRole("switch", { name: "With the site's name" }));
    await userEvent.type(dialog.getByRole("textbox", { name: "What to draw" }), "The sea at night");
    await userEvent.click(dialog.getByRole("button", { name: "Draw" }));

    expect(await dialog.findByRole("img", { name: "The sea" })).toBeInTheDocument();
    expect(await bodyOf(sent, "/api/blog/admin/covers/draw")).toEqual({
      title: "Ten years",
      summary: "A decade of shows.",
      body: "We booked a room.",
      style: "custom",
      description: "The sea at night",
      wordmark: false,
    });
  });

  it("says a failure in its words, and Cancel gives focus back", async () => {
    routed({
      "POST /api/blog/admin/covers/draw": {
        status: 502,
        body: {
          type: "urn:mechframe:problem:kernel.ai_failed",
          title: "Refused",
          status: 502,
          detail: FAILED,
          code: "kernel.ai_failed",
        },
      },
    });
    renderApp({ path: `/admin/blog/${ID}`, modules: [blog], session: writer });

    const opener = await screen.findByRole("button", { name: "Draw a cover" });
    await userEvent.click(opener);
    const dialog = within(await screen.findByRole("dialog", { name: "Draw a cover" }));
    await userEvent.click(dialog.getByRole("button", { name: "Draw" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent(FAILED);
    expect(dialog.getByRole("button", { name: "Draw" })).toBeEnabled();

    await userEvent.click(dialog.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog", { name: "Draw a cover" })).toBeNull();
    expect(opener).toHaveFocus();
  });
});

describe("the theme's colours", () => {
  it("are read from the tokens as #rrggbb, or not at all", () => {
    const element = document.createElement("div");
    document.body.append(element);
    element.style.setProperty("--mf-color-surface", " #0D1224");
    element.style.setProperty("--mf-color-text", "#ccd");
    element.style.setProperty("--mf-color-accent", "#FF7A1F");
    expect(themeColours(element)).toEqual({
      ground: "#0d1224",
      ink: "#ccccdd",
      accent: "#ff7a1f",
    });

    element.style.setProperty("--mf-color-accent", "oklch(70% 0.2 50)");
    expect(themeColours(element)).toBeNull();
    element.remove();
  });
});
