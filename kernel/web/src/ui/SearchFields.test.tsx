import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { SEARCH_DESCRIPTION_MAX, SEARCH_TITLE_MAX, SearchFields } from "./SearchFields";

function Fields({ errors = {} }: { errors?: { title?: string; description?: string } }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  return (
    <SearchFields
      title={title}
      description={description}
      onTitle={setTitle}
      onDescription={setDescription}
      fallbackTitle="About | Vibrant Mindz"
      fallbackDescription="We make music and art in Boston."
      hint="Left empty, these use the title and the page's opening words."
      errors={errors}
    />
  );
}

describe("SearchFields", () => {
  it("shows what an empty title and description become", () => {
    render(<Fields />);
    const title = screen.getByRole("textbox", { name: "Title in search results" });
    const description = screen.getByRole("textbox", { name: "Description" });
    expect(title).toHaveAttribute("placeholder", "About | Vibrant Mindz");
    expect(description).toHaveAttribute("placeholder", "We make music and art in Boston.");
    expect(title).toHaveAttribute("maxlength", String(SEARCH_TITLE_MAX));
    expect(description).toHaveAttribute("maxlength", String(SEARCH_DESCRIPTION_MAX));
    expect(screen.getByText("Left empty, these use the title and the page's opening words.")).toBeVisible();
  });

  it("hands up what's typed in each", async () => {
    render(<Fields />);
    await userEvent.type(screen.getByRole("textbox", { name: "Title in search results" }), "About us");
    await userEvent.type(screen.getByRole("textbox", { name: "Description" }), "Who we are");
    expect(screen.getByRole("textbox", { name: "Title in search results" })).toHaveValue("About us");
    expect(screen.getByRole("textbox", { name: "Description" })).toHaveValue("Who we are");
  });

  it("says what the server said of each", () => {
    render(<Fields errors={{ title: "Keep it to 70 characters." }} />);
    expect(screen.getByRole("textbox", { name: "Title in search results" })).toHaveAccessibleDescription(
      "Keep it to 70 characters.",
    );
  });
});
