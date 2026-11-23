// The editor's Write with AI (decision 0058): the kernel's entry in every
// editor's tools, drawn only with a key and the permission, drafting into the
// editor, rewriting the text, and filling only the fields it's given.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { renderWithKernel, testUser } from "../../testing";
import { problem, routedFetch, type Answer } from "../test-fetch";
import { MarkdownEditor, type WritingFields } from "../ui/MarkdownEditor";
import { tasksFor } from "./WritingHelp";

const writer = testUser({ roles: ["member", "editor"], permissions: ["kernel.ai.write"] });
const STYLES = [{ id: "00000000-0000-4000-8000-0000000000aa", name: "Warm", description: "Friendly" }];

type Seen = { title: string; summary: string; search: [string, string] | null };

function Editing({ start = "", withFields = true, report }: { start?: string; withFields?: boolean; report: (change: Partial<Seen>) => void }) {
  const [value, setValue] = useState(start);
  const [title, setTitle] = useState("Old title");
  const fields: WritingFields = {
    title: {
      value: title,
      set: (next) => {
        setTitle(next);
        report({ title: next });
      },
    },
    summary: {
      value: "",
      max: 300,
      set: (next) => {
        report({ summary: next });
      },
    },
    search: {
      set: (shown, under) => {
        report({ search: [shown, under] });
      },
    },
  };
  return (
    <MarkdownEditor
      label="Post body"
      value={value}
      onChange={setValue}
      preview={() => Promise.resolve("")}
      {...(withFields ? { fields } : {})}
    />
  );
}

function answers(state: Answer, more: Record<string, Answer | ((request: Request) => Answer)> = {}) {
  return routedFetch({ "GET /api/kernel/ai": state, ...more });
}

const ready: Answer = { status: 200, body: { ready: true, unreadable: false, styles: STYLES } };

function draw(options: { start?: string; withFields?: boolean } = {}) {
  const seen: Seen = { title: "", summary: "", search: null };
  renderWithKernel(
    <Editing
      {...options}
      report={(change) => {
        Object.assign(seen, change);
      }}
    />,
    { session: writer },
  );
  return seen;
}

async function opened() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Write with AI" }));
  return { user, dialog: within(await screen.findByRole("dialog", { name: "Write with AI" })) };
}

const bodyOf = async (sent: Request[], path: string): Promise<Record<string, unknown>> => {
  const found = sent.find((request) => new URL(request.url).pathname === path);
  if (!found) throw new Error(`Nothing was sent to ${path}.`);
  return (await found.clone().json()) as Record<string, unknown>;
};

