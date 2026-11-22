// The kit's text parts from the slots (decision 0060): the kernel's entries
// and the modules on fill editor.tools and prose.embed.
import { screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { renderWithKernel, testUser } from "../../testing";
import { defineModule, type ModuleDefinition } from "../modules";
import { Button } from "../ui/Button";
import { MarkdownEditor, type MarkdownTools } from "../ui/MarkdownEditor";
import { Prose } from "../ui/Prose";
import { TextPartsFromSlots, type EditorToolEntry } from "./textParts";

function named(name: string) {
  return function Named({ editor }: { editor: MarkdownTools }) {
    return (
      <Button
        size="small"
        onClick={() => {
          editor.insert(name);
        }}
      >
        {name}
      </Button>
    );
  };
}

function Player({ href, words }: { href: string; words: string }) {
  return <figure data-testid="player" data-href={href} aria-label={words} />;
}

const embeds: ModuleDefinition = defineModule({
  id: "embeds",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "editor.tools": [{ id: "embed", lazy: () => Promise.resolve({ default: named("Embed") }) }],
    "prose.embed": [
      {
        claims: (href) => href.startsWith("https://tube.example/"),
        lazy: () => Promise.resolve({ default: Player }),
      },
    ],
  },
});

const notes: ModuleDefinition = defineModule({
  id: "notes",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "editor.tools": [
      { id: "note", lazy: () => Promise.resolve({ default: named("Note") }), permission: "notes.note.write" },
    ],
  },
});

function Editor() {
  const [value, setValue] = useState("");
  return (
    <MarkdownEditor label="Page body" value={value} onChange={setValue} preview={(text) => Promise.resolve(text)} />
  );
}

async function buttons(): Promise<string[]> {
  const group = screen.getByRole("group", { name: "Formatting" });
  await within(group).findByRole("button", { name: "Embed" });
  return within(group)
    .getAllByRole("button")
    .map((button) => button.textContent);
}

describe("editor.tools", () => {
  it("gives every editor the buttons of the modules on, the kernel's first", async () => {
    const ai: EditorToolEntry[] = [{ id: "ai", lazy: () => Promise.resolve({ default: named("Write for me") }) }];
    renderWithKernel(
      <TextPartsFromSlots kernelTools={ai}>
        <Editor />
      </TextPartsFromSlots>,
      { modules: [embeds] },
    );
    expect((await buttons()).slice(-2)).toEqual(["Write for me", "Embed"]);
  });

  it("leaves out a module that's off, and a button the person may not use", async () => {
    renderWithKernel(<Editor />, { modules: [embeds, notes], session: testUser({ permissions: [] }) });
    expect(await buttons()).not.toContain("Note");
  });

  it("shows a button to those who hold its permission", async () => {
    renderWithKernel(<Editor />, {
      modules: [embeds, notes],
      session: testUser({ permissions: ["notes.note.write"] }),
    });
    expect(await screen.findByRole("button", { name: "Note" })).toBeInTheDocument();
  });

  it("draws no module's buttons while that module is off", () => {
    renderWithKernel(<Editor />, { modules: [embeds], on: [] });
    expect(screen.queryByRole("button", { name: "Embed" })).toBeNull();
  });
});

describe("prose.embed", () => {
  it("gives Prose the players of the modules on", async () => {
    renderWithKernel(<Prose html='<p><a href="https://tube.example/1">A video</a></p>' />, { modules: [embeds] });
    expect(await screen.findByTestId("player")).toHaveAttribute("data-href", "https://tube.example/1");
  });

  it("leaves the link while the module is off", () => {
    renderWithKernel(<Prose html='<p><a href="https://tube.example/1">A video</a></p>' />, { modules: [embeds], on: [] });
    expect(screen.getByRole("link", { name: "A video" })).toBeInTheDocument();
  });
});

describe("defineModule's checks", () => {
  it("wants an id and a part for each editor.tools entry", () => {
    expect(() =>
      defineModule({ id: "bad", routes: { public: [], member: [], admin: [] }, slots: { "editor.tools": [{ lazy: () => Promise.resolve({ default: named("x") }) }] } as never }),
    ).toThrow(/editor.tools entry must have an id/);
  });

  it("wants claims for each prose.embed entry", () => {
    expect(() =>
      defineModule({ id: "bad", routes: { public: [], member: [], admin: [] }, slots: { "prose.embed": [{ lazy: () => Promise.resolve({ default: Player }) }] } as never }),
    ).toThrow(/prose.embed entry must say which links it claims/);
  });
});
