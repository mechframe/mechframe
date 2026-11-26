import { screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";

import { renderWithKernel } from "../../testing";
import { QuietLink } from "./QuietLink";

describe("QuietLink", () => {
  it("is a link to a page, in the kit's quiet look, keeping a class of its own", () => {
    renderWithKernel(
      <QuietLink to="/admin/music/1" className="extra">
        Open the release
      </QuietLink>,
    );
    const link = screen.getByRole("link", { name: "Open the release" });
    expect(link).toHaveAttribute("href", "/admin/music/1");
    expect(link).toHaveClass("mf-quiet-link", "extra");
    expect(link).not.toHaveClass("mf-button");
  });

  it("takes a ref as a prop (React 19)", () => {
    const ref = createRef<HTMLAnchorElement>();
    renderWithKernel(
      <QuietLink to="/admin" ref={ref}>
        Back
      </QuietLink>,
    );
    expect(ref.current).toBe(screen.getByRole("link", { name: "Back" }));
  });
});
