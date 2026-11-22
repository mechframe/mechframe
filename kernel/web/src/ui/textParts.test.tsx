// The kit's text parts (decision 0060): the buttons other code adds to
// MarkdownEditor, and the players a lone link gives way to in Prose.
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode, useState, type ReactNode } from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { MarkdownEditor, type MarkdownTools } from "./MarkdownEditor";
import { Prose } from "./Prose";
import { TextPartsContext, type TextParts } from "./textParts";

function Stamp({ editor }: { editor: MarkdownTools }) {
  return (
    <Button
      size="small"
      onClick={() => {
        editor.insert("[stamp]");
      }}
    >
      Stamp
    </Button>
  );
}

function Broken(): ReactNode {
  throw new Error("This part is broken.");
}

function Player({ href, words }: { href: string; words: string }) {
  return (
    <figure data-testid="player" data-href={href}>
      {words}
    </figure>
  );
}

const onTube = (href: string) => href.startsWith("https://tube.example/");

function parts(overrides: Partial<TextParts> = {}): TextParts {
  return { tools: [], embeds: [], ...overrides };
}

function Editor({ given, own }: { given: TextParts; own?: boolean }) {
  const [value, setValue] = useState("");
  return (
    <MemoryRouter>
      <TextPartsContext.Provider value={given}>
        <MarkdownEditor
          label="Page body"
          value={value}
          onChange={setValue}
          preview={(text) => Promise.resolve(`<p>${text}</p>`)}
          {...(own ? { tools: () => <Button size="small">Own</Button> } : {})}
        />
      </TextPartsContext.Provider>
      <output data-testid="value">{value}</output>
    </MemoryRouter>
  );
}

function drawn(html: string, given: TextParts | null) {
  const prose = <Prose html={html} />;
  return render(
    <MemoryRouter>{given ? <TextPartsContext.Provider value={given}>{prose}</TextPartsContext.Provider> : prose}</MemoryRouter>,
  );
}

describe("MarkdownEditor's added buttons (editor.tools)", () => {
  it("draws them after its own buttons and the page's tools, given the editor's ways in", async () => {
    render(<Editor own given={parts({ tools: [{ key: "embeds:editor.tools:0", Part: Stamp }] })} />);
    const names = Array.from(screen.getByRole("group", { name: "Formatting" }).querySelectorAll("button")).map(
      (button) => button.textContent,
    );
    expect(names.slice(-2)).toEqual(["Own", "Stamp"]);
    await userEvent.click(screen.getByRole("button", { name: "Stamp" }));
    expect(screen.getByTestId("value")).toHaveTextContent("[stamp]");
  });

  it("leaves out a button that fails, and keeps the rest", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(
      <Editor
        given={parts({
          tools: [
            { key: "a", Part: Broken },
            { key: "b", Part: Stamp },
          ],
        })}
      />,
    );
    expect(screen.getByRole("button", { name: "Stamp" })).toBeInTheDocument();
    expect(screen.queryByText("This part didn't load.")).toBeNull();
    error.mockRestore();
  });

  it("draws only its own without them", () => {
    render(<Editor given={parts()} />);
    expect(screen.getByRole("group", { name: "Formatting" }).querySelectorAll("button")).toHaveLength(5);
  });
});

describe("Prose's players (prose.embed)", () => {
  const embeds = parts({ embeds: [{ key: "embeds:prose.embed:0", claims: onTube, Part: Player }] });

  it("puts a part in place of a paragraph that holds only a link it claims, given the link and its words", () => {
    const { container } = drawn(
      '<p>Before.</p><p><a href="https://tube.example/watch?v=1" rel="noopener">Our new video</a></p><p>After.</p>',
      embeds,
    );
    const player = screen.getByTestId("player");
    expect(player).toHaveAttribute("data-href", "https://tube.example/watch?v=1");
    expect(player).toHaveTextContent("Our new video");
    expect(container.querySelectorAll(".mf-prose > p")).toHaveLength(2);
    expect(Array.from(container.querySelector(".mf-prose")?.children ?? []).map((child) => child.textContent)).toEqual([
      "Before.",
      "Our new video",
      "After.",
    ]);
  });

  it("leaves a link in a sentence, a link it doesn't claim, and a paragraph with an image", () => {
    drawn(
      '<p>Watch <a href="https://tube.example/1">this</a> now.</p>' +
        '<p><a href="https://elsewhere.example/1">Elsewhere</a></p>' +
        '<p><a href="https://tube.example/2"><img src="/cover.png" alt="Cover"></a></p>',
      embeds,
    );
    expect(screen.queryByTestId("player")).toBeNull();
    expect(screen.getByRole("link", { name: "this" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Elsewhere" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cover" })).toBeInTheDocument();
  });

  it("leaves every link as it is without the parts", () => {
    drawn('<p><a href="https://tube.example/1">A video</a></p>', null);
    expect(screen.getByRole("link", { name: "A video" })).toBeInTheDocument();
  });

  it("draws a new text's players, and gives the old paragraph back first, once each in StrictMode", () => {
    const html = (n: number) => `<p><a href="https://tube.example/${String(n)}">Video ${String(n)}</a></p>`;
    const { rerender } = render(
      <StrictMode>
        <MemoryRouter>
          <TextPartsContext.Provider value={embeds}>
            <Prose html={html(1)} />
          </TextPartsContext.Provider>
        </MemoryRouter>
      </StrictMode>,
    );
    expect(screen.getAllByTestId("player")).toHaveLength(1);
    act(() => {
      rerender(
        <StrictMode>
          <MemoryRouter>
            <TextPartsContext.Provider value={embeds}>
              <Prose html={html(2)} />
            </TextPartsContext.Provider>
          </MemoryRouter>
        </StrictMode>,
      );
    });
    const players = screen.getAllByTestId("player");
    expect(players).toHaveLength(1);
    expect(players[0]).toHaveAttribute("data-href", "https://tube.example/2");
  });

  it("shows the link again when its part fails", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);
    drawn(
      '<p><a href="https://tube.example/1">A video</a></p>',
      parts({ embeds: [{ key: "x", claims: onTube, Part: Broken }] }),
    );
    expect(screen.getByRole("link", { name: "A video" })).toHaveAttribute("href", "https://tube.example/1");
    error.mockRestore();
  });
});
