// The site frame as a site that brings its own header and footer draws it
// (harness/web/frame.html, at /frame.html; dev plans/contracts/site-frame.md):
// a sticky header and a footer of the site's, a page at /frame.html that runs
// full bleed, an ordinary page it links to, reached without a reload, and a
// long page that docks a bar after the footer (contracts/after-footer.md).
// Playwright checks it (kernel/tests/e2e/frame.spec.ts). Sample words only.
import "../../../themes/machined-light/tokens.css";
import "../../../themes/vibrant-mindz/tokens.css";
import "./frame.css";

import { Link } from "react-router";

import { AfterFooter, SiteAccountLinks, SlotOutlet, defineSite, mountApp, useSite } from "@/kernel";

function Header() {
  const site = useSite();
  return (
    <header className="frame-header">
      <Link to="/frame.html" className="frame-name">
        {site?.name ?? "The site"}
      </Link>
      <nav aria-label="Main">
        <SlotOutlet name="nav.public" />
      </nav>
      <nav aria-label="Account">
        <SiteAccountLinks />
      </nav>
    </header>
  );
}

function Footer() {
  return (
    <footer className="frame-footer">
      <span>The site's own footer</span>
      <SlotOutlet name="site.footer" />
    </footer>
  );
}

function EdgeToEdge() {
  return (
    <section className="frame-hero">
      <h1>Edge to edge</h1>
      <p>This page runs full bleed: the frame's main has no padding.</p>
      <Link to="/frame-plain">An ordinary page</Link> <Link to="/frame-docked">A page with a docked bar</Link>
    </section>
  );
}

function Ordinary() {
  return (
    <>
      <h1>An ordinary page</h1>
      <p>The frame's main keeps its padding here.</p>
    </>
  );
}

function Docked() {
  return (
    <>
      <section className="frame-long">
        <h1>A docked bar</h1>
        <p>The bar rides the window's foot down this long page and settles below the footer at its end.</p>
        <Link to="/frame.html">Back to the edge-to-edge page</Link>
      </section>
      <AfterFooter>
        <section className="frame-dock" aria-label="Player">
          <span>Now playing: a sample track</span>
        </section>
      </AfterFooter>
    </>
  );
}

const site = defineSite({
  routes: {
    public: [
      { path: "/frame.html", lazy: () => Promise.resolve({ default: EdgeToEdge }), bleed: true },
      { path: "/frame-plain", lazy: () => Promise.resolve({ default: Ordinary }) },
      { path: "/frame-docked", lazy: () => Promise.resolve({ default: Docked }) },
    ],
    member: [],
  },
  header: Header,
  footer: Footer,
});

void mountApp({ modules: [], site });
