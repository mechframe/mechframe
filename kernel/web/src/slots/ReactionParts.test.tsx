import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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
    const { container } = renderWithKernel(
      <>
        <h1>The post</h1>
        <ReactionParts type="blog.post" id="p1" />
      </>,
      { modules: [broken, reactions] },
    );
    // The working part by its words, and the failed one's fallback by its own: both
    // are a status (CodeRabbit and cubic on #170).
    expect(await screen.findByText("blog.post p1")).toBeInTheDocument();
    await waitFor(() => {
      expect(container.querySelector(".mf-part-failed")).not.toBeNull();
    });
    expect(screen.getByRole("heading", { name: "The post" })).toBeInTheDocument();
  });

  it("makes a part afresh for another thing (cubic on #170)", async () => {
    function Counter({ id }: ReactionPartProps) {
      const [n, setN] = useState(0);
      return (
        <button type="button" onClick={() => {
            setN(n + 1);
          }}>
          {`${id} pressed ${String(n)}`}
        </button>
      );
    }
    const counting = defineModule({
      id: "reactions",
      routes: { public: [], member: [], admin: [] },
      slots: { "content.reactions": [{ id: "row", lazy: () => Promise.resolve({ default: Counter }) }] },
    });
    function Page() {
      const [id, setId] = useState("p1");
      return (
        <>
          <button type="button" onClick={() => {
              setId("p2");
            }}>
            Next post
          </button>
          <ReactionParts type="blog.post" id={id} />
        </>
      );
    }
    renderWithKernel(<Page />, { modules: [counting] });
    await userEvent.click(await screen.findByRole("button", { name: "p1 pressed 0" }));
    expect(screen.getByRole("button", { name: "p1 pressed 1" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next post" }));
    expect(await screen.findByRole("button", { name: "p2 pressed 0" })).toBeInTheDocument();
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
