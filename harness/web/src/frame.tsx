// The site frame as a site that brings its own header and footer draws it
// (harness/web/frame.html, at /frame.html; dev plans/contracts/site-frame.md):
// a sticky header and a footer of the site's, a page at /frame.html that runs
// full bleed, and an ordinary page it links to, reached without a reload.
// Playwright checks it (kernel/tests/e2e/frame.spec.ts). Sample words only.
import "../../../themes/machined-light/tokens.css";
import "../../../themes/vibrant-mindz/tokens.css";
import "./frame.css";

import { Link } from "react-router";

import { SiteAccountLinks, SlotOutlet, defineSite, mountApp, useSite } from "@/kernel";

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
      <Link to="/frame-plain">An ordinary page</Link>
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

const site = defineSite({
  routes: {
    public: [
      { path: "/frame.html", lazy: () => Promise.resolve({ default: EdgeToEdge }), bleed: true },
      { path: "/frame-plain", lazy: () => Promise.resolve({ default: Ordinary }) },
    ],
    member: [],
  },
  header: Header,
  footer: Footer,
});

void mountApp({ modules: [], site });
