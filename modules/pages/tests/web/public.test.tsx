/**
 * pages' public surface (`web/public.ts`, decision 0057; `dev plans/contracts/pages.md`
 * §10): what a site's own page at `/:address` imports as `@/modules/pages/public`
 * to draw pages' live page in its own look. The read is the API's; every answer
 * comes from a fetch that answers by method and path.
 */
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem } from "@/kernel";
import { renderWithKernel } from "@/kernel/testing";
import { isMoved, usePage, type LivePage, type PageMoved } from "@/modules/pages/public";

type Answer = { status: number; body?: unknown };

function routed(answers: Record<string, Answer>) {
  const sent: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) => {
      const url = new URL(request.url);
      sent.push(url);
      const found = answers[`${request.method} ${url.pathname}?${url.searchParams.toString()}`];
      if (!found) return Promise.reject(new TypeError("Failed to fetch"));
      return Promise.resolve(
        new Response(found.body === undefined ? null : JSON.stringify(found.body), {
          status: found.status,
          headers: { "content-type": found.status >= 400 ? "application/problem+json" : "application/json" },
        }),
      );
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const LIVE: LivePage = {
  title: "About",
  address: "/about",
  html: "<h2>Who we are</h2><p>A crew from Boston.</p>",
  search_title: "About · Test Site",
  search_description: "Who we are A crew from Boston.",
  updated_at: "2026-11-22T12:00:00+00:00",
};

const READ = "GET /api/pages/page?address=";

function OnePage({ address }: { address: string }) {
  const found = usePage(address);
  if (found.error) return <p>{found.error instanceof ApiProblem ? `${String(found.error.status)} ${found.error.code}` : "failed"}</p>;
  if (!found.data) return null;
  return isMoved(found.data) ? <p>moved to {found.data.moved}</p> : <h1>{found.data.title}</h1>;
}

describe("pages' public surface", () => {
  it("reads a live page, an address it left as where it is now, and any other as pages.page_not_found", async () => {
    routed({
      [`${READ}%2Fabout`]: { status: 200, body: LIVE },
      [`${READ}%2Fold-about`]: { status: 200, body: { moved: "/about" } satisfies PageMoved },
      [`${READ}%2Fnowhere`]: {
        status: 404,
        body: { type: "urn:mechframe:problem:pages.page_not_found", title: "Not found", status: 404, detail: "There's no page at that address.", code: "pages.page_not_found" },
      },
    });
    renderWithKernel(
      <>
        <OnePage address="/about" />
        <OnePage address="/old-about" />
        <OnePage address="/nowhere" />
      </>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: "About" })).toBeInTheDocument();
    expect(await screen.findByText("moved to /about")).toBeInTheDocument();
    expect(await screen.findByText("404 pages.page_not_found")).toBeInTheDocument();
  });

  it("takes the address as a route's parameter gives it, without its slash", async () => {
    const sent = routed({ [`${READ}%2Fabout`]: { status: 200, body: LIVE } });
    renderWithKernel(<OnePage address="about" />);

    expect(await screen.findByRole("heading", { level: 1, name: "About" })).toBeInTheDocument();
    expect(sent.map((url) => url.searchParams.get("address"))).toEqual(["/about"]);
  });

  it("tells a move from a page", () => {
    expect(isMoved({ moved: "/about" })).toBe(true);
    expect(isMoved(LIVE)).toBe(false);
  });
});
