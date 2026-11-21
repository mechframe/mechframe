/**
 * The site frame with the site's own header and footer, and pages that run
 * full bleed (`dev plans/contracts/site-frame.md`; decision 0048, amended).
 * The frame's own header and footer, and its sign-out, are in routes.test.tsx.
 */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { memo } from "react";
import { describe, expect, it, vi } from "vitest";

import { renderApp, testUser } from "../../testing";
import { SiteAccountLinks, SlotOutlet, defineModule, defineSite, useSite, type SiteDefinition } from "../../index";
import { routedFetch } from "../test-fetch";

function pageSaying(words: string) {
  return () => Promise.resolve({ default: () => <h1>{words}</h1> });
}

function Header() {
  const site = useSite();
  return (
    <header className="test-header">
      <a href="/">{site?.name ?? ""}, by its own header</a>
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
    <footer className="test-footer">
      <span>The site's own footer</span>
      <SlotOutlet name="site.footer" />
    </footer>
  );
}

const pages: SiteDefinition["routes"] = {
  public: [
    { path: "/about", lazy: pageSaying("About us"), bleed: true },
    { path: "/contact", lazy: pageSaying("Write to us") },
  ],
  member: [],
};

const site = defineSite({ routes: pages, header: Header, footer: Footer });

const blog = defineModule({
  id: "blog",
  routes: {
    public: [{ path: "/blog", lazy: pageSaying("The blog"), bleed: true }],
    member: [{ path: "/blog/drafts", lazy: pageSaying("Your drafts") }],
    admin: [{ path: "/admin/blog", lazy: pageSaying("Posts"), permission: "blog.post.write" }],
  },
  slots: {
    "nav.public": [{ label: "Blog", to: "/blog" }],
    "nav.member": [{ label: "Drafts", to: "/blog/drafts" }],
  },
});

const staff = testUser({ roles: ["member", "admin"], second_factor: true, permissions: ["auth.user.manage"] });

function main(): HTMLElement {
  return screen.getByRole("main");
}

/** The account links in the site's own header, never the frame's. */
function accountLinks(): string[] {
  const account = screen.getByRole("navigation", { name: "Account" });
  expect(account.closest(".test-header")).not.toBeNull();
  return [...account.querySelectorAll("a, button")].map((each) => each.textContent);
}

