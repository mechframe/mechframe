// discography's public reads as hooks (`dev plans/contracts/discography.md` §2):
// the live releases a page at a time, one live release or one of its tracks (or
// where it moved), and the artist's own links. discography's own Music, Release
// and Track pages read through these, and so does a site's own page that
// replaces them (`public.ts`, decision 0057).
import { useInfiniteQuery } from "@tanstack/react-query";

import { PUBLIC_RELEASES, PUBLIC_TRACKS, api, useApiQuery, type Kind, type LiveRelease, type LiveTrack, type MusicMoved } from "./api";

/**
 * The live releases, newest first, 12 a page, of one kind when it's named: `fetchNextPage()` for older ones.
 * With `ids` (50 at most, such as a homepage deck's from featured), the live ones among them in the order given, on one page (0.1.2).
 */
export function useReleases({ kind, ids }: { kind?: Kind; ids?: readonly string[] } = {}) {
  const query = { ...(kind ? { kind } : {}), ...(ids ? { ids: [...ids] } : {}) };
  return useInfiniteQuery({
    queryKey: ["get", PUBLIC_RELEASES, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET(PUBLIC_RELEASES, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The site answered without the releases.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

/** The live release at `slug`, or where it is now (`isMoved`); any other is an ApiProblem, 404 `discography.release_not_found`. */
export function useRelease(slug: string) {
  return useApiQuery("get", "/api/discography/releases/{slug}", { params: { path: { slug } } });
}

/** A live track that plays, or where it is now; any other is 404 `discography.track_not_found`. */
export function useTrack(release: string, track: string) {
  return useApiQuery("get", "/api/discography/releases/{slug}/tracks/{track}", { params: { path: { slug: release, track } } });
}

/**
 * The live tracks that play among `ids` (50 at most), in the order given, each with its release (0.1.2): a
 * homepage's Spotlight, after featured chose them. Its queue is `data.items.map((each) => playerItem(each, each.release))`.
 */
export function useTracks(ids: readonly string[]) {
  return useApiQuery("get", PUBLIC_TRACKS, { params: { query: { ids: [...ids] } } }, { enabled: ids.length > 0 });
}

/** The artist's own links: the Music page's "Listen everywhere". */
export function useArtistLinks() {
  return useApiQuery("get", "/api/discography/links");
}

/** Whether `found` is an address a live release or track left, to go on to `found.moved`. */
export function isMoved(found: LiveRelease | LiveTrack | MusicMoved): found is MusicMoved {
  return "moved" in found;
}