describe("Write with AI", () => {
  it("isn't drawn for someone without kernel.ai.write, who never asks", async () => {
    const { sent } = answers(ready);
    renderWithKernel(<Editing report={() => undefined} />, { session: testUser({ roles: ["member"] }) });
    expect(await screen.findByRole("textbox", { name: "Post body" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Write with AI" })).toBeNull();
    expect(sent).toHaveLength(0);
  });

  it("draws nothing while the site has no key", async () => {
    const { sent } = answers({ status: 200, body: { ready: false, unreadable: false, styles: [] } });
    draw();
    await waitFor(() => {
      expect(sent).toHaveLength(1);
    });
    expect(screen.queryByRole("button", { name: "Write with AI" })).toBeNull();
  });

  it("says so when the saved key can't be read", async () => {
    answers({ status: 200, body: { ready: false, unreadable: true, styles: [] } });
    draw();
    expect(await screen.findByText(/can't read its saved key/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Write with AI" })).toBeNull();
  });

  it("drafts into the empty editor, in the style picked", async () => {
    const { sent } = answers(ready, { "POST /api/kernel/ai/draft": { status: 200, body: { markdown: "## Spring\n\nWords." } } });
    draw();
    const { user, dialog } = await opened();
    await user.selectOptions(dialog.getByRole("combobox", { name: "Style" }), "Warm");
    await user.type(dialog.getByRole("textbox", { name: "What should it be about?" }), "Our spring tour");
    await user.click(dialog.getByRole("button", { name: "Write the draft" }));
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Post body" })).toHaveValue("## Spring\n\nWords.");
    });
    expect(await bodyOf(sent, "/api/kernel/ai/draft")).toEqual({
      what: "Post body",
      style_id: STYLES[0]?.id,
      topic: "Our spring tour",
      length: "medium",
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("rewrites the whole text with nothing selected", async () => {
    const { sent } = answers(ready, { "POST /api/kernel/ai/rewrite": { status: 200, body: { markdown: "Said better." } } });
    draw({ start: "Said once." });
    const { user, dialog } = await opened();
    await user.click(dialog.getByRole("button", { name: "Rewrite" }));
    expect(dialog.getByText(/Rewrites the whole text/)).toBeInTheDocument();
    await user.click(dialog.getByRole("button", { name: "Rewrite it" }));
    await waitFor(() => {
      expect(screen.getByRole("textbox", { name: "Post body" })).toHaveValue("Said better.");
    });
    expect(await bodyOf(sent, "/api/kernel/ai/rewrite")).toEqual({ what: "Post body", style_id: null, markdown: "Said once." });
  });

  it("keeps the text and says why when a rewrite is refused", async () => {
    const lost = problem(502, "kernel.ai_rewrite_lost");
    (lost.body as { detail: string }).detail = "The rewrite left out 1 link or image, so the text wasn't changed. Try again.";
    answers(ready, { "POST /api/kernel/ai/rewrite": lost });
    draw({ start: "[Album](/music)" });
    const { user, dialog } = await opened();
    await user.click(dialog.getByRole("button", { name: "Rewrite" }));
    await user.click(dialog.getByRole("button", { name: "Rewrite it" }));
    await waitFor(() => {
      expect(dialog.getByRole("alert")).toHaveTextContent("left out 1 link or image");
    });
    expect(screen.getByRole("textbox", { name: "Post body" })).toHaveValue("[Album](/music)");
  });

  it("offers titles to pick from, and uses the one picked", async () => {
    answers(ready, { "POST /api/kernel/ai/titles": { status: 200, body: { titles: ["Spring is here", "On tour"] } } });
    const seen = draw({ start: "The text." });
    const { user, dialog } = await opened();
    await user.click(dialog.getByRole("button", { name: "Titles" }));
    await user.click(dialog.getByRole("button", { name: "Suggest titles" }));
    const list = within(await dialog.findByRole("list", { name: "Titles" }));
    expect(list.getAllByRole("listitem").map((item) => item.textContent)).toEqual(["UseSpring is here", "UseOn tour"]);
    await user.click(list.getAllByRole("button", { name: "Use" })[1] as HTMLElement);
    expect(seen.title).toBe("On tour");
  });

  it("shows search words first, and puts them in on Use these", async () => {
    const { sent } = answers(ready, {
      "POST /api/kernel/ai/search": { status: 200, body: { title: "Spring tour", description: "Dates and towns." } },
    });
    const seen = draw({ start: "The text." });
    const { user, dialog } = await opened();
    await user.click(dialog.getByRole("button", { name: "Search words" }));
    await user.click(dialog.getByRole("button", { name: "Write search words" }));
    expect(await dialog.findByText("Dates and towns.")).toBeInTheDocument();
    expect(seen.search).toBeNull();
    await user.click(dialog.getByRole("button", { name: "Use these" }));
    expect(seen.search).toEqual(["Spring tour", "Dates and towns."]);
    expect(await bodyOf(sent, "/api/kernel/ai/search")).toMatchObject({ title: "Old title", body: "The text." });
  });

  it("writes a summary to the field's own limit", async () => {
    const { sent } = answers(ready, { "POST /api/kernel/ai/summary": { status: 200, body: { summary: "A short summary." } } });
    const seen = draw({ start: "The text." });
    const { user, dialog } = await opened();
    await user.click(dialog.getByRole("button", { name: "Summary" }));
    await user.click(dialog.getByRole("button", { name: "Write a summary" }));
    await user.click(await dialog.findByRole("button", { name: "Use this summary" }));
    expect(seen.summary).toBe("A short summary.");
    expect(await bodyOf(sent, "/api/kernel/ai/summary")).toMatchObject({ max: 300 });
  });

  it("offers the field tasks only for the fields it's given", () => {
    const editor = { label: "Page body", wrap: () => undefined, insert: () => undefined, selected: () => "", text: () => "", replace: () => undefined };
    expect(tasksFor(editor).map(([, label]) => label)).toEqual(["Draft", "Rewrite"]);
  });

  it("says the AI's limit in the editor's words", async () => {
    answers(ready, { "POST /api/kernel/ai/draft": problem(429, "kernel.rate_limited") });
    draw({ withFields: false });
    const { user, dialog } = await opened();
    expect(dialog.queryByRole("button", { name: "Titles" })).toBeNull();
    await user.type(dialog.getByRole("textbox", { name: "What should it be about?" }), "x");
    await user.click(dialog.getByRole("button", { name: "Write the draft" }));
    await waitFor(() => {
      expect(dialog.getByRole("alert")).toHaveTextContent("You've asked the AI for a lot in the last hour.");
    });
  });
});
