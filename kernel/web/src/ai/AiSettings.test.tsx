// Settings → AI (decision 0058): where the key in use comes from, a key saved
// write-only at the version read, removed, and checked with Anthropic.
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderApp, testUser } from "../../testing";
import { problem, routedFetch, type Answer } from "../test-fetch";
import { sourceWords } from "./AiSettings";

const admin = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["kernel.settings.manage", "kernel.writing.manage"] });
const empty = { status: 200, body: { items: [], next_cursor: null, people: {} } };

function answers(kept: boolean, state: Record<string, unknown>, more: Record<string, Answer | ((request: Request) => Answer)> = {}) {
  return routedFetch({
    "GET /api/kernel/notifications": { status: 200, body: { items: [], next_cursor: null, unread: 0 } },
    "GET /api/kernel/admin/attention": { status: 200, body: { items: [] } },
    "GET /api/kernel/admin/settings/kernel.ai": { status: 200, body: { version: kept ? 2 : 0, values: { api_key: { kept, changes: kept ? 1 : 0 } } } },
    "GET /api/kernel/admin/settings/kernel.ai/history": empty,
    "GET /api/kernel/admin/ai": { status: 200, body: { source: "none", model: "claude-opus-5-5", unreadable: false, ...state } },
    ...more,
  });
}

async function opened() {
  renderApp({ path: "/admin/settings/ai", session: admin });
  await screen.findByRole("heading", { level: 1, name: "Settings" });
  return screen.findByLabelText("Save a key");
}

const sentTo = (sent: Request[], method: string, path: string) =>
  sent.filter((request) => request.method === method && new URL(request.url).pathname === path);

describe("Settings → AI", () => {
  it("says where the key in use comes from, and shows the model the host set", async () => {
    answers(false, { source: "environment" });
    const field = await opened();
    expect(field).toHaveValue("");
    expect(field).toHaveAttribute("type", "password");
    expect(screen.getByRole("status")).toHaveTextContent(sourceWords("environment"));
    expect(screen.getByRole("textbox", { name: "Model" })).toHaveValue("claude-opus-5-5");
    expect(screen.queryByRole("button", { name: "Remove the saved key" })).toBeNull();
    expect(screen.getByRole("link", { name: "AI" })).toHaveAttribute("aria-current", "page");
  });

  it("saves a key typed, alone, at the version read", async () => {
    const { sent } = answers(false, {}, {
      "PUT /api/kernel/admin/settings/kernel.ai": { status: 200, body: { version: 1, changed: ["api_key"], merged: [] } },
    });
    const user = userEvent.setup();
    const field = await opened();
    await user.type(field, "sk-ant-typed-key-0123456789");
    await user.click(screen.getByRole("button", { name: "Save the key" }));
    expect(await screen.findByText("Key saved.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/settings/kernel.ai");
    expect(await put?.json()).toEqual({ version: 0, changes: { api_key: "sk-ant-typed-key-0123456789" } });
    expect(field).toHaveValue("");
  });

  it("says why a paste isn't a key, beside the field", async () => {
    const refused = problem(422, "kernel.invalid_request");
    (refused.body as Record<string, unknown>).errors = {
      api_key: ["An API key has no spaces or line breaks in it. Copy it again from the Anthropic console."],
    };
    answers(false, {}, { "PUT /api/kernel/admin/settings/kernel.ai": refused });
    const user = userEvent.setup();
    const field = await opened();
    await user.type(field, "not a key");
    await user.click(screen.getByRole("button", { name: "Save the key" }));
    expect(await screen.findByText("An API key has no spaces or line breaks in it. Copy it again from the Anthropic console.")).toBeInTheDocument();
  });

  it("removes a saved key, and checks the key in use", async () => {
    const { sent } = answers(true, { source: "settings" }, {
      "PUT /api/kernel/admin/settings/kernel.ai": { status: 200, body: { version: 3, changed: ["api_key"], merged: [] } },
      "POST /api/kernel/admin/ai/check": { status: 200, body: { works: true, source: "settings" } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings/ai", session: admin });
    await user.click(await screen.findByRole("button", { name: "Check the key" }));
    expect(await screen.findByText("The saved key works.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove the saved key" }));
    expect(await screen.findByText("The saved key is removed.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/settings/kernel.ai");
    expect(await put?.json()).toEqual({ version: 2, changes: { api_key: "" } });
  });

  it("says in Anthropic's place why the key was refused", async () => {
    const refused = problem(502, "kernel.ai_failed");
    (refused.body as Record<string, unknown>).detail = "Anthropic didn't accept the key. Check it was copied in full and hasn't been revoked.";
    answers(true, { source: "settings" }, { "POST /api/kernel/admin/ai/check": refused });
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings/ai", session: admin });
    await user.click(await screen.findByRole("button", { name: "Check the key" }));
    expect(await screen.findByText(/Anthropic didn't accept the key/)).toBeInTheDocument();
  });

  it("warns when the saved key can't be read, and can't check it", async () => {
    answers(true, { source: "settings", unreadable: true });
    renderApp({ path: "/admin/settings/ai", session: admin });
    expect(await screen.findByText("The saved key can't be read")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Check the key" })).toBeDisabled();
    });
  });
});
