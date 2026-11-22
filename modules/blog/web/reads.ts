// blog's public reads as hooks (`dev plans/contracts/blog.md` §2): the live
// posts a page at a time, one live post or where it moved, and the categories
// with their live posts. blog's own Blog and Post pages read through these, and
// so does a site's own page that replaces them (`public.ts`, decision 0057).
import { useInfiniteQuery } from "@tanstack/react-query";

import { PUBLIC_LIST, api, useApiQuery, type LivePost, type PostMoved } from "./api";

/** The live posts, newest first, 12 a page, of one category when it's named: `fetchNextPage()` for older ones. */
export function usePosts({ category = "" }: { category?: string } = {}) {
  const query = category ? { category } : {};
  return useInfiniteQuery({
    queryKey: ["get", PUBLIC_LIST, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET(PUBLIC_LIST, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The site answered without the posts.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

/** The live post at `slug`, or where it is now (`isMoved`); any other slug is an ApiProblem, 404 `blog.post_not_found`. */
export function usePost(slug: string) {
  return useApiQuery("get", "/api/blog/posts/{slug}", { params: { path: { slug } } });
}

/** Every category, in the order staff set, with its live posts. */
export function useCategories() {
  return useApiQuery("get", "/api/blog/categories");
}

/** Whether `found` is a slug a live post left, to go on to `found.moved`. */
export function isMoved(found: LivePost | PostMoved): found is PostMoved {
  return "moved" in found;
}