describe("the site's own header and footer", () => {
  it.each([
    ["its own page", "/about", null, "About us"],
    ["a module's page", "/blog", null, "The blog"],
    ["the kernel's home", "/", null, "Test Site"],
    ["the account page", "/account", testUser(), "Sign-in and security"],
    ["the 404 page", "/nowhere", null, "Page not found"],
    ["a member's 404 under /admin", "/admin", testUser(), "Page not found"],
  ] as const)("take the frame's place on %s", async (_, path, session, heading) => {
    renderApp({ path, sitePages: site, modules: [blog], session });
    expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Test Site, by its own header" })).toBeInTheDocument();
    expect(screen.getByText("The site's own footer")).toBeInTheDocument();
    // The frame's own are gone: one banner, one contentinfo, and no "Site" navigation.
    expect(screen.getAllByRole("banner")).toHaveLength(1);
    expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
    expect(screen.queryByRole("navigation", { name: "Site" })).toBeNull();
  });

  it("come after the frame's skip link, around its main", async () => {
    renderApp({ path: "/contact", sitePages: site });
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    const frame = main().parentElement;
    expect([...(frame?.children ?? [])].map((each) => each.tagName.toLowerCase() + (each.className ? `.${each.className}` : ""))).toEqual([
      "a.mf-skip",
      "header.test-header",
      "main",
      "footer.test-footer",
    ]);
  });

  it("show the modules' slot entries where the site puts them", async () => {
    renderApp({ path: "/about", sitePages: site, modules: [blog] });
    await screen.findByRole("heading", { level: 1, name: "About us" });
    expect(screen.getByRole("navigation", { name: "Main" })).toHaveTextContent("Blog");
  });

  it("are left out of the sign-in frame", async () => {
    renderApp({ path: "/sign-in", sitePages: site });
    expect(await screen.findByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
    expect(screen.queryByText("The site's own footer")).toBeNull();
    expect(screen.queryByRole("link", { name: "Test Site, by its own header" })).toBeNull();
  });

  it("are left out of the admin frame", async () => {
    routedFetch({});
    renderApp({ path: "/admin", sitePages: site, session: staff });
    expect(await screen.findByRole("navigation", { name: "Admin" })).toBeInTheDocument();
    expect(screen.queryByText("The site's own footer")).toBeNull();
    expect(screen.queryByRole("link", { name: "Test Site, by its own header" })).toBeNull();
  });

  it("fall back to the frame's own when one fails to draw, and the page stays", async () => {
    const failed = vi.spyOn(console, "error").mockImplementation(() => undefined);
    function Broken(): never {
      throw new Error("The header broke.");
    }
    renderApp({ path: "/contact", sitePages: defineSite({ routes: pages, header: Broken, footer: Broken }) });
    expect(await screen.findByRole("heading", { level: 1, name: "Write to us" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Site" })).toBeInTheDocument();
    expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
    const said = failed.mock.calls.map(([first]) => String(first));
    expect(said).toContain("The site's header failed to show.");
    expect(said).toContain("The site's footer failed to show.");
  });

  it("take a component React wraps, such as memo's", async () => {
    renderApp({ path: "/contact", sitePages: defineSite({ routes: pages, header: memo(Header) }) });
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    expect(screen.getByRole("link", { name: "Test Site, by its own header" })).toBeInTheDocument();
    // No footer given: the frame's own.
    expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
    expect(screen.queryByText("The site's own footer")).toBeNull();
  });
});

describe("SiteAccountLinks", () => {
  it("is Sign in for a person signed out", async () => {
    renderApp({ path: "/contact", sitePages: site });
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    expect(accountLinks()).toEqual(["Sign in"]);
  });

  it("is the member's links, the account, the admin for staff, and Sign out", async () => {
    const { unmount } = renderApp({ path: "/contact", sitePages: site, modules: [blog], session: testUser() });
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    expect(accountLinks()).toEqual([
      "Drafts",
      "Your account",
      "Sign out",
    ]);
    unmount();
    renderApp({ path: "/contact", sitePages: site, modules: [blog], session: staff });
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    expect(accountLinks()).toEqual([
      "Drafts",
      "Your account",
      "Admin",
      "Sign out",
    ]);
  });

  it("signs out and goes home", async () => {
    const sent = vi.fn<(request: Request) => Promise<Response>>(() => Promise.resolve(new Response(null, { status: 204 })));
    vi.stubGlobal("fetch", sent);
    const { router } = renderApp({ path: "/contact", sitePages: site, session: testUser() });
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    expect(accountLinks()).toContain("Sign out");
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/");
    });
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
    expect(sent.mock.calls.map(([request]) => new URL(request.url).pathname)).toContain("/api/auth/sign-out");
  });
});

describe("a page that runs full bleed", () => {
  it("drops the main's padding while it's open, and gives it back on the next page", async () => {
    const { router } = renderApp({ path: "/about", sitePages: site, modules: [blog], strict: true });
    await screen.findByRole("heading", { level: 1, name: "About us" });
    expect(main()).toHaveClass("mf-bleed");
    await router.navigate("/contact");
    await screen.findByRole("heading", { level: 1, name: "Write to us" });
    expect(main()).not.toHaveClass("mf-bleed");
    await router.navigate("/blog");
    await screen.findByRole("heading", { level: 1, name: "The blog" });
    expect(main()).toHaveClass("mf-bleed");
    await router.navigate("/about");
    await screen.findByRole("heading", { level: 1, name: "About us" });
    expect(main()).toHaveClass("mf-bleed");
  });

  it("is a module's, and keeps the padding on the 404 page while the module is off", async () => {
    const { unmount } = renderApp({ path: "/blog", modules: [blog] });
    await screen.findByRole("heading", { level: 1, name: "The blog" });
    expect(main()).toHaveClass("mf-bleed");
    unmount();
    renderApp({ path: "/blog", modules: [blog], on: [] });
    await screen.findByRole("heading", { level: 1, name: "Page not found" });
    expect(main()).not.toHaveClass("mf-bleed");
  });

  it("keeps the padding on the 404 page when the module's switch reads off after the routes are built", async () => {
    // Not known at the start, so every module's routes stand and the page waits on its switch (ModuleGate).
    routedFetch({ "GET /api/kernel/modules": { status: 200, body: { on: [] } } });
    renderApp({ path: "/blog", modules: [blog], on: "loading" });
    await screen.findByRole("heading", { level: 1, name: "Page not found" });
    expect(main()).not.toHaveClass("mf-bleed");
  });

  it("holds at / for the page that owns it, the site's or a module's", async () => {
    const home = defineSite({ routes: { public: [{ path: "/", lazy: pageSaying("Home"), bleed: true }], member: [] } });
    const { unmount } = renderApp({ sitePages: home });
    await screen.findByRole("heading", { level: 1, name: "Home" });
    expect(main()).toHaveClass("mf-bleed");
    unmount();
    const landing = defineModule({
      id: "landing",
      routes: { public: [{ path: "/", lazy: pageSaying("The landing page"), bleed: true }], member: [], admin: [] },
    });
    const second = renderApp({ modules: [landing] });
    await screen.findByRole("heading", { level: 1, name: "The landing page" });
    expect(main()).toHaveClass("mf-bleed");
    second.unmount();
    renderApp({ modules: [landing], on: [] });
    await screen.findByRole("heading", { level: 1, name: "Test Site" });
    expect(main()).not.toHaveClass("mf-bleed");
  });

  it("is a member page's too", async () => {
    const drafts = defineSite({
      routes: { public: [], member: [{ path: "/drafts", lazy: pageSaying("Drafts"), bleed: true }] },
    });
    renderApp({ path: "/drafts", sitePages: drafts, session: testUser() });
    await screen.findByRole("heading", { level: 1, name: "Drafts" });
    expect(main()).toHaveClass("mf-bleed");
  });
});
