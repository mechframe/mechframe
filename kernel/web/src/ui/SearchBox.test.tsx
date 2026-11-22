import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { SearchBox } from "./SearchBox";

function Box() {
  const [q, setQ] = useState("");
  return (
    <>
      <SearchBox
        label="Search files"
        value={q}
        onChange={(event) => {
          setQ(event.target.value);
        }}
      />
      <output data-testid="q">{q}</output>
    </>
  );
}

describe("SearchBox", () => {
  it("is a search field named by its label, which it says inside, with the magnifier hidden", () => {
    const { container } = render(<Box />);
    const box = screen.getByRole("searchbox", { name: "Search files" });
    expect(box).toHaveAttribute("placeholder", "Search files");
    expect(container.querySelector(".mf-search > svg")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector(".mf-search")).toContainElement(box);
  });

  it("hands up what's typed", async () => {
    render(<Box />);
    await userEvent.type(screen.getByRole("searchbox", { name: "Search files" }), "cover");
    expect(screen.getByTestId("q")).toHaveTextContent("cover");
  });
});
