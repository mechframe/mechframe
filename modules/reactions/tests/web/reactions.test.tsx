/**
 * reactions' row (`dev plans/contracts/reactions.md` §7): each reaction with its
 * count and name, pressed when it's the reader's own, in the palette's order;
 * pressing and taking back, the count changed at once and put back on a refusal;
 * signed out to sign-in; an unverified member told to verify; nothing drawn for a
 * thing that isn't live or a read that fails; and the row in `ReactionParts`.
 * Every answer comes from a fetch that answers by method and path.
 */
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReactionParts, SESSION_KEY } from "@/kernel";
import { renderWithKernel, testUser } from "@/kernel/testing";

import type { Counted, Reactions } from "../../web/api";
import reactions from "../../web/module.web";
import ReactionRow from "../../web/ReactionRow";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const ID = "11111111-1111-4111-8111-111111111111";
const PRESS = (key: string) => `/api/reactions/blog.post/${ID}/${key}`;

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const found = answers[`${request.method} ${new URL(request.url).pathname}`];
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

function problem(status: number, code: string, detail: string): Answer {
  return { status, body: { type: `urn:mechframe:problem:${code}`, title: "Refused", status, detail, code } };
}

const PALETTE = [
  { key: "fire", label: "Fire" },
  { key: "love", label: "Love" },
  { key: "mind_blown", label: "Mind blown" },
];

function counted(counts: Partial<Record<string, number>> = {}, mine: string[] = []): Counted {
  const all: Record<string, number> = { fire: 0, love: 0, mind_blown: 0 };
  for (const [key, n] of Object.entries(counts)) if (n !== undefined) all[key] = n;
  return { id: ID, counts: all, mine };
}

function read(item: Counted | null = counted(), palette = PALETTE): Answer {
  const body: Reactions = { palette, items: item ? [item] : [] };
  return { status: 200, body };
}

const member = testUser();

function draw(options: { session?: typeof member | null; path?: string } = {}) {
  return renderWithKernel(<ReactionRow type="blog.post" id={ID} />, {
    session: options.session === undefined ? member : options.session,
    path: options.path ?? "/blog/ten-years",
  });
}

const button = (name: RegExp) => screen.findByRole("button", { name });

