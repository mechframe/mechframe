/**
 * campaigns' web (`dev plans/contracts/campaigns.md`): `NewsletterSignup` open,
 * sent, closed and with a field's error; the confirm and unsubscribe pages; the
 * Newsletter page's cards, attention card, tabs and empty tabs; the editor's
 * draft, test, schedule and sent states; and the Settings section. Every answer
 * comes from a fetch that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderApp, renderWithKernel, testUser } from "@/kernel/testing";
import { NewsletterSignup, useNewsletterOn } from "@/modules/campaigns/public";

import { sourceWords, whyWords } from "../../web/api";
import campaigns from "../../web/module.web";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const ID = "11111111-1111-4111-8111-111111111111";
const SUB = "22222222-2222-4222-8222-222222222222";
const ONE = `/api/campaigns/admin/emails/${ID}`;
const BASE: Answers = {
  "GET /api/kernel/notifications": { status: 200, body: { items: [], next_cursor: null, unread: 0 } },
  "GET /api/kernel/admin/attention": { status: 200, body: { items: [] } },
  "GET /api/campaigns/signup": { status: 200, body: { open: true } },
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

const sender = testUser({
  roles: ["member", "admin"],
  second_factor: true,
  permissions: ["campaigns.email.manage", "campaigns.subscriber.manage", "kernel.settings.manage"],
});

const writerOnly = testUser({ roles: ["member", "editor"], second_factor: true, permissions: ["campaigns.email.manage"] });

// --- NewsletterSignup --------------------------------------------------------------------

describe("NewsletterSignup", () => {
  it("signs an address up with its source and the bot check's proof, then says to check the inbox", async () => {
    const sent = routed({ "POST /api/campaigns/subscribe": { status: 202, body: { received: true } } });
    const user = userEvent.setup();
    renderWithKernel(<NewsletterSignup heading="New music in your inbox" source="music" />, { modules: [campaigns] });
    expect(await screen.findByRole("heading", { name: "New music in your inbox" })).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Email" }), "rae@example.com");
    await user.click(screen.getByRole("button", { name: "Sign up" }));
    const done = await screen.findByRole("status");
    expect(done).toHaveTextContent("Check your inbox");
    expect(done).toHaveTextContent("If rae@example.com isn’t on the list yet, a confirmation is on its way.");
    await waitFor(() => {
      expect(done).toHaveFocus();
    });
    const [post] = sentTo(sent, "POST", "/api/campaigns/subscribe");
    const body = await json(post as Request);
    expect(body).toMatchObject({ email: "rae@example.com", source: "music", bot: { website: "" } });
  });

  it("asks for an address before sending, and shows the server's word on one it refused", async () => {
    const sent = routed({
      "POST /api/campaigns/subscribe": problem(422, "kernel.invalid_request", {
        errors: { "body.email": ["Enter one email address, like name@example.com."] },
      }),
    });
    const user = userEvent.setup();
    renderWithKernel(<NewsletterSignup />, { modules: [campaigns] });
    await user.click(await screen.findByRole("button", { name: "Sign up" }));
    expect(await screen.findByText("Enter your email address.")).toBeInTheDocument();
    expect(sentTo(sent, "POST", "/api/campaigns/subscribe")).toHaveLength(0);
    await user.type(screen.getByRole("textbox", { name: "Email" }), "not an address");
    await user.click(screen.getByRole("button", { name: "Sign up" }));
    expect(await screen.findByText("Enter one email address, like name@example.com.")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Email" })).toHaveFocus();
    // Typing again puts the server's word away (CodeRabbit on #134).
    await user.type(screen.getByRole("textbox", { name: "Email" }), "x");
    expect(screen.queryByText("Enter one email address, like name@example.com.")).toBeNull();
  });

  it("says sign-ups are closed while Settings closes them, or while campaigns is off", async () => {
    routed({ "GET /api/campaigns/signup": { status: 200, body: { open: false } } });
    const first = renderWithKernel(<NewsletterSignup />, { modules: [campaigns] });
    expect(await screen.findByText("Sign-ups are closed just now.")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Email" })).toBeNull();
    first.unmount();
    renderWithKernel(<NewsletterSignup />, { modules: [campaigns], on: [] });
    expect(await screen.findByText("Sign-ups are closed just now.")).toBeInTheDocument();
  });

  it("tells another form whether sign-ups are open", async () => {
    routed({});
    function Box() {
      const open = useNewsletterOn();
      return <p>{open === undefined ? "Reading" : open ? "Offer the news" : "No news box"}</p>;
    }
    renderWithKernel(<Box />, { modules: [campaigns] });
    expect(await screen.findByText("Offer the news")).toBeInTheDocument();
  });
});

// --- the confirm and unsubscribe pages ------------------------------------------------------

describe("the link pages", () => {
  it("confirms by its button, never by being opened", async () => {
    const sent = routed({
      "POST /api/campaigns/confirm": { status: 200, body: { email_hint: "r…@example.com", subscribed: true } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/newsletter/confirm?token=t0k", modules: [campaigns] });
    expect(await screen.findByRole("heading", { level: 1, name: "Confirm your subscription" })).toBeInTheDocument();
    expect(sentTo(sent, "POST", "/api/campaigns/confirm")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    const done = await screen.findByRole("status");
    expect(within(done).getByRole("heading", { name: "You're subscribed" })).toBeInTheDocument();
    expect(done).toHaveTextContent("The news goes to r…@example.com from now on.");
    const [post] = sentTo(sent, "POST", "/api/campaigns/confirm");
    expect(await json(post as Request)).toEqual({ token: "t0k" });
  });

  it("unsubscribes by its button and says a link it doesn't know is one", async () => {
    let calls = 0;
    const sent = routed({
      "POST /api/campaigns/unsubscribe": () => {
        calls += 1;
        return calls === 1 ? problem(404, "campaigns.unknown_link") : { status: 200, body: { email_hint: "r…@example.com", subscribed: false } };
      },
    });
    const user = userEvent.setup();
    renderApp({ path: "/newsletter/unsubscribe?token=t0k", modules: [campaigns] });
    await user.click(await screen.findByRole("button", { name: "Unsubscribe" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This link isn't one the site knows.");
    await user.click(screen.getByRole("button", { name: "Unsubscribe" }));
    expect(await screen.findByRole("heading", { name: "You're unsubscribed" })).toBeInTheDocument();
    const [first] = sentTo(sent, "POST", "/api/campaigns/unsubscribe");
    expect(new URL((first as Request).url).searchParams.get("token")).toBe("t0k");
  });

  it("asks for the email's link when it has no token", async () => {
    routed({});
    renderApp({ path: "/newsletter/unsubscribe", modules: [campaigns] });
    expect(await screen.findByText(/This page needs the link from the email/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Unsubscribe" })).toBeNull();
  });
});

// --- the Newsletter page -------------------------------------------------------------------

const COUNTS = { subscribed: 1284, pending: 3, unsubscribed: 40, scheduled: 1, set_aside: 12, emails: 3 };

function emails(overrides: Record<string, unknown> = {}) {
  return {
    status: 200,
    body: {
      items: [
        { id: ID, subject: "The new single", kind: "release", status: "draft", sent_to: 0, when: null },
        { id: SUB, subject: "Winter shows", kind: "newsletter", status: "scheduled", sent_to: 1284, when: "2026-12-01T09:00:00+00:00" },
      ],
      next_cursor: null,
      counts: COUNTS,
      scheduled: { id: SUB, subject: "Winter shows", when: "2026-12-01T09:00:00+00:00" },
      waiting: {
        tone: "warning",
        what: "3 addresses bounced and were set aside",
        why: "They won't be emailed again.",
        label: "See them",
        to: "/admin/campaigns?tab=set-aside",
      },
      setup: { signups_open: true, has_address: true, reads_bounces: false },
      ...overrides,
    },
  };
}

describe("the Newsletter page", () => {
  it("draws the cards, the attention card and the Emails tab's rows", async () => {
    routed({ "GET /api/campaigns/admin/emails": emails() });
    renderApp({ path: "/admin/campaigns", modules: [campaigns], session: sender });
    expect(await screen.findByRole("heading", { level: 1, name: "Newsletter" })).toBeInTheDocument();
    expect(await screen.findByText("3 addresses bounced and were set aside")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See them" })).toHaveAttribute("href", "/admin/campaigns?tab=set-aside");
    const subscribed = screen.getByRole("region", { name: "Subscribed" });
    expect(subscribed).toHaveTextContent("1,284");
    expect(subscribed).toHaveTextContent("Sign-ups open");
    expect(screen.getByRole("region", { name: "Scheduled" })).toHaveTextContent("Up next");
    expect(screen.getByRole("region", { name: "Set aside" })).toHaveTextContent("12");
    const table = screen.getByRole("table");
    expect(within(table).getByText("The new single")).toBeInTheDocument();
    expect(within(table).getByText("Release announcement")).toBeInTheDocument();
    expect(within(table).getByText("1,284 people")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "Open Winter shows" })).toHaveAttribute("href", `/admin/campaigns/${SUB}`);
    expect(screen.getByRole("link", { name: "New email" })).toHaveAttribute("href", "/admin/campaigns/new");
  });

  it("warns that nothing sends without the postal address", async () => {
    routed({ "GET /api/campaigns/admin/emails": emails({ setup: { signups_open: false, has_address: false, reads_bounces: true }, waiting: null }) });
    renderApp({ path: "/admin/campaigns", modules: [campaigns], session: sender });
    expect(await screen.findByText("The newsletter has no postal address")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Subscribed" })).toHaveTextContent("Sign-ups closed");
  });

  it("lists the subscribers, removes one who asks to be forgotten, and shows the set-aside tab", async () => {
    const sent = routed({
      "GET /api/campaigns/admin/emails": emails(),
      "GET /api/campaigns/admin/subscribers": {
        status: 200,
        body: {
          items: [{ id: SUB, email: "rae@example.com", name: "Rae Okafor", source: "contact", status: "subscribed", since: "2026-11-01T10:00:00+00:00" }],
          next_cursor: null,
          counts: COUNTS,
        },
      },
      [`DELETE /api/campaigns/admin/subscribers/${SUB}`]: { status: 204 },
      "GET /api/campaigns/admin/set-aside": {
        status: 200,
        body: {
          items: [
            { email: "gone@example.com", why: "bounced", detail: "address: 5.1.1", since: "2026-11-20T10:00:00+00:00" },
            { email: "spam@example.com", why: "complained", detail: "spam report: abuse", since: "2026-11-19T10:00:00+00:00" },
          ],
          next_cursor: null,
          reads_bounces: false,
        },
      },
    });
    const user = userEvent.setup();
    const { router } = renderApp({ path: "/admin/campaigns?tab=subscribers", modules: [campaigns], session: sender });
    const row = (await screen.findByText("rae@example.com")).closest("tr") as HTMLElement;
    expect(row).toHaveTextContent("The contact form");
    expect(row).toHaveTextContent("Subscribed");
    await user.click(within(row).getByRole("button", { name: "Remove rae@example.com" }));
    await user.click(await screen.findByRole("button", { name: "Remove them" }));
    await waitFor(() => {
      expect(sentTo(sent, "DELETE", `/api/campaigns/admin/subscribers/${SUB}`)).toHaveLength(1);
    });
    await router.navigate("/admin/campaigns?tab=set-aside");
    expect(await screen.findByText("Bounced: the address doesn't exist")).toBeInTheDocument();
    expect(screen.getByText("Marked a newsletter as spam")).toBeInTheDocument();
    expect(screen.getByText(/Bounces aren’t being read/)).toBeInTheDocument();
  });

  it("shows each tab empty, and hides the people's tabs from someone who only sends", async () => {
    routed({
      "GET /api/campaigns/admin/emails": emails({ items: [], scheduled: null, waiting: null }),
    });
    renderApp({ path: "/admin/campaigns?tab=subscribers", modules: [campaigns], session: writerOnly });
    expect(await screen.findByText("No emails yet")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Subscribers" })).toBeNull();
    expect(screen.getByRole("region", { name: "Scheduled" })).toHaveTextContent("Nothing scheduled");
  });
});

// --- the editor --------------------------------------------------------------------------

function full(overrides: Record<string, unknown> = {}) {
  return {
    id: ID,
    version: 2,
    kind: "newsletter",
    subject: "Winter shows",
    preview: "Three nights",
    body: "Three nights in **December**.",
    status: "draft",
    send_at: null,
    started_at: null,
    sent_at: null,
    sent_to: 0,
    audience: 3,
    from_post: false,
    created_at: "2026-11-20T10:00:00+00:00",
    updated_at: "2026-11-20T10:00:00+00:00",
    ...overrides,
  };
}

describe("the email editor", () => {
  it("saves a new draft and opens it", async () => {
    const sent = routed({
      "POST /api/campaigns/admin/emails": { status: 201, body: full({ version: 1 }) },
      [`GET ${ONE}`]: { status: 200, body: full({ version: 1 }) },
    });
    const user = userEvent.setup();
    const { router } = renderApp({ path: "/admin/campaigns/new", modules: [campaigns], session: sender });
    await user.click(await screen.findByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("An email needs a subject.")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Subject" }), "W");
    expect(screen.queryByText("An email needs a subject.")).toBeNull();
    await user.clear(screen.getByRole("textbox", { name: "Subject" }));
    await user.type(screen.getByRole("textbox", { name: "Subject" }), "Winter shows");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/admin/campaigns/${ID}`);
    });
    const [post] = sentTo(sent, "POST", "/api/campaigns/admin/emails");
    expect(await json(post as Request)).toMatchObject({ subject: "Winter shows", kind: "newsletter" });
  });

  it("sends a test to the person asking, and schedules it", async () => {
    const sent = routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`POST ${ONE}/test`]: { status: 200, body: { to: "member@mechframe.test" } },
      [`POST ${ONE}/send`]: { status: 200, body: full({ version: 3, status: "scheduled", send_at: "2026-12-01T09:00:00+00:00" }) },
    });
    const user = userEvent.setup();
    renderApp({ path: `/admin/campaigns/${ID}`, modules: [campaigns], session: sender });
    expect(await screen.findByDisplayValue("Winter shows")).toBeInTheDocument();
    expect(screen.getByText("It goes to 3 people: everyone subscribed and not set aside.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Send a test to me" }));
    expect(await screen.findByText("A test is on its way to member@mechframe.test.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Schedule" }));
    await user.type(screen.getByLabelText("When it goes out"), "2026-12-01T09:00");
    await user.click(screen.getByRole("button", { name: "Schedule it" }));
    expect(await screen.findByRole("button", { name: "Cancel the schedule" })).toBeInTheDocument();
    const [send] = sentTo(sent, "POST", `${ONE}/send`);
    expect(typeof (await json(send as Request)).at).toBe("string");
  });

  it("says why a send was refused without the postal address", async () => {
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`POST ${ONE}/send`]: problem(409, "campaigns.no_address"),
    });
    const user = userEvent.setup();
    renderApp({ path: `/admin/campaigns/${ID}`, modules: [campaigns], session: sender });
    await user.click(await screen.findByRole("button", { name: "Send now" }));
    await user.click(await screen.findByRole("button", { name: "Send it" }));
    expect(await screen.findByText("The newsletter has no postal address")).toBeInTheDocument();
  });

  it("asks which to keep when someone else saved first", async () => {
    let saves = 0;
    let retried: Record<string, unknown> | null = null;
    routed({
      [`GET ${ONE}`]: { status: 200, body: full() },
      [`PATCH ${ONE}`]: async (request) => {
        saves += 1;
        if (saves === 1) return problem(409, "campaigns.changed", { email: full({ version: 3, subject: "Their subject" }) });
        // The retry goes at their version with the subject kept (CodeRabbit on #134); else it's refused again.
        retried = await json(request);
        return retried.version === 3 && retried.subject === "My subject"
          ? { status: 200, body: full({ version: 4, subject: "My subject" }) }
          : problem(409, "campaigns.changed", { email: full({ version: 3, subject: "Their subject" }) });
      },
    });
    const user = userEvent.setup();
    renderApp({ path: `/admin/campaigns/${ID}`, modules: [campaigns], session: sender });
    const subject = await screen.findByRole("textbox", { name: "Subject" });
    await user.clear(subject);
    await user.type(subject, "My subject");
    await user.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Their subject")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /Keep mine/ }));
    await user.click(screen.getByRole("button", { name: "Save with these choices" }));
    await waitFor(() => {
      expect(saves).toBe(2);
    });
    expect(retried).toMatchObject({ version: 3, subject: "My subject" });
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("reads a sent email back, with whom it went to", async () => {
    routed({
      [`GET ${ONE}`]: { status: 200, body: full({ status: "sent", sent_to: 3, started_at: "2026-11-21T09:00:00+00:00", sent_at: "2026-11-21T09:01:00+00:00" }) },
      [`POST ${ONE}/preview`]: { status: 200, body: { html: "<p>Three nights in <strong>December</strong>.</p>" } },
    });
    renderApp({ path: `/admin/campaigns/${ID}`, modules: [campaigns], session: sender });
    expect(await screen.findByText(/Sent to 3 people, /)).toBeInTheDocument();
    expect(await screen.findByText("December")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Subject" })).toBeNull();
  });
});

// --- Settings and the words ----------------------------------------------------------------

describe("the Newsletter settings", () => {
  it("shows the switch, the address, the note and the pace", async () => {
    const form = (version: number, values: Record<string, unknown>): Answer => ({ status: 200, body: { version, values } });
    const empty = { status: 200, body: { items: [], next_cursor: null, people: {} } };
    routed({
      "GET /api/kernel/admin/settings/kernel.site": form(1, { description: "", kind: "Organization", logo: "", card_image: "", same_as: [], llms_summary: "", ai_crawlers: "allow" }),
      "GET /api/kernel/admin/settings/kernel.auth": form(0, { sign_up_mode: "closed" }),
      "GET /api/kernel/admin/settings/campaigns": form(2, {
        signups_open: true,
        postal_address: "P.O. Box 12\nBoston, MA",
        footer_note: "You're getting this because you asked.",
        send_per_hour: 6000,
      }),
      "GET /api/kernel/admin/settings/kernel.site/history": empty,
      "GET /api/kernel/admin/settings/kernel.auth/history": empty,
      "GET /api/kernel/admin/settings/campaigns/history": empty,
    });
    renderApp({ path: "/admin/settings", modules: [campaigns], session: sender });
    expect(await screen.findByRole("textbox", { name: "Postal address" })).toHaveValue("P.O. Box 12\nBoston, MA");
    expect(screen.getByRole("switch", { name: "Sign-ups open" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("spinbutton", { name: "Emails an hour" })).toHaveValue(6000);
  });
});

describe("the words", () => {
  it("names a source and a reason as the board does", () => {
    expect(sourceWords("form")).toBe("A sign-up form");
    expect(sourceWords("contact")).toBe("The contact form");
    expect(sourceWords("music-page")).toBe("Music page");
    expect(whyWords("bounced", "address: 5.1.2")).toBe("Bounced: the domain doesn't exist");
    expect(whyWords("bounced", "Set aside by hand")).toBe("Bounced");
    expect(whyWords("unsubscribed", "")).toBe("Unsubscribed");
  });
});

describe("sending an email never saved", () => {
  it("saves it, sends it, then opens it in its sent state (CodeRabbit on #134)", async () => {
    const sent = routed({
      "POST /api/campaigns/admin/emails": { status: 201, body: full({ version: 1 }) },
      // Answered late: an editor that moved to the new address on its first save is
      // drawn by then, holding the draft.
      [`POST ${ONE}/send`]: async () => {
        await new Promise((resolve) => setTimeout(resolve, 300));
        return { status: 200, body: full({ version: 2, status: "sending", sent_to: 0, started_at: "2026-11-23T09:00:00+00:00" }) };
      },
      [`POST ${ONE}/preview`]: { status: 200, body: { html: "<p>Three nights.</p>" } },
    });
    const user = userEvent.setup();
    const { router } = renderApp({ path: "/admin/campaigns/new", modules: [campaigns], session: sender });
    await user.type(await screen.findByRole("textbox", { name: "Subject" }), "Winter shows");
    await user.click(screen.getByRole("button", { name: "Send now" }));
    await user.click(await screen.findByRole("button", { name: "Send it" }));
    expect(await screen.findByText("Sending: 0 people so far.")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(`/admin/campaigns/${ID}`);
    expect(screen.queryByRole("button", { name: "Send now" })).toBeNull();
    expect(sentTo(sent, "POST", `${ONE}/send`)).toHaveLength(1);
  });
});
