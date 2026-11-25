import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithKernel, testUser } from "../../testing";
import { defineModule } from "../modules";
import { ShareParts } from "./ShareParts";
import type { SharePartProps } from "./types";

function Given({ type, id, live, adminPath }: SharePartProps) {
  return <output>{`${type} ${id} ${live ? "live" : "not live"} ${adminPath}`}</output>;
}

const social = defineModule({
  id: "social",
  routes: { public: [], member: [], admin: [] },
  slots: {
    "content.share": [{ id: "buffer", lazy: () => Promise.resolve({ default: Given }), permission: "social.post.send" }],
  },
});

const sharer = testUser({ roles: ["member", "editor"], permissions: ["social.post.send"] });

describe("ShareParts", () => {
  it("gives each part the thing, whether it's live, and the admin page it's on", async () => {
    renderWithKernel(<ShareParts type="blog.post" id="p1" live />, {
      modules: [social],
      session: sharer,
      path: "/admin/blog/p1",
    });
    expect(await screen.findByRole("status")).toHaveTextContent("blog.post p1 live /admin/blog/p1");
  });

  it("draws nothing while the module that fills it is off", () => {
    const { container } = renderWithKernel(<ShareParts type="blog.post" id="p1" live={false} />, {
      modules: [social],
      on: [],
      session: sharer,
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("draws nothing for someone without the part's permission", () => {
    const { container } = renderWithKernel(<ShareParts type="blog.post" id="p1" live />, {
      modules: [social],
      session: testUser({ roles: ["member", "editor"], permissions: [] }),
    });
    expect(container).toBeEmptyDOMElement();
  });

  it("keeps the page when a part fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = defineModule({
      id: "broken",
      routes: { public: [], member: [], admin: [] },
      slots: {
        "content.share": [
          {
            id: "bad",
            lazy: () =>
              Promise.resolve({
                default: () => {
                  throw new Error("the card broke");
                },
              }),
          },
        ],
      },
    });
    renderWithKernel(
      <>
        <h1>The post</h1>
        <ShareParts type="blog.post" id="p1" live />
      </>,
      { modules: [broken, social], session: sharer },
    );
    expect(await screen.findByRole("status")).toHaveTextContent("blog.post p1 live");
    expect(screen.getByRole("heading", { name: "The post" })).toBeInTheDocument();
  });

  it("refuses an entry without an id", () => {
    expect(() =>
      defineModule({
        id: "nameless",
        routes: { public: [], member: [], admin: [] },
        slots: { "content.share": [{ lazy: () => Promise.resolve({ default: Given }) }] } as never,
      }),
    ).toThrow("nameless's content.share entry must have an id.");
  });
});
