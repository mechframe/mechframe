import { describe, expect, it } from "vitest";

import { applied, link, prefixLines, wrap, type Change, type Selection } from "./markdownEdits";

/** The text and its selection once `change` is made, the selection marked with [ and ]. */
function after(at: Selection, change: Change): string {
  const value = applied(at.value, change);
  const [start, end] = change.select;
  return `${value.slice(0, start)}[${value.slice(start, end)}]${value.slice(end)}`;
}

/** A selection from text with [ and ] marking it. */
function sel(marked: string): Selection {
  const start = marked.indexOf("[");
  const end = marked.indexOf("]") - 1;
  return { value: marked.replace("[", "").replace("]", ""), start, end };
}

describe("wrap", () => {
  it("wraps the selection and keeps it selected", () => {
    const at = sel("Some [loud] words");
    expect(after(at, wrap(at, "**", "**", "bold words"))).toBe("Some **[loud]** words");
  });

  it("puts in its placeholder, selected, when nothing is", () => {
    const at = sel("Some [] words");
    expect(after(at, wrap(at, "_", "_", "italic words"))).toBe("Some _[italic words]_ words");
  });

  it("unwraps a selection that's wrapped already, from outside or inside", () => {
    const outside = sel("Some **[loud]** words");
    expect(after(outside, wrap(outside, "**", "**", "bold words"))).toBe("Some [loud] words");
    const inside = sel("Some [**loud**] words");
    expect(after(inside, wrap(inside, "**", "**", "bold words"))).toBe("Some [loud] words");
  });

  it("takes only a whole wrapper as one, and nothing before the text's start", () => {
    const at = sel("[*]*x");
    expect(applied(at.value, wrap(at, "**", "**", "b"))).toBe("******x");
    const start = sel("[x]**");
    expect(applied(start.value, wrap(start, "**", "**", "b"))).toBe("**x****");
  });
});

describe("wrap with one character (Italic's *; CodeRabbit on #118)", () => {
  const italic = (marked: string) => {
    const at = sel(marked);
    return after(at, wrap(at, "*", "*", "italic words"));
  };

  it("wraps inside a word, where an underscore wouldn't make emphasis", () => {
    expect(italic("a[b]c")).toBe("a*[b]*c");
  });

  it("takes an odd run of stars as italic and an even one as bold only", () => {
    expect(italic("*[word]*")).toBe("[word]");
    expect(italic("**[word]**")).toBe("***[word]***");
    expect(italic("***[word]***")).toBe("**[word]**");
  });

  it("reads a selection's own stars the same way", () => {
    expect(italic("[*word*]")).toBe("[word]");
    expect(italic("[**word**]")).toBe("*[**word**]*");
  });
});

describe("prefixLines", () => {
  it("marks the caret's line and keeps the caret in its words", () => {
    const at = sel("One\nTw[]o\nThree");
    expect(after(at, prefixLines(at, "## "))).toBe("One\n## Tw[]o\nThree");
  });

  it("marks every line the selection touches, and only those", () => {
    const at = sel("One\nT[wo\nThr]ee\nFour");
    expect(after(at, prefixLines(at, "> "))).toBe("One\n[> Two\n> Three]\nFour");
  });

  it("unmarks the lines when every one is marked", () => {
    const at = sel("[> Two\n> Three]");
    expect(after(at, prefixLines(at, "> "))).toBe("[Two\nThree]");
  });

  it("marks the lines that aren't when only some are", () => {
    const at = sel("[> Two\nThree]");
    expect(applied(at.value, prefixLines(at, "> "))).toBe("> > Two\n> Three");
  });

  it("leaves the next line alone when the selection ends at its start", () => {
    const at = sel("[One\n]Two");
    expect(applied(at.value, prefixLines(at, "## "))).toBe("## One\nTwo");
  });

  it("marks the first line when the text starts with an empty one and the caret is at its start (Codex on #118)", () => {
    const at = { value: "\nTwo", start: 0, end: 0 };
    expect(applied(at.value, prefixLines(at, "## "))).toBe("## \nTwo");
    const both = { value: "\nTwo", start: 0, end: 4 };
    expect(applied(both.value, prefixLines(both, "> "))).toBe("> \n> Two");
  });

  it("marks the first line and the last", () => {
    const first = sel("[]One\nTwo");
    expect(applied(first.value, prefixLines(first, "## "))).toBe("## One\nTwo");
    const last = sel("One\nTwo[]");
    expect(applied(last.value, prefixLines(last, "## "))).toBe("One\n## Two");
  });
});

describe("link", () => {
  it("links the selection and selects the address to type over", () => {
    const at = sel("See [the credits] now");
    expect(after(at, link(at, "link words"))).toBe("See [the credits]([https://]) now");
  });

  it("links its placeholder when nothing is selected", () => {
    const at = sel("See []");
    expect(after(at, link(at, "link words"))).toBe("See [link words]([https://])");
  });
});
