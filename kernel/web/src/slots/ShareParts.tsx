/**
 * `ShareParts` (decision 0067): where a module's admin page offers to share
 * what it's about, the parts of `content.share` the person may see, each
 * given the thing's content type and id, whether it's public now, and the admin
 * page it's drawn on. `social` fills it with its Share card; blog's post editor
 * draws it. Neither imports the other, so a site without `social` draws
 * nothing here, and a part that fails leaves the page.
 */
import { Suspense, useCallback, useState } from "react";
import { useLocation } from "react-router";

import { lazyPart } from "../app/lazy";
import { ErrorBoundary } from "../ui/ErrorBoundary";
import { useSlot } from "./slots";

export type ShareProps = {
  /** The content type, `<module>.<entity>`: `blog.post`. */
  type: string;
  id: string;
  /** Whether the thing is public now: a part may only offer to share it then. */
  live: boolean;
};

export function ShareParts({ type, id, live }: ShareProps) {
  const entries = useSlot("content.share");
  const { pathname } = useLocation();
  // Bumped by Try again, so the parts are made again, as SlotOutlet's are.
  const [, setTries] = useState(0);
  const again = useCallback(() => {
    setTries((tries) => tries + 1);
  }, []);
  if (entries.length === 0) return null;
  return (
    <>
      {entries.map((entry) => {
        const Part = lazyPart(entry.lazy);
        return (
          <ErrorBoundary key={entry.key} where={`${entry.module}'s part of content.share`} onRetry={again}>
            <Suspense fallback={null}>
              <Part type={type} id={id} live={live} adminPath={pathname} />
            </Suspense>
          </ErrorBoundary>
        );
      })}
    </>
  );
}
