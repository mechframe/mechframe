/**
 * The site's frame (K4 contract §2), around public and member pages, with
 * `nav.public`, `nav.member` and `site.footer`. The admin's is
 * `admin/AdminFrame.tsx` (K4.6); the sign-in pages' `auth/AuthFrame.tsx`.
 *
 * A site may give its own header and footer (`defineSite({ header, footer })`),
 * drawn in place of the frame's, and a page may run full bleed (`bleed: true`
 * on its route): `dev plans/contracts/site-frame.md`, decision 0048.
 *
 * The site frame holds no heading or paragraph of its own, so a page's words
 * are the only ones the parity test compares with the server's copy.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
} from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router";

import { useSession, useSignOut } from "../session/session";
import { SlotOutlet } from "../slots/slots";
import { useSite } from "../site/site";
import { ErrorBoundary } from "../ui/ErrorBoundary";
import { RouteFocus } from "../ui/RouteFocus";
import { ScrollMemory } from "../ui/ScrollMemory";
import { onStay } from "../ui/unsaved";
import { useKernelSetup } from "./context";

/** Every page: focus moved to its heading, scroll kept per page and landed on its place (`ScrollMemory`). */
export function Root() {
  return (
    <>
      <RouteFocus />
      <ScrollMemory />
      <Outlet />
    </>
  );
}

/** The skip link every frame starts with. */
export function Skip() {
  return (
    <a className="mf-skip" href="#main">
      Skip to the content
    </a>
  );
}

/**
 * The frame's account links, for a site's own header too: Sign in, or the
 * member's `nav.member` links, Your account, Admin for staff, and Sign out.
 * The site wraps them in its own `<nav aria-label="Account">`.
 */
export function SiteAccountLinks() {
  const session = useSession();
  const signOut = useSignOut();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  // Where the page is when the move home settles, not where it was at the click.
  const at = useRef(pathname);
  // A Sign out whose move home a question about unsaved changes is holding:
  // out once the move goes on and lands home; forgotten if they stay (CodeRabbit on #83).
  const held = useRef(false);
  useLayoutEffect(() => {
    at.current = pathname;
    if (held.current && pathname === "/") {
      held.current = false;
      signOut().catch((error: unknown) => {
        console.error("Signing out failed.", error);
      });
    }
  });
  useEffect(
    () =>
      onStay(() => {
        held.current = false;
      }),
    [],
  );
  if (session.status === "signed-out") return <Link to="/sign-in">Sign in</Link>;
  if (session.status !== "signed-in") return null;
  // Home first, then out: signed out on a member page, its guard sends the
  // person to sign in, which overtook a move home whose code was still coming.
  // Out only once home: a question about unsaved changes can keep them where
  // they are, and choosing to stay keeps them signed in (cubic on #82). The
  // move is drawn at once (`flushSync`), not in a transition, so `at` says
  // where the page is when navigate() settles: drawn later, it still said the
  // old page, and Sign out went home without signing out (K4.5).
  const leave = () => {
    Promise.resolve(navigate("/", { flushSync: true }))
      .then(() => {
        if (at.current === "/") return signOut();
        held.current = true; // a question holds the move: out if it goes on, not if they stay
        return undefined;
      })
      .catch((error: unknown) => {
        console.error("Signing out failed.", error);
      });
  };
  return (
    <>
      <SlotOutlet name="nav.member" label="Your pages" />
      <Link to="/account">Your account</Link>
      {session.staff ? <Link to="/admin">Admin</Link> : null}
      <button type="button" className="mf-text-link" onClick={leave}>
        Sign out
      </button>
    </>
  );
}

function FrameHeader() {
  const site = useSite();
  return (
    <header className="mf-site-header">
      {site ? (
        <Link to="/" className="mf-site-name">
          {site.name}
        </Link>
      ) : null}
      <nav aria-label="Site">
        <SlotOutlet name="nav.public" />
      </nav>
      <nav aria-label="Account">
        <SiteAccountLinks />
      </nav>
    </header>
  );
}

function FrameFooter() {
  return (
    <footer className="mf-site-footer">
      <SlotOutlet name="site.footer" />
    </footer>
  );
}

/** The site's part if it gave one, in a boundary that falls back to the frame's own. */
function Part({ given: Given, own, where }: { given: ComponentType | undefined; own: ReactNode; where: string }) {
  if (!Given) return own;
  return (
    <ErrorBoundary where={where} fallback={() => own}>
      <Given />
    </ErrorBoundary>
  );
}

/** Each open page that runs full bleed counts itself in, and out when it goes. */
const BleedCount = createContext<(change: 1 | -1) => void>(() => undefined);

/**
 * Wraps a page whose route is `bleed`: the frame's `main` drops its padding
 * while it's open. Set before paint, as soon as the route matches, so there's
 * no shift while the page's code loads.
 */
export function Bleed({ children }: { children: ReactNode }) {
  const count = useContext(BleedCount);
  useLayoutEffect(() => {
    count(1);
    return () => {
      count(-1);
    };
  }, [count]);
  return children;
}

export function SiteFrame({ children }: { children?: ReactNode }) {
  const { frame } = useKernelSetup();
  const [bleeding, setBleeding] = useState(0);
  const count = useCallback((change: 1 | -1) => {
    setBleeding((open) => open + change);
  }, []);
  return (
    <div className="mf-site mf-site-look">
      <Skip />
      <Part given={frame?.header} own={<FrameHeader />} where="The site's header" />
      <main id="main" className={bleeding > 0 ? "mf-bleed" : undefined}>
        <BleedCount.Provider value={count}>{children ?? <Outlet />}</BleedCount.Provider>
      </main>
      <Part given={frame?.footer} own={<FrameFooter />} where="The site's footer" />
    </div>
  );
}
