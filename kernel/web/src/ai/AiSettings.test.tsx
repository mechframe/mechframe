// Settings → AI (decision 0058): where the key in use comes from, a key saved
// write-only at the version read, removed, and checked with Anthropic; and the
// model, from Anthropic's list (decision 0064), in each of the board's states.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderApp, testUser } from "../../testing";
import { problem, routedFetch, type Answer } from "../test-fetch";
import { modelSourceWords, sourceWords } from "./AiSettings";

const admin = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["kernel.settings.manage", "kernel.writing.manage"] });
const empty = { status: 200, body: { items: [], next_cursor: null, people: {} } };
const OPUS = { id: "claude-opus-5-5", name: "Claude Opus 5.5" };
const SONNET = { id: "claude-sonnet-5-5", name: "Claude Sonnet 5.5" };
const HAIKU = { id: "claude-haiku-5-5", name: "Claude Haiku 5.5" };
const MODELS = "GET /api/kernel/admin/ai/models";

function listed(inUse: Record<string, unknown> = {}) {
  return { status: 200, body: { models: [OPUS, SONNET, HAIKU], in_use: { ...OPUS, source: "environment", listed: true, ...inUse } } };
}

function answers(kept: boolean, state: Record<string, unknown>, more: Record<string, Answer | ((request: Request) => Answer)> = {}) {
  return routedFetch({
    "GET /api/kernel/notifications": { status: 200, body: { items: [], next_cursor: null, unread: 0 } },
    "GET /api/kernel/admin/attention": { status: 200, body: { items: [] } },
    "GET /api/kernel/admin/settings/kernel.ai": { status: 200, body: { version: kept ? 2 : 0, values: { api_key: { kept, changes: kept ? 1 : 0 } } } },
    "GET /api/kernel/admin/settings/kernel.ai/history": empty,
    "GET /api/kernel/admin/ai": { status: 200, body: { source: "none", model: "claude-opus-5-5", model_source: "environment", unreadable: false, ...state } },
    [MODELS]: listed(),
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
    expect(await screen.findByRole("combobox", { name: "Model" })).toHaveValue("claude-opus-5-5");
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

describe("Settings → AI's model (decision 0064)", () => {
  const offered = (model: HTMLElement) => within(model).getAllByRole("option").map((option) => option.textContent);

  async function model() {
    const found = await screen.findByRole("combobox", { name: "Model" });
    await waitFor(() => {
      expect(found).toBeEnabled();
    });
    return found;
  }

  it("lists Anthropic's newest of each kind, the host's model chosen (Host's key)", async () => {
    answers(false, { source: "environment" });
    await opened();
    const picker = await model();
    expect(offered(picker)).toEqual(["Claude Opus 5.5", "Claude Sonnet 5.5", "Claude Haiku 5.5"]);
    expect(picker).toHaveValue("claude-opus-5-5");
    expect(screen.getByText("Anthropic's newest model of each kind, listed when this page opens.")).toBeInTheDocument();
    expect(screen.getByText(modelSourceWords("environment"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save the model" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Use the host's model" })).toBeNull();
  });

  it("saves another model picked, at the version read (Model picked)", async () => {
    const { sent } = answers(false, { source: "environment" }, {
      "PUT /api/kernel/admin/ai/model": { status: 200, body: { version: 1, changed: ["model"], merged: [] } },
    });
    const user = userEvent.setup();
    await opened();
    await user.selectOptions(await model(), "claude-sonnet-5-5");
    await user.click(screen.getByRole("button", { name: "Save the model" }));
    expect(await screen.findByText("Saved the model.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/ai/model");
    expect(await put?.json()).toEqual({ version: 0, model: "claude-sonnet-5-5" });
  });

  it("says a saved model is used, and Use the host's model clears it (Model saved)", async () => {
    const { sent } = answers(true, { source: "settings", model: SONNET.id, model_source: "settings" }, {
      [MODELS]: listed({ ...SONNET, source: "settings" }),
      "PUT /api/kernel/admin/ai/model": { status: 200, body: { version: 3, changed: ["model"], merged: [] } },
    });
    const user = userEvent.setup();
    renderApp({ path: "/admin/settings/ai", session: admin });
    expect(await model()).toHaveValue("claude-sonnet-5-5");
    expect(screen.getByText(modelSourceWords("settings"))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use the host's model" }));
    expect(await screen.findByText("Using the host's model.")).toBeInTheDocument();
    const [put] = sentTo(sent, "PUT", "/api/kernel/admin/ai/model");
    expect(await put?.json()).toEqual({ version: 2, model: null });
  });

  it("shows the model in use alone when the list can't load, and Try again reads it again (Model list failed)", async () => {
    let asks = 0;
    answers(false, { source: "environment" }, {
      [MODELS]: () => {
        asks += 1;
        return asks === 1 ? problem(502, "kernel.ai_failed") : listed();
      },
    });
    const user = userEvent.setup();
    await opened();
    expect(await screen.findByText("Couldn't load Anthropic's model list, so the model in use is the only one shown.")).toBeInTheDocument();
    const picker = screen.getByRole("combobox", { name: "Model" });
    expect(picker).toBeDisabled();
    expect(offered(picker)).toEqual(["claude-opus-5-5"]);
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(offered(await model())).toEqual(["Claude Opus 5.5", "Claude Sonnet 5.5", "Claude Haiku 5.5"]);
    expect(screen.queryByText(/Couldn't load Anthropic's model list/)).toBeNull();
  });

  it("waits for a working key before it lists (No key)", async () => {
    answers(false, { source: "none" }, { [MODELS]: problem(503, "kernel.ai_off") });
    await opened();
    expect(await screen.findByText("Anthropic's model list loads once a key works.")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Model" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(screen.getByRole("button", { name: "Save the model" })).toBeDisabled();
  });

  it("warns when Anthropic doesn't list the model saved, and lists it first (Model not listed)", async () => {
    answers(true, { source: "settings", model: "claude-opus-4-typo", model_source: "settings" }, {
      [MODELS]: listed({ id: "claude-opus-4-typo", name: null, source: "settings", listed: false }),
    });
    renderApp({ path: "/admin/settings/ai", session: admin });
    expect(await screen.findByText("Anthropic doesn't list claude-opus-4-typo for this key, so the AI's writing help may fail.")).toBeInTheDocument();
    expect(screen.getByText("Choose another, or use the host's model.")).toBeInTheDocument();
    const picker = await model();
    expect(offered(picker)).toEqual(["claude-opus-4-typo", "Claude Opus 5.5", "Claude Sonnet 5.5", "Claude Haiku 5.5"]);
    expect(picker).toHaveValue("claude-opus-4-typo");
    expect(screen.getByText(modelSourceWords("settings"))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use the host's model" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Save the model" })).toBeDisabled();
  });
});
