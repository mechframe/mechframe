/**
 * social's web (`dev plans/contracts/social.md` §7): the Share card with no
 * token, with Buffer's channels not listed yet, before the thing is live, and
 * ready, picking channels, a text over a channel's limit, a share refused as
 * shared before and sent again, Refresh and Take it back; the Settings
 * section's token states, save, remove and Check. Every answer comes from a
 * fetch that answers by method and path.
 */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithKernel, testUser } from "@/kernel/testing";

import { lengthFor, type Channel, type Share, type ShareView, type TokenState } from "../../web/api";
import social from "../../web/module.web";
import SharePanel from "../../web/SharePanel";
import SocialSettings from "../../web/SocialSettings";

type Answer = { status: number; body?: unknown };
type Answers = Record<string, Answer | ((request: Request) => Answer | Promise<Answer>)>;

const ID = "11111111-1111-4111-8111-111111111111";
const LINK = "https://site.test/blog/jazz";

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

const sentTo = (sent: Request[], method: string, path: string) =>
  sent.filter((request) => request.method === method && new URL(request.url).pathname === path);

const channel = (over: Partial<Channel>): Channel => ({
  id: "ch-x",
  name: "@testsite",
  service: "twitter",
  network: "X",
  descriptor: "Profile",
  usable: true,
  problem: "",
  queue_paused: false,
  limit: 280,
  ...over,
});

const CHANNELS = [
  channel({}),
  channel({ id: "ch-linkedin", name: "Test Site", service: "linkedin", network: "LinkedIn", limit: 3000 }),
  channel({ id: "ch-instagram", name: "testsite", service: "instagram", network: "Instagram", usable: false, problem: "Instagram takes no link posts from here.", limit: null }),
];

const share = (over: Partial<Share>): Share => ({
  id: "33333333-3333-4333-8333-333333333333",
  channel_id: "ch-x",
  channel_name: "@testsite (Profile)",
  service: "twitter",
  network: "X",
  text: "Jazz at noon",
  link: LINK,
  mode: "queue",
  due_at: "2026-11-25T15:00:00+00:00",
  state: "queued",
  error: "",
  external_link: null,
  sent_at: null,
  sent_by_name: "Ada",
  created_at: "2026-11-24T12:00:00+00:00",
  ...over,
});

const view = (over: Partial<ShareView> = {}): ShareView => ({
  ready: true,
  source: "saved",
  unreadable: false,
  live: true,
  card: { url: LINK, title: "Jazz at noon", description: "Where to hear it.", image: null },
  text: "Jazz at noon\n\nWhere to hear it.",
  channels: CHANNELS,
  listed_at: "2026-11-24T11:00:00+00:00",
  history: [],
  ...over,
});

const sharer = testUser({ roles: ["member", "editor"], second_factor: true, permissions: ["social.post.send"] });
const admin = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["social.post.send", "kernel.settings.manage"] });
const SHARES = "/api/social/admin/shares";

function card(live = true) {
  return renderWithKernel(<SharePanel type="blog.post" id={ID} live={live} adminPath={`/admin/blog/${ID}`} />, { session: sharer });
}

