// Rows edited in place: credits, streaming links and roles. Each row keeps its
// own key as the rows before it go, so React never hands a removed row's
// elements, its focused Remove button among them, to the row after it; and a
// removal puts the focus in the row that took its place, on its first field,
// or on Add once no row is left (CodeRabbit on #145, 0.1.3). The keys live
// here, beside the rows: they never reach a form's data, its dirty check or a
// save.
import { useEffect, useRef, useState, type RefObject } from "react";

type Held = { keys: readonly number[]; next: number };

function numbered(count: number, from: number): Held {
  return { keys: Array.from({ length: count }, (_, at) => from + at), next: from + count };
}

/** A key for each of `count` rows, kept by each row as rows are added and removed here. */
export function useRowKeys(count: number): { keys: readonly number[]; added: () => void; removed: (index: number) => void } {
  const [held, setHeld] = useState<Held>(() => numbered(count, 0));
  let shown = held;
  if (held.keys.length !== count) {
    // The rows changed from outside, a new read or theirs taken: keys anew.
    shown = numbered(count, held.next);
    setHeld(shown);
  }
  return {
    keys: shown.keys,
    added: () => {
      setHeld((now) => ({ keys: [...now.keys, now.next], next: now.next + 1 }));
    },
    removed: (index) => {
      setHeld((now) => ({ keys: now.keys.filter((_, at) => at !== index), next: now.next }));
    },
  };
}

/**
 * Where the focus goes once a row is removed. `rowsRef` is on the element that
 * holds the rows and Add: each row's first field is marked `data-row-first`,
 * and Add `data-row-add`. Call `removedAt` with the row's index as it goes.
 */
export function useFocusAfterRemoval<Holder extends HTMLElement>(): { rowsRef: RefObject<Holder | null>; removedAt: (index: number) => void } {
  const rowsRef = useRef<Holder | null>(null);
  const pendingRef = useRef<number | null>(null);
  useEffect(() => {
    const at = pendingRef.current;
    if (at === null) return;
    pendingRef.current = null;
    const holder = rowsRef.current;
    if (!holder) return;
    const firsts = holder.querySelectorAll<HTMLElement>("[data-row-first]");
    const target = firsts.length ? firsts[Math.min(at, firsts.length - 1)] : holder.querySelector<HTMLElement>("[data-row-add]");
    target?.focus();
  });
  return {
    rowsRef,
    removedAt: (index) => {
      pendingRef.current = index;
    },
  };
}
