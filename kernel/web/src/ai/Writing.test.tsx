// Settings → Writing (decision 0058): the writing rules for those who change
// settings, the styles for those who keep them, and a style's own page.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderApp, testUser } from "../../testing";
import { problem, routedFetch, type Answer } from "../test-fetch";

const ADMIN = ["kernel.settings.manage", "kernel.writing.manage", "kernel.ai.write"];
const admin = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ADMIN });
const editor = testUser({ roles: ["member", "editor"], second_factor: true, permissions: ["kernel.writing.manage", "kernel.ai.write"] });
const empty = { status: 200, body: { items: [], next_cursor: null, people: {} } };

const RULES = [
  { id: "verified_only", label: "Claim only what's verified", text: "Claim nothing.", why: "Stops guessing.", warning: "" },
  { id: "no_fabrication", label: "Never invent customers, quotes, reviews or numbers", text: "Never invent.", why: "Reads as fact.", warning: "Fake reviews are banned by the FTC." },
];

const STYLE = {
  id: "00000000-0000-4000-8000-0000000000aa",
  version: 3,
  name: "Warm",
  description: "Friendly",
  voice_rules: "- Short.",
  avoid: "delve",
  samples: ["We play."],
  created_by_id: null,
  updated_by_id: null,
  created_at: "2026-11-23T12:00:00+00:00",
  updated_at: "2026-11-23T12:00:00+00:00",
};

function answers(more: Record<string, Answer | ((request: Request) => Answer)> = {}) {
  return routedFetch({
    "GET /api/kernel/notifications": { status: 200, body: { items: [], next_cursor: null, unread: 0 } },
    "GET /api/kernel/admin/attention": { status: 200, body: { items: [] } },
    "GET /api/kernel/admin/settings/kernel.writing": {
      status: 200,
      body: {
        version: 1,
        values: { mode: "defaults", rules_off: [], added_rules: "", own_text: "", about: "A label.", audience: "", can_say: "", never_say: "", voice: "" },
      },
    },
    "GET /api/kernel/admin/settings/kernel.writing/history": empty,
    "GET /api/kernel/admin/writing/rules": { status: 200, body: { mechanics: "This is the writing constitution.", rules: RULES, default_text: "- Claim nothing.\n- Never invent." } },
    "GET /api/kernel/admin/writing/styles": { status: 200, body: { items: [STYLE] } },
    "GET /api/kernel/ai": { status: 200, body: { ready: true, unreadable: false, styles: [] } },
    ...more,
  });
}

const sentTo = (sent: Request[], method: string, path: string) =>
  sent.filter((request) => request.method === method && new URL(request.url).pathname === path);