describe("the Share card", () => {
  it("sends people to Settings with no token", async () => {
    routed({ [`GET ${SHARES}`]: { status: 200, body: view({ ready: false, source: "none", channels: [], listed_at: null }) } });
    card();
    expect(await screen.findByText(/An admin can save its token in Settings/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Settings" })).toHaveAttribute("href", "/admin/settings");
  });

  it("says a saved token can't be read", async () => {
    routed({ [`GET ${SHARES}`]: { status: 200, body: view({ ready: false, unreadable: true, channels: [] }) } });
    card();
    expect(await screen.findByText("The saved Buffer token can't be read")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
  });

  it("checks the channels when Buffer hasn't listed them", async () => {
    let listed = false;
    const sent = routed({
      [`GET ${SHARES}`]: () => ({ status: 200, body: listed ? view() : view({ ready: false, channels: [], listed_at: null }) }),
      "POST /api/social/admin/channels": () => {
        listed = true;
        return { status: 200, body: { channels: CHANNELS, listed_at: "2026-11-24T11:00:00+00:00" } };
      },
    });
    const user = userEvent.setup();
    card();
    await user.click(await screen.findByRole("button", { name: "Check the channels" }));
    expect(await screen.findByRole("button", { name: /@testsite \(X\)/ })).toBeInTheDocument();
    expect(sentTo(sent, "POST", "/api/social/admin/channels")).toHaveLength(1);
  });

  it("waits until the thing is published", async () => {
    routed({ [`GET ${SHARES}`]: { status: 200, body: view({ live: false, card: null, text: "" }) } });
    card(false);
    expect(await screen.findByText("Share it once it's published.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
  });

  it("reads the view again once the post is published on the page", async () => {
    let published = false;
    routed({ [`GET ${SHARES}`]: () => ({ status: 200, body: published ? view() : view({ live: false, card: null, text: "" }) }) });
    function Editor() {
      const [live, setLive] = useState(false);
      return (
        <>
          <button
            type="button"
            onClick={() => {
              published = true;
              setLive(true);
            }}
          >
            Publish
          </button>
          <SharePanel type="blog.post" id={ID} live={live} adminPath={`/admin/blog/${ID}`} />
        </>
      );
    }
    const user = userEvent.setup();
    renderWithKernel(<Editor />, { session: sharer });
    expect(await screen.findByText("Share it once it's published.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Publish" }));
    expect(await screen.findByRole("button", { name: "Share" })).toBeInTheDocument();
    expect(screen.queryByText("Share it once it's published.")).toBeNull();
  });

  it("shares to the channels picked, with the text and when, from the page it's on", async () => {
    const sent = routed({
      [`GET ${SHARES}`]: { status: 200, body: view() },
      [`POST ${SHARES}`]: { status: 200, body: { results: [share({}), share({ id: "44444444-4444-4444-8444-444444444444", channel_id: "ch-linkedin" })], history: [] } },
    });
    const user = userEvent.setup();
    card();
    const share_ = await screen.findByRole("button", { name: "Share" });
    expect(share_).toBeDisabled();
    expect(screen.getByText("Instagram takes no link posts from here.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /@testsite \(X\)/ }));
    await user.click(screen.getByRole("button", { name: /Test Site \(LinkedIn\)/ }));
    expect(screen.getByText(/of 280 characters for X, the link included/)).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "When" }), "draft");
    await user.click(share_);
    expect(await screen.findByText("Shared to 2 channels.")).toBeInTheDocument();
    const [request] = sentTo(sent, "POST", SHARES);
    expect(await request?.json()).toEqual({
      type: "blog.post",
      id: ID,
      admin_path: `/admin/blog/${ID}`,
      channel_ids: ["ch-x", "ch-linkedin"],
      text: "Jazz at noon\n\nWhere to hear it.",
      when: "draft",
      due_at: null,
      again: false,
    });
  });

  it("refuses a text too long for a channel picked", async () => {
    routed({ [`GET ${SHARES}`]: { status: 200, body: view() } });
    const user = userEvent.setup();
    card();
    await user.click(await screen.findByRole("button", { name: /@testsite \(X\)/ }));
    const text = screen.getByRole("textbox", { name: "Text" });
    await user.clear(text);
    await user.click(text);
    await user.paste("x".repeat(260));
    expect(screen.getByText("Too long for X. Shorten the text.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Share" })).toBeDisabled();
  });

  it("asks before sharing to a channel again", async () => {
    let tries = 0;
    const sent = routed({
      [`GET ${SHARES}`]: { status: 200, body: view() },
      [`POST ${SHARES}`]: () => {
        tries += 1;
        if (tries === 1) return problem(409, "social.shared_before", "This already went to @testsite on 24 November (sent).");
        return { status: 200, body: { results: [share({})], history: [] } };
      },
    });
    const user = userEvent.setup();
    card();
    await user.click(await screen.findByRole("button", { name: /@testsite \(X\)/ }));
    await user.click(screen.getByRole("button", { name: "Share" }));
    expect(await screen.findByText("It's been shared there before")).toBeInTheDocument();
    expect(screen.getByText(/This already went to @testsite/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Share again" }));
    await waitFor(() => {
      expect(sentTo(sent, "POST", SHARES)).toHaveLength(2);
    });
    expect(await sentTo(sent, "POST", SHARES)[1]?.json()).toMatchObject({ again: true });
  });

  it("drops Share again once the channels picked change (CodeRabbit on #152)", async () => {
    routed({
      [`GET ${SHARES}`]: { status: 200, body: view() },
      [`POST ${SHARES}`]: problem(409, "social.shared_before", "This already went to @testsite on 24 November (sent)."),
    });
    const user = userEvent.setup();
    card();
    await user.click(await screen.findByRole("button", { name: /@testsite \(X\)/ }));
    await user.click(screen.getByRole("button", { name: "Share" }));
    expect(await screen.findByRole("button", { name: "Share again" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Test Site \(LinkedIn\)/ }));
    expect(screen.queryByRole("button", { name: "Share again" })).toBeNull();
  });

  it("says a refusal in the server's words", async () => {
    routed({
      [`GET ${SHARES}`]: { status: 200, body: view() },
      [`POST ${SHARES}`]: problem(409, "social.address_not_answering", "Its address answered 404, so a post would link to nothing."),
    });
    const user = userEvent.setup();
    card();
    await user.click(await screen.findByRole("button", { name: /@testsite \(X\)/ }));
    await user.click(screen.getByRole("button", { name: "Share" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Its address answered 404");
  });

  it("lists what went before, refreshes it and takes back what's waiting", async () => {
    const waiting = share({});
    const sent = share({ id: "55555555-5555-4555-8555-555555555555", state: "sent", external_link: "https://network.test/post-1", channel_name: "Test Site (Page)", network: "LinkedIn" });
    const lost = share({ id: "66666666-6666-4666-8666-666666666666", state: "unknown", error: "Buffer didn't answer, so this may or may not have gone." });
    const requests = routed({
      [`GET ${SHARES}`]: { status: 200, body: view({ history: [waiting, sent, lost] }) },
      [`POST ${SHARES}/refresh`]: { status: 200, body: { history: [waiting, sent, lost] } },
      [`DELETE ${SHARES}/${waiting.id}`]: { status: 200, body: { history: [{ ...waiting, state: "removed" }, sent, lost] } },
    });
    const user = userEvent.setup();
    card();
    const list = await screen.findByRole("list", { name: "Shared so far" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(within(items[0] as HTMLElement).getByText("Queued in Buffer")).toBeInTheDocument();
    expect(within(items[1] as HTMLElement).getByRole("link", { name: "See it on LinkedIn" })).toHaveAttribute("href", "https://network.test/post-1");
    expect(within(items[2] as HTMLElement).getByText("Not confirmed")).toBeInTheDocument();
    expect(within(items[2] as HTMLElement).getByText(/may or may not have gone/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => {
      expect(sentTo(requests, "POST", `${SHARES}/refresh`)).toHaveLength(1);
    });
    await user.click(within(items[0] as HTMLElement).getByRole("button", { name: "Take it back" }));
    expect(await screen.findByText("Taken back from @testsite (Profile).")).toBeInTheDocument();
  });
});

describe("the Social settings", () => {
  const form = (kept: boolean): Answer => ({ status: 200, body: { version: 3, values: { buffer_token: { kept, changes: kept ? 1 : 0 } } } });
  const state = (over: Partial<TokenState> = {}): Answer => ({ status: 200, body: { source: "saved", unreadable: false, channels: CHANNELS, listed_at: "2026-11-24T11:00:00+00:00", ...over } });

  it("says where the token comes from and lists its channels", async () => {
    routed({ "GET /api/kernel/admin/settings/social": form(false), "GET /api/social/admin/state": state({ source: "host" }) });
    renderWithKernel(<SocialSettings />, { session: admin });
    expect(await screen.findByRole("status")).toHaveTextContent("Sharing uses the host's token, BUFFER_ACCESS_TOKEN.");
    expect(screen.getByText("Instagram takes no link posts from here.")).toBeInTheDocument();
    expect(screen.getAllByText("Can be shared to")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Remove the saved token" })).toBeNull();
  });

  it("saves a token alone, at the version read", async () => {
    const sent = routed({
      "GET /api/kernel/admin/settings/social": form(false),
      "GET /api/social/admin/state": state({ source: "none", channels: [], listed_at: null }),
      "PUT /api/kernel/admin/settings/social": { status: 200, body: { version: 4, changed: ["buffer_token"], merged: [] } },
    });
    const user = userEvent.setup();
    renderWithKernel(<SocialSettings />, { session: admin });
    expect(await screen.findByRole("button", { name: "Check the token" })).toBeDisabled();
    await user.type(screen.getByLabelText("Save a Buffer token"), "buffer-token-for-the-web-tests-0001");
    await user.click(screen.getByRole("button", { name: "Save the token" }));
    expect(await screen.findByText("Token saved. Check it to list its channels.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/settings/social");
    expect(await put?.json()).toEqual({ version: 3, changes: { buffer_token: "buffer-token-for-the-web-tests-0001" } });
  });

  it("keeps a token typed while another one saves (CodeRabbit on #152)", async () => {
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    routed({
      "GET /api/kernel/admin/settings/social": form(false),
      "GET /api/social/admin/state": state({ source: "none", channels: [], listed_at: null }),
      "PUT /api/kernel/admin/settings/social": async () => {
        await held;
        return { status: 200, body: { version: 4, changed: ["buffer_token"], merged: [] } };
      },
    });
    const user = userEvent.setup();
    renderWithKernel(<SocialSettings />, { session: admin });
    const field = await screen.findByLabelText("Save a Buffer token");
    await user.type(field, "buffer-token-for-the-web-tests-0001");
    await user.click(screen.getByRole("button", { name: "Save the token" }));
    await user.type(field, "-more");
    release();
    expect(await screen.findByText("Token saved. Check it to list its channels.")).toBeInTheDocument();
    expect(screen.getByLabelText("Save a Buffer token")).toHaveValue("buffer-token-for-the-web-tests-0001-more");
  });

  it("shows a refused paste's reason under the field", async () => {
    routed({
      "GET /api/kernel/admin/settings/social": form(false),
      "GET /api/social/admin/state": state({ source: "none", channels: [] }),
      "PUT /api/kernel/admin/settings/social": {
        status: 422,
        body: { type: "urn:mechframe:problem:kernel.invalid_request", title: "Refused", status: 422, detail: "Refused.", code: "kernel.invalid_request", errors: { buffer_token: ["That's too short to be a Buffer token."] } },
      },
    });
    const user = userEvent.setup();
    renderWithKernel(<SocialSettings />, { session: admin });
    await user.type(await screen.findByLabelText("Save a Buffer token"), "tiny");
    await user.click(screen.getByRole("button", { name: "Save the token" }));
    expect(await screen.findByText("That's too short to be a Buffer token.")).toBeInTheDocument();
  });

  it("removes the saved token and checks the one in use", async () => {
    const sent = routed({
      "GET /api/kernel/admin/settings/social": form(true),
      "GET /api/social/admin/state": state(),
      "PUT /api/kernel/admin/settings/social": { status: 200, body: { version: 4, changed: ["buffer_token"], merged: [] } },
      "POST /api/social/admin/channels": { status: 200, body: { channels: CHANNELS, listed_at: "2026-11-24T12:00:00+00:00" } },
    });
    const user = userEvent.setup();
    renderWithKernel(<SocialSettings />, { session: admin });
    await user.click(await screen.findByRole("button", { name: "Check the token" }));
    expect(await screen.findByText("The token works: Buffer lists 3 channels.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove the saved token" }));
    expect(await screen.findByText("The saved token is removed.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/settings/social");
    expect(await put?.json()).toEqual({ version: 3, changes: { buffer_token: "" } });
  });

  it("says a saved token can't be read", async () => {
    routed({ "GET /api/kernel/admin/settings/social": form(true), "GET /api/social/admin/state": state({ unreadable: true, channels: [] }) });
    renderWithKernel(<SocialSettings />, { session: admin });
    expect(await screen.findByText("The saved Buffer token can't be read")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check the token" })).toBeDisabled();
  });
});

describe("lengthFor", () => {
  it("counts in code points, as the server does (CodeRabbit on #152)", () => {
    const sax = String.fromCodePoint(0x1f3b7);
    expect(lengthFor(channel({}), sax.repeat(10), "https://s.test/a")).toBe(10 + 2 + 16);
    expect(lengthFor(channel({ service: "linkedin" }), sax.repeat(2), "https://s.test/a")).toBe(2);
  });
});

describe("social's binding", () => {
  it("fills the Share slot for those who share, and Settings for those who manage it", () => {
    expect(social.slots?.["content.share"]?.[0]).toMatchObject({ id: "buffer", permission: "social.post.send" });
    expect(social.slots?.["admin.settings.section"]?.[0]).toMatchObject({ id: "social", title: "Social", permission: "kernel.settings.manage" });
  });
});
