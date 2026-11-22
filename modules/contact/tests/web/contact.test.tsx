/**
 * contact's web (`dev plans/contracts/contact.md`): the Contact page and its
 * form, the form alone as a site's own page draws it, the Inbox with its tabs,
 * its open message and its actions, the Export's CSV, and the Settings
 * section. Every answer comes from a fetch that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, renderWithKernel, testUser } from "@/kernel/testing";

import { morePages, toCsv, type InboxItem, type InboxMessage, type InboxPage } from "../../web/api";
import contact from "../../web/module.web";
import { ContactForm } from "@/modules/contact/public";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const FORM_PATH = "GET /api/contact/form";
const SEND = "POST /api/contact/messages";
const LIST = "GET /api/contact/admin/messages";
const ID = "11111111-1111-4111-8111-111111111111";
const OTHER = "22222222-2222-4222-8222-222222222222";
const ONE = `/api/contact/admin/messages/${ID}`;

const FORM = {
  intro: "Write to us and we'll reply by email.",
  topics: [
    { key: "question", label: "A question" },
    { key: "work", label: "Working together" },
  ],
};

const BASE: Answers = {
  [FORM_PATH]: { status: 200, body: FORM },
  "GET /api/kernel/notifications": { status: 200, body: { items: [], next_cursor: null, unread: 0 } },
  "GET /api/kernel/admin/attention": { status: 200, body: { items: [] } },
};

function routed(answers: Answers) {
  const sent: Request[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      sent.push(request.clone());
      const all: Answers = { ...BASE, ...answers };
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

const sentTo = (sent: Request[], method: string, path: string) =>
  sent.filter((request) => request.method === method && new URL(request.url).pathname === path);

async function json(request: Request): Promise<Record<string, unknown>> {
  return (await request.json()) as Record<string, unknown>;
}

async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByRole("textbox", { name: "Name" }), "Rae Okafor");
  await user.type(screen.getByRole("textbox", { name: "Email" }), "rae@example.com");
  await user.selectOptions(screen.getByRole("combobox", { name: "What it's about" }), "work");
  await user.type(screen.getByRole("textbox", { name: "Message" }), "Can you play in March?");
}

describe("the Contact page", () => {
  it("draws the intro and the topics, sends the message with the bot check's proof, and thanks the sender", async () => {
    const sent = routed({ [SEND]: { status: 202, body: { received: true } } });
    const user = userEvent.setup();
    renderApp({ path: "/contact", modules: [contact] });

    expect(await screen.findByRole("heading", { level: 1, name: "Contact" })).toBeInTheDocument();
    expect(await screen.findByText(FORM.intro)).toBeInTheDocument();
    const topics = screen.getByRole("combobox", { name: "What it's about" });
    expect(within(topics).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Choose one",
      "A question",
      "Working together",
    ]);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Send message" }));

    const thanks = await screen.findByRole("status");
    expect(within(thanks).getByRole("heading", { name: "Message sent" })).toBeInTheDocument();
    expect(thanks).toHaveTextContent("Thanks for writing. We’ll reply by email.");
    await waitFor(() => {
      expect(thanks).toHaveFocus();
    });
    const [post] = sentTo(sent, "POST", "/api/contact/messages");
    expect(post).toBeDefined();
    const body = await json(post as Request);
    expect(body).toMatchObject({
      name: "Rae Okafor",
      email: "rae@example.com",
      topic: "work",
      message: "Can you play in March?",
      wants_news: false,
      bot: { website: "" },
    });
    expect(typeof (body.bot as { elapsed_ms: unknown }).elapsed_ms).toBe("number");

    await user.click(screen.getByRole("button", { name: "Send another" }));
    expect(await screen.findByRole("textbox", { name: "Name" })).toHaveValue("");
  });

  it("checks the fields before sending anything, then shows what the server said of one", async () => {
    const sent = routed({
      [SEND]: problem(422, "kernel.invalid_request", {
        errors: { "body.email": ["Enter one email address, like name@example.com."] },
      }),
    });
    const user = userEvent.setup();
    renderApp({ path: "/contact", modules: [contact] });

    await user.click(await screen.findByRole("button", { name: "Send message" }));
    const name = screen.getByRole("textbox", { name: "Name" });
    expect(name).toHaveAccessibleDescription("Enter your name.");
    expect(name).toHaveFocus();
    expect(sentTo(sent, "POST", "/api/contact/messages")).toHaveLength(0);

    await fill(user);
    await user.click(screen.getByRole("button", { name: "Send message" }));
    const email = screen.getByRole("textbox", { name: "Email" });
    await waitFor(() => {
      expect(email).toHaveAccessibleDescription("Enter one email address, like name@example.com.");
    });
    expect(email).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("says to wait when too many messages came from one address", async () => {
    routed({ [SEND]: problem(429, "kernel.rate_limited") });
    const user = userEvent.setup();
    renderApp({ path: "/contact", modules: [contact] });
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please wait an hour and try again.");
  });

  it("offers news and releases only while campaigns is on, and sends the choice", async () => {
    routed({ [SEND]: { status: 202, body: { received: true } } });
    const first = renderApp({ path: "/contact", modules: [contact], on: ["contact"] });
    await screen.findByRole("textbox", { name: "Name" });
    expect(screen.queryByRole("checkbox", { name: "Send me news and releases too" })).toBeNull();
    first.unmount();

    const sent = routed({ [SEND]: { status: 202, body: { received: true } } });
    const user = userEvent.setup();
    renderApp({ path: "/contact", modules: [contact], on: ["contact", "campaigns"] });
    await fill(user);
    const news = await screen.findByRole("checkbox", { name: "Send me news and releases too" });
    expect(news).not.toBeChecked();
    await user.click(news);
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByRole("status");
    const [post] = sentTo(sent, "POST", "/api/contact/messages");
    expect(await json(post as Request)).toMatchObject({ wants_news: true });
  });

  it("puts Contact in the footer's menu", async () => {
    routed({});
    renderApp({ path: "/contact", modules: [contact] });
    const footer = await screen.findByRole("navigation", { name: "Footer" });
    expect(within(footer).getByRole("link", { name: "Contact" })).toHaveAttribute("href", "/contact");
  });
});

describe("the form on a site's own page (public.ts)", () => {
  it("draws alone and tells the page once it's sent", async () => {
    routed({ [SEND]: { status: 202, body: { received: true } } });
    const onSent = vi.fn();
    const user = userEvent.setup();
    renderWithKernel(<ContactForm onSent={onSent} />);
    await fill(user);
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByRole("status");
    expect(onSent).toHaveBeenCalledTimes(1);
  });
});

// --- the Inbox ---------------------------------------------------------------------------

const reader = testUser({
  roles: ["member", "admin"],
  second_factor: true,
  permissions: ["contact.message.manage", "kernel.settings.manage"],
});

function item(overrides: Partial<InboxItem> = {}): InboxItem {
  return {
    id: ID,
    name: "Rae Okafor",
    topic_label: "Working together",
    first_line: "Can you play in March?",
    status: "new",
    first: true,
    received_at: "2026-11-20T12:00:00+00:00",
    ...overrides,
  };
}

function message(overrides: Partial<InboxMessage> = {}): InboxMessage {
  return {
    id: ID,
    name: "Rae Okafor",
    email: "rae@example.com",
    topic_label: "Working together",
    message: "Can you play in March?\n\nWe have a night free.",
    wants_news: true,
    status: "new",
    held_reason: null,
    received_at: "2026-11-20T12:00:00+00:00",
    status_at: "2026-11-20T12:00:00+00:00",
    ...overrides,
  };
}

function page(items: InboxItem[], overrides: Partial<InboxPage> = {}): Answer {
  const body: InboxPage = {
    items,
    next_cursor: null,
    counts: { new: 2, replied: 1, archived: 0, spam: 1 },
    waiting: {
      tone: "warning",
      what: "2 new messages are waiting",
      why: "The oldest came in 2 days ago and hasn't had a reply.",
      label: "Open the first",
      to: `/admin/contact/${ID}`,
    },
    ...overrides,
  };
  return { status: 200, body };
}

describe("the Inbox", () => {
  it("shows the waiting card, each tab's count and the list, and opens a message beside it", async () => {
    routed({ [LIST]: page([item(), item({ id: OTHER, name: "Sam Ito", status: "replied", first: false })]), [`GET ${ONE}`]: { status: 200, body: message() } });
    renderApp({ path: `/admin/contact/${ID}`, modules: [contact], session: reader });

    expect(await screen.findByRole("heading", { level: 1, name: "Inbox" })).toBeInTheDocument();
    expect(await screen.findByText("2 new messages are waiting")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open the first" })).toHaveAttribute("href", `/admin/contact/${ID}`);
    const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent);
    expect(tabs).toEqual(["All (3)", "New (2)", "Replied (1)", "Archived (0)", "Spam (1)"]);
    const list = screen.getByRole("list", { name: "Messages" });
    const rows = within(list).getAllByRole("link");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("aria-current", "true");
    expect(within(list).getByText("Replied")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { level: 2, name: "Rae Okafor" })).toBeInTheDocument();
    expect(screen.getByText("Wants the newsletter")).toBeInTheDocument();
    expect(screen.getByText(/We have a night free\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reply by email" })).toHaveAttribute(
      "href",
      "mailto:rae%40example.com?subject=Re%3A%20Working%20together",
    );
    expect(screen.getByText("Replies go from your own email, so the conversation carries on there.")).toBeInTheDocument();
  });

  it("marks a message replied, and says so", async () => {
    const sent = routed({
      [LIST]: page([item()]),
      [`GET ${ONE}`]: { status: 200, body: message() },
      [`POST ${ONE}/status`]: { status: 200, body: message({ status: "replied" }) },
    });
    const user = userEvent.setup();
    renderApp({ path: `/admin/contact/${ID}`, modules: [contact], session: reader });
    await user.click(await screen.findByRole("button", { name: "Mark as replied" }));
    expect(await screen.findByText("Marked as replied.")).toBeInTheDocument();
    const [post] = sentTo(sent, "POST", `${ONE}/status`);
    expect(await json(post as Request)).toEqual({ status: "replied" });
    expect(screen.queryByRole("button", { name: "Mark as replied" })).toBeNull();
  });

  it("says why a message was set apart, and lets it out of spam", async () => {
    const sent = routed({
      [LIST]: page([item({ status: "spam" })]),
      [`GET ${ONE}`]: { status: 200, body: message({ status: "spam", held_reason: "links" }) },
      [`POST ${ONE}/status`]: { status: 200, body: message({ status: "new", held_reason: "links" }) },
    });
    const user = userEvent.setup();
    const { router } = renderApp({ path: `/admin/contact/${ID}?tab=spam`, modules: [contact], session: reader });
    expect(await screen.findByText("Set apart: It holds more links than the filters allow.")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Spam (1)" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("button", { name: "Archive" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Not spam" }));
    await screen.findByText("Back in New.");
    const [post] = sentTo(sent, "POST", `${ONE}/status`);
    expect(await json(post as Request)).toEqual({ status: "new" });
    const requested = sentTo(sent, "GET", "/api/contact/admin/messages").map((request) => new URL(request.url).searchParams.get("status"));
    expect(requested).toContain("spam");
    expect(router.state.location.search).toBe("?tab=spam");
  });

  it("asks before deleting a message for good, then goes back to the list", async () => {
    const sent = routed({
      [LIST]: page([item()]),
      [`GET ${ONE}`]: { status: 200, body: message() },
      [`DELETE ${ONE}`]: { status: 204 },
    });
    const user = userEvent.setup();
    const { router } = renderApp({ path: `/admin/contact/${ID}`, modules: [contact], session: reader });
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete this message?" });
    expect(sentTo(sent, "DELETE", ONE)).toHaveLength(0);
    await user.click(within(dialog).getByRole("button", { name: "Delete it" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/admin/contact");
    });
    expect(sentTo(sent, "DELETE", ONE)).toHaveLength(1);
  });

  it("shows more of a long tab, from the cursor", async () => {
    const sent = routed({
      [LIST]: (request) =>
        new URL(request.url).searchParams.get("cursor") === "c1"
          ? page([item({ id: OTHER, name: "Sam Ito" })])
          : page([item()], { next_cursor: "c1" }),
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/contact", modules: [contact], session: reader });
    await user.click(await screen.findByRole("button", { name: "Show more" }));
    const list = screen.getByRole("list", { name: "Messages" });
    await waitFor(() => {
      expect(within(list).getAllByRole("link")).toHaveLength(2);
    });
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
    expect(sentTo(sent, "GET", "/api/contact/admin/messages").some((request) => new URL(request.url).searchParams.get("cursor") === "c1")).toBe(true);
  });

  it("exports every page of the tab into one CSV (Codex on #125)", async () => {
    const made: Blob[] = [];
    const createObjectURL = vi.fn((blob: Blob) => {
      made.push(blob);
      return "blob:export";
    });
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const sent = routed({
      [LIST]: page([item()]),
      "GET /api/contact/admin/messages/export": (request) =>
        new URL(request.url).searchParams.get("cursor") === "e1"
          ? { status: 200, body: { items: [message({ id: OTHER, name: "Sam Ito" })], next_cursor: null } }
          : { status: 200, body: { items: [message()], next_cursor: "e1" } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/contact?tab=new", modules: [contact], session: reader });
    await user.click(await screen.findByRole("button", { name: "Export" }));
    await waitFor(() => {
      expect(made).toHaveLength(1);
    });
    const exports = sentTo(sent, "GET", "/api/contact/admin/messages/export");
    expect(exports.map((request) => new URL(request.url).searchParams.get("cursor"))).toEqual([null, "e1"]);
    expect(exports.every((request) => new URL(request.url).searchParams.get("status") === "new")).toBe(true);
    const csv = await (made[0] as Blob).text();
    expect(csv).toContain('"Rae Okafor"');
    expect(csv).toContain('"Sam Ito"');
  });

  it("says when the next messages didn't load, and tries the same page again (CodeRabbit on #125)", async () => {
    let tries = 0;
    routed({
      [LIST]: (request) => {
        if (new URL(request.url).searchParams.get("cursor") !== "c1") return page([item()], { next_cursor: "c1" });
        tries += 1;
        return tries === 1 ? problem(500, "kernel.internal_error") : page([item({ id: OTHER, name: "Sam Ito" })]);
      },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/contact", modules: [contact], session: reader });
    await user.click(await screen.findByRole("button", { name: "Show more" }));
    expect(await screen.findByText("The next messages couldn’t be loaded.")).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Messages" });
    expect(within(list).getAllByRole("link")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Show more" }));
    await waitFor(() => {
      expect(within(list).getAllByRole("link")).toHaveLength(2);
    });
    expect(screen.queryByText("The next messages couldn’t be loaded.")).toBeNull();
  });

  it("goes back to the list when another tab is picked (CodeRabbit on #125)", async () => {
    routed({ [LIST]: page([item()]), [`GET ${ONE}`]: { status: 200, body: message() } });
    const user = userEvent.setup();
    const { router } = renderApp({ path: `/admin/contact/${ID}`, modules: [contact], session: reader });
    await screen.findByRole("heading", { level: 2, name: "Rae Okafor" });
    await user.click(screen.getByRole("tab", { name: "Spam (1)" }));
    await waitFor(() => {
      expect(`${router.state.location.pathname}${router.state.location.search}`).toBe("/admin/contact?tab=spam");
    });
    await user.click(screen.getByRole("tab", { name: "All (3)" }));
    await waitFor(() => {
      expect(`${router.state.location.pathname}${router.state.location.search}`).toBe("/admin/contact");
    });
  });

  it("says when a tab is empty", async () => {
    routed({ [LIST]: page([], { waiting: null, counts: { new: 0, replied: 0, archived: 0, spam: 0 } }) });
    renderApp({ path: "/admin/contact?tab=spam", modules: [contact], session: reader });
    expect(await screen.findByText("No spam")).toBeInTheDocument();
    expect(screen.queryByText(/waiting/)).toBeNull();
  });

  it("is under Content as Inbox, for those who may read it", async () => {
    routed({ [LIST]: page([item()]) });
    renderApp({ path: "/admin/contact", modules: [contact], session: reader });
    expect(await screen.findByRole("link", { name: "Inbox" })).toHaveAttribute("href", "/admin/contact");
  });
});

describe("the pages after the first", () => {
  it("never lets an older answer undo the pages loaded after it (CodeRabbit on #125)", () => {
    const a = item({ id: "a" });
    const b = item({ id: "b" });
    const newer = morePages(null, 20, { items: [b], next_cursor: null });
    expect(morePages(newer, 10, { items: [a], next_cursor: "x" })).toBe(newer);
    const appended = morePages({ after: 20, items: [a], next: "c2" }, 20, { items: [b], next_cursor: null });
    expect(appended).toEqual({ after: 20, items: [a, b], next: null });
    // A first page read since starts over from it.
    expect(morePages({ after: 10, items: [a], next: "c2" }, 20, { items: [b], next_cursor: "c3" })).toEqual({
      after: 20,
      items: [b],
      next: "c3",
    });
  });
});

describe("the Export's CSV", () => {
  it("quotes every cell and makes a formula plain text", () => {
    const csv = toCsv([message({ name: '=HYPERLINK("x")', message: 'Say "hi",\nthen go.', wants_news: false })]);
    const [header, row] = csv.split("\r\n");
    expect(header).toBe('"Received","Name","Email","Topic","Status","Wants the newsletter","Message"');
    expect(row).toContain(`"'=HYPERLINK(""x"")"`);
    expect(csv).toContain('"Say ""hi"",\nthen go."');
    expect(row).toContain('"New","No"');
    for (const lead of ["+1", "-1", "@x"]) {
      expect(toCsv([message({ name: lead })])).toContain(`"'${lead}"`);
    }
  });
});

// --- Settings -----------------------------------------------------------------------------

const form = (version: number, values: Record<string, unknown>): Answer => ({ status: 200, body: { version, values } });
const empty = { status: 200, body: { items: [], next_cursor: null, people: {} } };

describe("the Contact form's settings", () => {
  it("says when they couldn't be read, and offers to try again (CodeRabbit on #125)", async () => {
    routed({
      "GET /api/kernel/admin/settings/kernel.site": form(1, { description: "", kind: "Organization", logo: "", card_image: "", same_as: [], llms_summary: "", ai_crawlers: "allow" }),
      "GET /api/kernel/admin/settings/kernel.auth": form(0, { sign_up_mode: "closed" }),
      "GET /api/kernel/admin/settings/contact": problem(500, "kernel.internal_error"),
      "GET /api/kernel/admin/settings/kernel.site/history": empty,
      "GET /api/kernel/admin/settings/kernel.auth/history": empty,
      "GET /api/kernel/admin/settings/contact/history": empty,
    });
    renderApp({ path: "/admin/settings", modules: [contact], session: reader });
    expect(await screen.findByText("The contact form's settings couldn't be loaded.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Intro" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Add a topic" })).toBeNull();
  });

  it("edits the intro and the topics, and the Site tab's Save sends them", async () => {
    const sent = routed({
      "GET /api/kernel/admin/settings/kernel.site": form(1, { description: "", kind: "Organization", logo: "", card_image: "", same_as: [], llms_summary: "", ai_crawlers: "allow" }),
      "GET /api/kernel/admin/settings/kernel.auth": form(0, { sign_up_mode: "closed" }),
      "GET /api/kernel/admin/settings/contact": form(3, {
        intro: "Write to us.",
        topics: [
          { key: "question", label: "A question", first: false },
          { key: "work", label: "Working together", first: true },
        ],
      }),
      "GET /api/kernel/admin/settings/kernel.site/history": empty,
      "GET /api/kernel/admin/settings/kernel.auth/history": empty,
      "GET /api/kernel/admin/settings/contact/history": empty,
      "PUT /api/kernel/admin/settings/contact": { status: 200, body: { version: 4, changed: ["topics"], merged: [] } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings", modules: [contact], session: reader });

    expect(await screen.findByDisplayValue("Write to us.")).toBe(screen.getByRole("textbox", { name: "Intro" }));
    expect(screen.getByRole("textbox", { name: "Topic 2" })).toHaveValue("Working together");
    expect(screen.getAllByRole("switch", { name: "First" }).map((each) => each.getAttribute("aria-checked"))).toEqual(["false", "true"]);
    expect(screen.getByRole("button", { name: "Move A question up" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Add a topic" }));
    await user.type(screen.getByRole("textbox", { name: "Topic 3" }), "Press");
    await user.click(screen.getByRole("button", { name: "Move Working together up" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(sentTo(sent, "PUT", "/api/kernel/admin/settings/contact")).toHaveLength(1);
    });
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/settings/contact");
    expect(await json(put as Request)).toEqual({
      version: 3,
      changes: {
        topics: [
          { key: "work", label: "Working together", first: true },
          { key: "question", label: "A question", first: false },
          { key: "topic-3", label: "Press", first: false },
        ],
      },
    });
  });
});
