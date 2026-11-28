/**
 * `ReactionParts` (decision 0068): where a module's public page draws the
 * reactions under one of its things, the parts of `content.reactions`, each
 * given the thing's content type and id as item references name it (hook 11).
 * `reactions` fills it with its row; blog's post page draws it. Neither
 * imports the other, so a site without `reactions` draws nothing here, and a
 * part that fails leaves the page.
 */
import { Suspense, useCallback, useState } from "react";

import { lazyPart } from "../app/lazy";
import { ErrorBoundary } from "../ui/ErrorBoundary";
import { useSlot } from "./slots";

export type ReactionProps = {
  /** The content type, `<module>.<entity>`: `blog.post`. */
  type: string;
  id: string;
};

export function ReactionParts({ type, id }: ReactionProps) {
  const entries = useSlot("content.reactions");
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
          // Keyed by the thing too, so a part is made afresh for another thing, never
          // carrying one post's state to the next (cubic on #170).
          <ErrorBoundary key={`${entry.key}:${type}:${id}`} where={`${entry.module}'s part of content.reactions`} onRetry={again}>
            <Suspense fallback={null}>
              <Part type={type} id={id} />
            </Suspense>
          </ErrorBoundary>
        );
      })}
    </>
  );
}
