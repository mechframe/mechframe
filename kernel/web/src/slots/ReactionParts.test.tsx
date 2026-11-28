import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithKernel } from "../../testing";
import { defineModule } from "../modules";
import { ReactionParts } from "./ReactionParts";
import type { ReactionPartProps } from "./types";

function Given({ type, id }: ReactionPartProps) {
  return <output>{`${type} ${id}`}</output>;
}

const reactions = defineModule({
  id: "reactions",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "content.reactions": [{ id: "row", lazy: () => Promise.resolve({ default: Given }) }],
  },
});

describe("ReactionParts", () => {
  it("gives each part the thing by its type and id, signed out too", async () => {
    renderWithKernel(<ReactionParts type="blog.post" id="p1" />, { modules: [reactions], session: null });
    expect(await screen.findByRole("status")).toHaveTextContent("blog.post p1");
  });

  it("draws nothing while the module that fills it is off", () => {
    const { container } = renderWithKernel(<ReactionParts type="blog.post" id="p1" />, {
      modules: [reactions],
      on: [],
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("keeps the page when a part fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = defineModule({
      id: "broken",
      routes: { public: [], member: [], admin: [] },
      slots: {
        "content.reactions": [
          {
            id: "bad",
            lazy: () =>
              Promise.resolve({
                default: () => {
                  throw new Error("the row broke");
                },
              }),
          },
        ],
      },
    });
    renderWithKernel(
      <>
        <h1>The post</h1>
        <ReactionParts type="blog.post" id="p1" />
      </>,
      { modules: [broken, reactions] },
    );
    expect(await screen.findByRole("status")).toHaveTextContent("blog.post p1");
    expect(screen.getByRole("heading", { name: "The post" })).toBeInTheDocument();
  });

  it("refuses an entry without an id", () => {
    expect(() =>
      defineModule({
        id: "nameless",
        routes: { public: [], member: [], admin: [] },
        slots: { "content.reactions": [{ lazy: () => Promise.resolve({ default: Given }) }] } as never,
      }),
    ).toThrow("nameless's content.reactions entry must have an id.");
  });
});
