/**
 * The built-in reactions' icons, by key, as VM Website's Post board draws them
 * (24 by 24, stroked at 1.9 in the text's colour). The keys are `BUILT_IN`'s in
 * `backend/reactions/schemas.py`, in its order: a test holds the two equal.
 */
import type { ReactNode } from "react";

const PATHS: Record<string, ReactNode> = {
  fire: (
    <path d="M12 21c-3.9 0-6.5-2.6-6.5-6.1 0-3.4 2.6-5.5 3.8-8.4.5 1.7 1.6 2.9 2.6 3.4.2-2.5 1.5-4.7 3.6-6.4-.1 2.4.9 4 2 5.6 1.2 1.7 1 3.1 1 5.8 0 3.5-2.6 6.1-6.5 6.1z" />
  ),
  love: <path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />,
  mind_blown: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6" />,
};

/** A reaction's icon, hidden from screen readers: its button says the label. */
export function ReactionIcon({ name }: { name: string }) {
  return (
    <svg
      className="mf-reaction-icon"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
