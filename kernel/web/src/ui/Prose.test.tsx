import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { Prose } from "./Prose";

function Where() {
  return <output data-testid="where">{useLocation().pathname}</output>;
}

function draw(html: string) {
  return render(
    <MemoryRouter initialEntries={["/about"]}>
      <Routes>
        <Route path="*" element={<Prose html={html} />} />
      </Routes>
      <Where />
    </MemoryRouter>,
  );
}

describe("Prose", () => {
  it("draws the server's HTML in the prose class", () => {
    const { container } = draw("<h2>Who we are</h2><p>A <strong>crew</strong>.</p>");
    expect(screen.getByRole("heading", { level: 2, name: "Who we are" })).toBeVisible();
    expect(container.querySelector(".mf-prose")).toContainHTML("<strong>crew</strong>");
  });

  it("moves inside the app for a link to a page here", async () => {
    draw('<p><a href="/credits">Credits</a></p>');
    await userEvent.click(screen.getByRole("link", { name: "Credits" }));
    expect(screen.getByTestId("where")).toHaveTextContent("/credits");
  });

  /** Whether Prose took the click: read on the document, after its handler, then stopped so jsdom doesn't try to go. */
  function took(anchor: HTMLElement, init: MouseEventInit = {}): boolean {
    const seen: boolean[] = [];
    const record = (event: Event) => {
      seen.push(event.defaultPrevented);
      event.preventDefault();
    };
    document.addEventListener("click", record);
    try {
      fireEvent.click(anchor, { button: 0, ...init });
    } finally {
      document.removeEventListener("click", record);
    }
    const [prevented] = seen;
    if (prevented === undefined) throw new Error("The click never reached the document.");
    return prevented;
  }

  it("takes a plain click on a link to a page here", () => {
    draw('<p><a href="/credits">Credits</a></p>');
    expect(took(screen.getByRole("link", { name: "Credits" }))).toBe(true);
    expect(screen.getByTestId("where")).toHaveTextContent("/credits");
  });

  it.each([
    ['<a href="https://example.com/x">Away</a>', "Away"],
    ['<a href="//evil.example/x">Away</a>', "Away"],
    ['<a href="mailto:a@example.com">Mail</a>', "Mail"],
    ['<a href="#part">Part</a>', "Part"],
    ['<a href="/report.pdf" download>Report</a>', "Report"],
  ])("leaves a link elsewhere to the browser: %s", (html, name) => {
    draw(`<p>${html}</p>`);
    expect(took(screen.getByRole("link", { name }))).toBe(false);
    expect(screen.getByTestId("where")).toHaveTextContent("/about");
  });

  it.each([{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }])(
    "leaves a click with %o to the browser",
    (init) => {
      draw('<p><a href="/credits">Credits</a></p>');
      expect(took(screen.getByRole("link", { name: "Credits" }), init)).toBe(false);
      expect(screen.getByTestId("where")).toHaveTextContent("/about");
    },
  );
});