describe("Settings → Writing", () => {
  it("switches a default rule off, with its warning, and saves only that", async () => {
    const { sent } = answers({
      "PUT /api/kernel/admin/settings/kernel.writing": { status: 200, body: { version: 2, changed: ["rules_off"], merged: [] } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings/writing", session: admin });
    const rule = await screen.findByRole("switch", { name: "Never invent customers, quotes, reviews or numbers" });
    expect(rule).toBeChecked();
    expect(screen.getByRole("textbox", { name: "About the site" })).toHaveValue("A label.");
    await user.click(rule);
    // Said in the warning colour, as its risk (VM Website Dev 17's W2).
    expect(await screen.findByText("Fake reviews are banned by the FTC.")).toHaveClass("mf-ai-warning");
    expect(screen.getByText("Stops guessing.")).not.toHaveClass("mf-ai-warning");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Writing rules saved.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/settings/kernel.writing");
    expect(await put?.json()).toEqual({ version: 1, changes: { rules_off: ["no_fabrication"] } });
  });

  it("offers the site's own text in place of the rules, started from the defaults", async () => {
    answers();
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings/writing", session: admin });
    await user.selectOptions(await screen.findByRole("combobox", { name: "Rules" }), "own");
    expect(screen.queryByRole("switch", { name: "Claim only what's verified" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Start from the defaults" }));
    expect(screen.getByRole("textbox", { name: "Our own text" })).toHaveValue("- Claim nothing.\n- Never invent.");
  });

  it("shows an editor only the styles, and never asks for the rules", async () => {
    const { sent } = answers();
    renderApp({ path: "/admin/settings/writing", session: editor });
    expect(await screen.findByRole("heading", { name: "Writing styles" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Warm" })).toHaveAttribute("href", `/admin/settings/writing/styles/${STYLE.id}`);
    expect(screen.queryByRole("heading", { name: "Writing rules" })).toBeNull();
    expect(sentTo(sent, "GET", "/api/kernel/admin/settings/kernel.writing")).toHaveLength(0);
    const tabs = within(screen.getByRole("navigation", { name: "Settings" }));
    expect(tabs.getAllByRole("link").map((link) => link.textContent)).toEqual(["Writing"]);
  });
});

describe("a writing style's page", () => {
  it("makes a new style and goes to its page", async () => {
    const { sent } = answers({ "POST /api/kernel/admin/writing/styles": { status: 201, body: { ...STYLE, name: "Bright" } } });
    const user = userEvent.setup();
    const { router } = renderApp({ path: "/admin/settings/writing/styles/new", session: editor });
    await user.type(await screen.findByRole("textbox", { name: "Name" }), "Bright");
    await user.type(screen.getByRole("textbox", { name: "Sample 1" }), "We play loud.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe(`/admin/settings/writing/styles/${STYLE.id}`);
    });
    const [post] = sentTo(sent, "POST", "/api/kernel/admin/writing/styles");
    expect(await post?.json()).toEqual({ name: "Bright", description: "", voice_rules: "", avoid: "", samples: ["We play loud."] });
  });

  it("drafts the rules from the samples, then saves at the version read", async () => {
    const { sent } = answers({
      [`GET /api/kernel/admin/writing/styles/${STYLE.id}`]: { status: 200, body: STYLE },
      "POST /api/kernel/ai/style-rules": { status: 200, body: { voice_rules: "- Loud and short.", avoid: "leverage" } },
      [`PATCH /api/kernel/admin/writing/styles/${STYLE.id}`]: { status: 200, body: { ...STYLE, version: 4, voice_rules: "- Loud and short.", avoid: "leverage" } },
    });
    const user = userEvent.setup();
    renderApp({ path: `/admin/settings/writing/styles/${STYLE.id}`, session: editor });
    await user.click(await screen.findByRole("button", { name: "Draft the rules from the samples" }));
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Voice rules" })).toHaveValue("- Loud and short.");
    });
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Style saved.")).toBeInTheDocument();
    const [patch] = sentTo(sent, "PATCH", `/api/kernel/admin/writing/styles/${STYLE.id}`);
    expect(await patch?.json()).toMatchObject({ version: 3, voice_rules: "- Loud and short.", avoid: "leverage" });
  });

  it("says when someone saved the style meanwhile", async () => {
    answers({
      [`GET /api/kernel/admin/writing/styles/${STYLE.id}`]: { status: 200, body: STYLE },
      [`PATCH /api/kernel/admin/writing/styles/${STYLE.id}`]: problem(409, "kernel.writing_style_changed"),
    });
    const user = userEvent.setup();
    renderApp({ path: `/admin/settings/writing/styles/${STYLE.id}`, session: editor });
    await user.type(await screen.findByRole("textbox", { name: "Description" }), " and kind");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Someone changed this style since you opened it.");
    });
  });

  it("marks the Writing tab on a style's page, the page it belongs to (VM Website Dev 17's S1)", async () => {
    answers({ [`GET /api/kernel/admin/writing/styles/${STYLE.id}`]: { status: 200, body: STYLE } });
    renderApp({ path: `/admin/settings/writing/styles/${STYLE.id}`, session: admin });
    const tabs = within(await screen.findByRole("navigation", { name: "Settings" }));
    expect(tabs.getByRole("link", { name: "Writing" })).toHaveAttribute("aria-current", "page");
    expect(tabs.getByRole("link", { name: "AI" })).not.toHaveAttribute("aria-current");
  });

  it("deletes a style once asked again", async () => {
    const { sent } = answers({
      [`GET /api/kernel/admin/writing/styles/${STYLE.id}`]: { status: 200, body: STYLE },
      [`DELETE /api/kernel/admin/writing/styles/${STYLE.id}`]: { status: 204 },
    });
    const user = userEvent.setup();
    const { router } = renderApp({ path: `/admin/settings/writing/styles/${STYLE.id}`, session: editor });
    await user.click(await screen.findByRole("button", { name: "Delete" }));
    const asked = within(await screen.findByRole("dialog", { name: "Delete this style?" }));
    await user.click(asked.getByRole("button", { name: "Delete" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/admin/settings/writing");
    });
    expect(sentTo(sent, "DELETE", `/api/kernel/admin/writing/styles/${STYLE.id}`)).toHaveLength(1);
  });
});
