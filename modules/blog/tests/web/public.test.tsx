/**
 * blog's public surface (`web/public.ts`, decision 0057): what a site's own Blog
 * and Post pages import as `@/modules/blog/public` to draw blog's posts. Each
 * read is the API's, a page at a time; every answer comes from a fetch that
 * answers by method and path.
 */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem } from "@/kernel";
import { renderWithKernel } from "@/kernel/testing";
import {
  day,
  isMoved,
  pathOf,
  useCategories,
  usePost,
  usePosts,
  type BlogCategoryCount,
  type LivePost,
  type PostCard,
  type PostMoved,
} from "@/modules/blog/public";

type Answer = { status: number; body?: unknown };

function routed(answers: Record<string, Answer | ((request: Request) => Answer)>) {
  const sent: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((request: Request) => {
      const url = new URL(request.url);
      sent.push(url);
      const found = answers[`${request.method} ${url.pathname}`];
      if (!found) return Promise.reject(new TypeError("Failed to fetch"));
      const answer = typeof found === "function" ? found(request) : found;
      return Promise.resolve(
        new Response(answer.body === undefined ? null : JSON.stringify(answer.body), {
          status: answer.status,
          headers: { "content-type": answer.status >= 400 ? "application/problem+json" : "application/json" },
        }),
      );
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

function card(overrides: Partial<PostCard> = {}): PostCard {
  return {
    title: "Ten years",
    slug: "ten-years",
    summary: "A decade of shows.",
    cover: null,
    category: { slug: "news", label: "News" },
    author: "Pat Writer",
    published_at: "2026-11-20T12:00:00+00:00",
    reading_minutes: 3,
    ...overrides,
  };
}

const LIVE: LivePost = {
  ...card(),
  id: "00000000-0000-4000-8000-0000000000b1",
  html: "<p>A room.</p>",
  updated_at: "2026-11-21T12:00:00+00:00",
  search_title: "Ten years · Test Site",
  search_description: "A decade of shows.",
  related: [],
  allow_comments: true,
};

function Posts({ category }: { category?: string }) {
  const posts = usePosts(category ? { category } : {});
  const cards = posts.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <div>
      <ul>
        {cards.map((each) => (
          <li key={each.slug}>{each.title}</li>
        ))}
      </ul>
      {posts.hasNextPage ? (
        <button type="button" onClick={() => void posts.fetchNextPage()}>
          Older posts
        </button>
      ) : null}
    </div>
  );
}

function OnePost({ slug }: { slug: string }) {
  const found = usePost(slug);
  if (found.error) return <p>{found.error instanceof ApiProblem ? `${String(found.error.status)} ${found.error.code}` : "failed"}</p>;
  if (!found.data) return null;
  return isMoved(found.data) ? <p>moved to {found.data.moved}</p> : <h1>{found.data.title}</h1>;
}

function Categories() {
  const found = useCategories();
  const items: BlogCategoryCount[] = found.data?.items ?? [];
  return (
    <ul>
      {items.map((each) => (
        <li key={each.slug}>{`${each.label}: ${String(each.posts)}`}</li>
      ))}
    </ul>
  );
}

describe("blog's public surface", () => {
  it("reads the live posts a page at a time, of one category when it's named", async () => {
    const sent = routed({
      "GET /api/blog/posts": (request) =>
        new URL(request.url).searchParams.get("cursor") === "next"
          ? { status: 200, body: { items: [card({ title: "Salt", slug: "salt" })], next_cursor: null } }
          : { status: 200, body: { items: [card()], next_cursor: "next" } },
    });
    renderWithKernel(<Posts category="news" />);

    expect(await screen.findByText("Ten years")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Older posts" }));
    expect(await screen.findByText("Salt")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Older posts" })).not.toBeInTheDocument();
    expect(sent.map((url) => url.search)).toEqual(["?category=news", "?category=news&cursor=next"]);
  });

  it("reads one live post, a slug it left as where it is now, and any other as blog.post_not_found", async () => {
    routed({
      "GET /api/blog/posts/ten-years": { status: 200, body: LIVE },
      "GET /api/blog/posts/old-words": { status: 200, body: { moved: "/blog/ten-years" } satisfies PostMoved },
      "GET /api/blog/posts/nothing": {
        status: 404,
        body: { type: "urn:mechframe:problem:blog.post_not_found", title: "Not found", status: 404, detail: "There's no post at that address.", code: "blog.post_not_found" },
      },
    });
    renderWithKernel(
      <>
        <OnePost slug="ten-years" />
        <OnePost slug="old-words" />
        <OnePost slug="nothing" />
      </>,
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Ten years" })).toBeInTheDocument();
    expect(await screen.findByText("moved to /blog/ten-years")).toBeInTheDocument();
    expect(await screen.findByText("404 blog.post_not_found")).toBeInTheDocument();
  });

  it("reads the categories with their live posts", async () => {
    routed({ "GET /api/blog/categories": { status: 200, body: { items: [{ slug: "news", label: "News", posts: 4 }] } } });
    renderWithKernel(<Categories />);

    expect(await screen.findByText("News: 4")).toBeInTheDocument();
  });

  it("tells a move from a post, and says where a post lives and the day it went up", () => {
    expect(isMoved({ moved: "/blog/ten-years" })).toBe(true);
    expect(isMoved(LIVE)).toBe(false);
    expect(pathOf("ten-years")).toBe("/blog/ten-years");
    expect(day("2026-11-20T12:00:00+00:00")).toContain("2026");
  });
});
