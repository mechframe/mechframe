import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { MarkdownEditor, type MarkdownEditorProps } from "./MarkdownEditor";

function Editor({ start = "", ...props }: Partial<MarkdownEditorProps> & { start?: string }) {
  const [value, setValue] = useState(start);
  return (
    <MemoryRouter>
      <MarkdownEditor
        label="Page body"
        value={value}
        onChange={setValue}
        preview={props.preview ?? ((text) => Promise.resolve(`<p>${text}</p>`))}
        {...props}
      />
      <output data-testid="value">{value}</output>
    </MemoryRouter>
  );
}

function body(): HTMLTextAreaElement {
  return screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Page body" });
}

function select(start: number, end: number) {
  act(() => {
    body().setSelectionRange(start, end);
  });
}

describe("MarkdownEditor", () => {
  it("is a named text under Write and Preview tabs, with the board's buttons", () => {
    render(<Editor />);
    expect(screen.getByRole("tablist", { name: "Editor" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Write" })).toHaveAttribute("aria-selected", "true");
    const formatting = screen.getByRole("group", { name: "Formatting" });
    for (const name of ["Bold", "Italic", "Heading", "Quote", "Link"]) {
      expect(formatting).toContainElement(screen.getByRole("button", { name }));
    }
    expect(body()).toBeVisible();
  });

  it("types into the text and hands each change up", async () => {
    render(<Editor />);
    await userEvent.type(body(), "Hello");
    expect(screen.getByTestId("value")).toHaveTextContent("Hello");
  });

  it("wraps the selection in bold and keeps it selected", async () => {
    render(<Editor start="Some loud words" />);
    select(5, 9);
    await userEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(body().value).toBe("Some **loud** words");
    expect(body().value.slice(body().selectionStart, body().selectionEnd)).toBe("loud");
    expect(body()).toHaveFocus();
  });

  it("makes the line a heading, a quote and a link from the buttons", async () => {
    render(<Editor start="One" />);
    select(0, 0);
    await userEvent.click(screen.getByRole("button", { name: "Heading" }));
    expect(body().value).toBe("## One");
    select(0, 0);
    await userEvent.click(screen.getByRole("button", { name: "Heading" }));
    expect(body().value).toBe("One");
    select(0, 3);
    await userEvent.click(screen.getByRole("button", { name: "Quote" }));
    expect(body().value).toBe("> One");
    select(2, 5);
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    expect(body().value).toBe("> [One](https://)");
    expect(body().value.slice(body().selectionStart, body().selectionEnd)).toBe("https://");
  });

  it("takes Ctrl B and Ctrl I in the text", async () => {
    render(<Editor start="word" />);
    select(0, 4);
    body().focus();
    await userEvent.keyboard("{Control>}b{/Control}");
    expect(body().value).toBe("**word**");
    await userEvent.keyboard("{Control>}i{/Control}");
    expect(body().value).toBe("***word***");
  });

  it("refuses a button's change that would pass the text's limit (CodeRabbit on #118)", async () => {
    render(<Editor start="word" maxLength={4} />);
    select(0, 4);
    await userEvent.click(screen.getByRole("button", { name: "Bold" }));
    expect(body().value).toBe("word");
    select(0, 2);
    await userEvent.click(screen.getByRole("button", { name: "Italic" }));
    expect(body().value).toBe("word");
  });

  it("gives a module's tools the editor's ways in", async () => {
    render(
      <Editor
        start="See "
        tools={({ editor }) => (
          <Button
            size="small"
            onClick={() => {
              editor.insert(`[picked: ${editor.selected() || "none"}]`);
            }}
          >
            Embed
          </Button>
        )}
      />,
    );
    select(4, 4);
    await userEvent.click(screen.getByRole("button", { name: "Embed" }));
    expect(body().value).toBe("See [picked: none]");
  });

  it("asks for the preview only while it's open, once per text, and draws it", async () => {
    const preview = vi.fn((text: string) => Promise.resolve(`<h2>${text}</h2>`));
    render(<Editor start="Hi" preview={preview} previewTitle="About" previewNote="This is how the page looks." />);
    expect(preview).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(await screen.findByRole("heading", { name: "Hi" })).toBeVisible();
    expect(screen.getByText("About")).toBeVisible();
    expect(screen.getByText("This is how the page looks.")).toBeVisible();
    await userEvent.click(screen.getByRole("tab", { name: "Write" }));
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(preview).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("tab", { name: "Write" }));
    await userEvent.type(body(), "!");
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(await screen.findByRole("heading", { name: "Hi!" })).toBeVisible();
    expect(preview).toHaveBeenLastCalledWith("Hi!");
    expect(preview).toHaveBeenCalledTimes(2);
  });

  it("says a preview that failed and asks again on Try again", async () => {
    const preview = vi.fn<(text: string) => Promise<string>>().mockRejectedValueOnce(new Error("Offline")).mockResolvedValue("<p>Back</p>");
    render(<Editor start="x" preview={preview} />);
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(await screen.findByText("The preview couldn't be loaded.")).toBeVisible();
    expect(screen.getByText("Offline")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Back")).toBeVisible();
  });

  it("says an empty text has nothing to show", async () => {
    render(<Editor preview={() => Promise.resolve("")} />);
    await userEvent.click(screen.getByRole("tab", { name: "Preview" }));
    expect(await screen.findByText("Nothing written yet.")).toBeVisible();
  });

  it("ties its hint and its error to the text", () => {
    render(<Editor hint="Markdown works here." error="The body is too long." />);
    expect(body()).toHaveAccessibleDescription("Markdown works here. The body is too long.");
    expect(body()).toHaveAttribute("aria-invalid", "true");
  });

  // jsdom has no execCommand, so every test here takes this way; Playwright's kit test takes the browser's, with Ctrl Z.
  it("sets the text and puts the selection back where the browser can't type the change", async () => {
    expect("execCommand" in document).toBe(false);
    render(<Editor start="ab" />);
    select(0, 2);
    await userEvent.click(screen.getByRole("button", { name: "Italic" }));
    await waitFor(() => {
      expect(body().value).toBe("*ab*");
    });
    expect(body().value.slice(body().selectionStart, body().selectionEnd)).toBe("ab");
  });
});
