// portfolio's public reads as hooks (`dev plans/contracts/portfolio.md` §2): the
// live pieces a page at a time, one live piece, and the disciplines with
// something live. The Art page reads through these, and so does a site's own
// page or a module that lists portfolio in `requires` (`public.ts`, decision 0057).
import { useInfiniteQuery } from "@tanstack/react-query";

import { PUBLIC_DISCIPLINES, PUBLIC_LIST, api, useApiQuery } from "./api";

/** The live pieces, newest first, a page at a time, of one discipline when it's named. */
export function usePieces({ discipline = "" }: { discipline?: string } = {}) {
  const query = discipline ? { discipline } : {};
  return useInfiniteQuery({
    queryKey: ["get", PUBLIC_LIST, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET(PUBLIC_LIST, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The site answered without the pieces.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

/** The live piece at `slug`; any other slug is an ApiProblem, 404 `portfolio.piece_not_found`. */
export function usePiece(slug: string) {
  return useApiQuery("get", "/api/portfolio/pieces/{slug}", { params: { path: { slug } } }, { enabled: slug !== "" });
}

/** The disciplines with something live, in the order staff set. */
export function useDisciplines() {
  return useApiQuery("get", PUBLIC_DISCIPLINES);
}
