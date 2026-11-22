// The library's list, a page of 40 at a time, newest first: every page asked
// for so far in one list, with "Show more" while there are older ones (Codex
// on #116). Its key starts as the list's own, so a change that invalidates the
// list (["get", LIBRARY]) reloads it.
import { useInfiniteQuery } from "@tanstack/react-query";

import { LIBRARY, api, type Image, type ImagePage } from "../api";

export type LibraryQuery = { q?: string; missing_alt?: boolean };

export function useLibrary(query: LibraryQuery) {
  const found = useInfiniteQuery({
    queryKey: ["get", LIBRARY, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }): Promise<ImagePage> => {
      const { data } = await api.GET(LIBRARY, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The library answered without its page.");
      return data;
    },
    getNextPageParam: (last: ImagePage) => last.next_cursor ?? undefined,
  });
  const items: Image[] = found.data?.pages.flatMap((page) => page.items) ?? [];
  return { found, items, missing: found.data?.pages[0]?.missing_alt ?? 0, loaded: found.data !== undefined };
}
