/**
 * Consent categories (hook 6, decision 0052; `kernel.consent` on the server).
 *
 * A script or iframe from another host waits until the visitor grants its
 * category: `analytics`, `marketing` or `media`. `necessary` never waits.
 *
 *     <ConsentGate category="media" fallback={(grant) => <Facade onPlay={grant} />}>
 *       <iframe src="https://www.youtube-nocookie.com/embed/…" title="…" />
 *     </ConsentGate>
 *
 * An embed's facade click is the consent to `media` (the owner, 2026-11-20);
 * analytics waits for a banner, which is the `consent` module's to draw.
 * CONSENT_MODE `off` (`GET /api/kernel/site`'s `consent.mode`) opens every
 * gate, and until the site is read every gate but `necessary` holds.
 *
 * The choice is kept in the browser only, in the first-party cookie
 * `__Host-mf_consent` (the granted categories joined by dots), set here by
 * script for 180 days; the server never stores it and the CSP never changes
 * with it. Every gate of a category opens at once, and a choice made in
 * another tab is read when this one has the focus again.
 */
import { useCallback, useSyncExternalStore, type ReactNode } from "react";

import { useSite } from "../site/site";

export type ConsentCategory = "necessary" | "analytics" | "marketing" | "media";

/** The categories in the order the cookie keeps them. */
const CATEGORIES: readonly ConsentCategory[] = ["necessary", "analytics", "marketing", "media"];

export const CONSENT_COOKIE = "__Host-mf_consent";

/** How long a choice is kept: 180 days, in seconds. */
const KEEP_SECONDS = 180 * 24 * 60 * 60;

const listeners = new Set<() => void>();

/** The cookie's value as written, "" for none: the store's snapshot, compared by value. */
function stored(): string {
  for (const pair of document.cookie.split(";")) {
    const at = pair.indexOf("=");
    if (at > 0 && pair.slice(0, at).trim() === CONSENT_COOKIE) return pair.slice(at + 1).trim();
  }
  return "";
}

/** The names a value holds; `keep` writes back only the categories that need consent. */
function granted(value: string): Set<string> {
  return new Set(value.split("."));
}

function keep(categories: Set<string>): void {
  const value = CATEGORIES.filter((category) => category !== "necessary" && categories.has(category)).join(".");
  const life = String(value ? KEEP_SECONDS : 0);
  // A __Host- cookie: Secure, Path=/ and no Domain, so only this site's own pages read it.
  document.cookie = `${CONSENT_COOKIE}=${value}; Path=/; Max-Age=${life}; SameSite=Lax; Secure`;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("focus", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("focus", listener);
  };
}

export type Consent = {
  /** Whether what `category` holds may load now. */
  granted: boolean;
  /** Grants `category` (what a facade's click or a banner's Allow calls). */
  grant: () => void;
  /** Takes the grant back: the category's gates hold again. */
  withdraw: () => void;
};

/** Whether `category` is granted, and the means to grant it or take it back. */
export function useConsent(category: ConsentCategory): Consent {
  const mode = useSite()?.consent.mode;
  const value = useSyncExternalStore(subscribe, stored, () => "");
  const grant = useCallback(() => {
    if (category === "necessary") return;
    const now = granted(stored());
    now.add(category);
    keep(now);
  }, [category]);
  const withdraw = useCallback(() => {
    const now = granted(stored());
    now.delete(category);
    keep(now);
  }, [category]);
  const open = category === "necessary" || mode === "off" || (mode === "ask" && granted(value).has(category));
  return { granted: open, grant, withdraw };
}

export type ConsentGateProps = {
  category: ConsentCategory;
  /** What shows while it holds: a facade, a note with an Allow button, or nothing. */
  fallback?: ReactNode | ((grant: () => void) => ReactNode);
  /** The script or iframe it holds. */
  children: ReactNode;
};

/** Holds `children` until `category` is granted, showing `fallback` meanwhile. */
export function ConsentGate({ category, fallback = null, children }: ConsentGateProps) {
  const { granted: open, grant } = useConsent(category);
  if (open) return <>{children}</>;
  return <>{typeof fallback === "function" ? fallback(grant) : fallback}</>;
}