describe("the row", () => {
  it("draws each reaction with its count and name, the reader's own pressed", async () => {
    const sent = routed({ "GET /api/reactions": read(counted({ fire: 3, mind_blown: 1 }, ["fire"])) });
    draw();
    expect(await screen.findByRole("group", { name: "Reactions" })).toBeInTheDocument();
    expect(await button(/Fire/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Fire, 3" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Love, 0" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Mind blown, 1" })).toBeInTheDocument();
    const url = new URL(sent[0]?.url ?? "");
    expect(url.searchParams.get("type")).toBe("blog.post");
    expect(url.searchParams.getAll("id")).toEqual([ID]);
  });

  it("draws the palette's reactions in its order", async () => {
    routed({
      "GET /api/reactions": read({ id: ID, counts: { love: 2, fire: 0 }, mine: [] }, [
        { key: "love", label: "Love" },
        { key: "fire", label: "Fire" },
      ]),
    });
    draw();
    await button(/Love/);
    expect(screen.getAllByRole("button").map((each) => each.getAttribute("aria-label"))).toEqual(["Love, 2", "Fire, 0"]);
    expect(screen.getAllByRole("button").map((each) => each.textContent)).toEqual(["2", "0"]);
  });

  it("draws nothing for a thing the site doesn't show, or a read that fails", async () => {
    // Each waits for its read to have answered before it looks (cubic on #170).
    routed({ "GET /api/reactions": read(null) });
    const { container, queryClient, unmount } = draw();
    await waitFor(() => {
      expect(queryClient.getQueryCache().findAll({ queryKey: ["get", "/api/reactions"] })[0]?.state.status).toBe("success");
    });
    expect(container).toBeEmptyDOMElement();
    unmount();
    routed({ "GET /api/reactions": problem(404, "reactions.unknown_type", "Nothing on this site is a blog.post.") });
    const failed = draw();
    await waitFor(() => {
      expect(failed.queryClient.getQueryCache().findAll({ queryKey: ["get", "/api/reactions"] })[0]?.state.status).toBe("error");
    });
    expect(failed.container).toBeEmptyDOMElement();
  });

  it("goes when a read again fails, though the last answer is kept (cubic on #170)", async () => {
    routed({ "GET /api/reactions": read(counted({ fire: 2 })) });
    const { queryClient } = draw();
    await button(/Fire, 2/);
    routed({ "GET /api/reactions": problem(503, "kernel.unavailable", "The site is busy.") });
    await queryClient.invalidateQueries({ queryKey: ["get", "/api/reactions"] });
    await waitFor(() => {
      expect(screen.queryByRole("group", { name: "Reactions" })).not.toBeInTheDocument();
    });
  });
});

describe("pressing", () => {
  it("adds the reader's reaction at once and keeps the server's count", async () => {
    let answer: (value: Answer) => void = () => undefined;
    const sent = routed({
      "GET /api/reactions": read(counted({ fire: 3 })),
      [`PUT ${PRESS("fire")}`]: () =>
        new Promise<Answer>((resolve) => {
          answer = resolve;
        }),
    });
    draw();
    await userEvent.click(await button(/Fire, 3/));
    expect(screen.getByRole("button", { name: "Fire, 4" })).toHaveAttribute("aria-pressed", "true");
    answer({ status: 200, body: counted({ fire: 5 }, ["fire"]) });
    expect(await button(/Fire, 5/)).toHaveAttribute("aria-pressed", "true");
    expect(sent.filter((request) => request.method === "PUT")).toHaveLength(1);
  });

  it("sends two presses one after the other, and keeps both (Codex on #170)", async () => {
    let fire: (value: Answer) => void = () => undefined;
    const sent = routed({
      "GET /api/reactions": read(counted()),
      // The first answer is the row as its own write saw it, before the second.
      [`PUT ${PRESS("fire")}`]: () =>
        new Promise<Answer>((resolve) => {
          fire = resolve;
        }),
      [`PUT ${PRESS("love")}`]: { status: 200, body: counted({ fire: 1, love: 1 }, ["fire", "love"]) },
    });
    draw();
    await userEvent.click(await button(/Fire, 0/));
    await userEvent.click(await button(/Love, 0/));
    expect(screen.getByRole("button", { name: "Love, 1" })).toHaveAttribute("aria-pressed", "true");
    // Love's write waits for Fire's answer.
    expect(sent.filter((request) => request.method === "PUT")).toHaveLength(1);
    fire({ status: 200, body: counted({ fire: 1 }, ["fire"]) });
    await waitFor(() => {
      expect(sent.filter((request) => request.method === "PUT")).toHaveLength(2);
    });
    expect(await button(/Love, 1/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Fire, 1" })).toHaveAttribute("aria-pressed", "true");
  });

  it("takes the reader's own back", async () => {
    const sent = routed({
      "GET /api/reactions": read(counted({ love: 2 }, ["love"])),
      [`DELETE ${PRESS("love")}`]: { status: 200, body: counted({ love: 1 }) },
    });
    draw();
    await userEvent.click(await button(/Love, 2/));
    expect(await button(/Love, 1/)).toHaveAttribute("aria-pressed", "false");
    expect(sent.some((request) => request.method === "DELETE")).toBe(true);
  });

  it("puts the count back and says why when the server refuses", async () => {
    routed({
      "GET /api/reactions": read(counted({ fire: 3 })),
      [`PUT ${PRESS("fire")}`]: problem(403, "kernel.timed_out", "You can't post until your time-out ends."),
    });
    draw();
    await userEvent.click(await button(/Fire, 3/));
    expect(await screen.findByText("You can't post until your time-out ends.")).toBeInTheDocument();
    expect(await button(/Fire, 3/)).toHaveAttribute("aria-pressed", "false");
  });

  it("sends a reader who isn't signed in to sign in, and back", async () => {
    const sent = routed({ "GET /api/reactions": read(counted({ fire: 3 })) });
    const { router } = draw({ session: null, path: "/blog/ten-years?from=home" });
    await userEvent.click(await button(/Fire, 3/));
    expect(router.state.location.pathname).toBe("/sign-in");
    expect(new URLSearchParams(router.state.location.search).get("next")).toBe("/blog/ten-years?from=home");
    expect(sent.some((request) => request.method !== "GET")).toBe(false);
  });

  it("draws no late answer once the reader has signed out (CodeRabbit on #170)", async () => {
    let fire: (value: Answer) => void = () => undefined;
    routed({
      "GET /api/reactions": read(counted({ fire: 3 })),
      [`PUT ${PRESS("fire")}`]: () =>
        new Promise<Answer>((resolve) => {
          fire = resolve;
        }),
    });
    const { queryClient } = draw();
    await userEvent.click(await button(/Fire, 3/));
    expect(screen.getByRole("button", { name: "Fire, 4" })).toHaveAttribute("aria-pressed", "true");
    // Signed out, and the row read again for no one; the member's answer comes at once,
    // before the cache has told the row (CodeRabbit and cubic on #170).
    const row = ["get", "/api/reactions", { params: { query: { type: "blog.post", id: [ID] } } }];
    act(() => {
      queryClient.setQueryData(SESSION_KEY, null);
      queryClient.setQueryData(row, read(counted({ fire: 4 })).body);
      fire({ status: 200, body: counted({ fire: 4 }, ["fire"]) });
    });
    await new Promise((resolve) => setTimeout(resolve, 50));
    // Dropped, and read again for no one: never the member's own.
    expect(queryClient.getQueryData<Reactions>(row)?.items[0]?.mine).toEqual([]);
    expect(await button(/Fire, /)).toHaveAttribute("aria-pressed", "false");
  });

  it("never sends a queued press once another person is signed in (CodeRabbit on #170)", async () => {
    let fire: (value: Answer) => void = () => undefined;
    const sent = routed({
      "GET /api/reactions": read(counted()),
      [`PUT ${PRESS("fire")}`]: () =>
        new Promise<Answer>((resolve) => {
          fire = resolve;
        }),
      [`PUT ${PRESS("love")}`]: { status: 200, body: counted({ love: 1 }, ["love"]) },
    });
    const { queryClient } = draw();
    await userEvent.click(await button(/Fire, 0/));
    await userEvent.click(await button(/Love, 0/));
    // The answer comes at once, before the cache has told the row (CodeRabbit and cubic on #170).
    queryClient.setQueryData(SESSION_KEY, testUser({ id: "00000000-0000-4000-8000-000000000002" }));
    fire({ status: 200, body: counted({ fire: 1 }, ["fire"]) });
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(sent.filter((request) => request.method === "PUT").map((request) => new URL(request.url).pathname)).toEqual([PRESS("fire")]);
  });

  it("reads the row again when a queued press is dropped because the row has gone (cubic on #170)", async () => {
    let fire: (value: Answer) => void = () => undefined;
    const sent = routed({
      "GET /api/reactions": read(counted()),
      [`PUT ${PRESS("fire")}`]: () =>
        new Promise<Answer>((resolve) => {
          fire = resolve;
        }),
      [`PUT ${PRESS("love")}`]: { status: 200, body: counted({ love: 1 }, ["love"]) },
    });
    const { queryClient, unmount } = draw();
    await userEvent.click(await button(/Fire, 0/));
    await userEvent.click(await button(/Love, 0/));
    unmount();
    fire({ status: 200, body: counted({ fire: 1 }, ["fire"]) });
    const row = ["get", "/api/reactions", { params: { query: { type: "blog.post", id: [ID] } } }];
    await waitFor(() => {
      expect(queryClient.getQueryState(row)?.isInvalidated).toBe(true);
    });
    expect(sent.filter((request) => request.method === "PUT")).toHaveLength(1);
  });

  it("lets an unverified member take their own back (CodeRabbit on #170)", async () => {
    const sent = routed({
      "GET /api/reactions": read(counted({ love: 1 }, ["love"])),
      [`DELETE ${PRESS("love")}`]: { status: 200, body: counted() },
    });
    draw({ session: testUser({ verified: false }) });
    await userEvent.click(await button(/Love, 1/));
    expect(await button(/Love, 0/)).toHaveAttribute("aria-pressed", "false");
    expect(sent.some((request) => request.method === "DELETE")).toBe(true);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does nothing while who's signed in isn't known yet (cubic on #170)", async () => {
    const sent = routed({ "GET /api/reactions": read(counted({ fire: 3 })) });
    const { router } = renderWithKernel(<ReactionRow type="blog.post" id={ID} />, {
      session: "loading",
      path: "/blog/ten-years",
    });
    await userEvent.click(await button(/Fire, 3/));
    expect(router.state.location.pathname).toBe("/blog/ten-years");
    expect(sent.some((request) => request.method !== "GET")).toBe(false);
  });

  it("asks an unverified member to verify first, sending nothing", async () => {
    const sent = routed({ "GET /api/reactions": read(counted()) });
    draw({ session: testUser({ verified: false }) });
    await userEvent.click(await button(/Love, 0/));
    expect(await screen.findByRole("status")).toHaveTextContent("Verify your email address first.");
    expect(screen.getByRole("link", { name: "Go to your account" })).toHaveAttribute("href", "/account");
    expect(sent.some((request) => request.method !== "GET")).toBe(false);
  });

  it("asks to verify when the server says the address isn't", async () => {
    routed({
      "GET /api/reactions": read(counted()),
      [`PUT ${PRESS("love")}`]: problem(403, "reactions.email_unverified", "Verify your email address first."),
    });
    draw();
    await userEvent.click(await button(/Love, 0/));
    expect(await screen.findByRole("status")).toHaveTextContent("Verify your email address first.");
    expect(screen.getByRole("button", { name: "Love, 0" })).toHaveAttribute("aria-pressed", "false");
  });
});

describe("ReactionParts", () => {
  it("draws the row with reactions on, and nothing with it off", async () => {
    routed({ "GET /api/reactions": read(counted({ fire: 1 })) });
    renderWithKernel(<ReactionParts type="blog.post" id={ID} />, { modules: [reactions], session: member });
    expect(await button(/Fire, 1/)).toBeInTheDocument();
  });

  it("draws nothing while reactions is off", () => {
    routed({ "GET /api/reactions": read() });
    const { container } = renderWithKernel(<ReactionParts type="blog.post" id={ID} />, {
      modules: [reactions],
      on: [],
    });
    expect(container).toBeEmptyDOMElement();
  });
});
