// The players' one list on the web (web/providers.ts): the same cases the
// backend answers (tests/providers.cases.json), the Markdown the editor writes,
// Bandcamp's embed code, and a playlist item's YouTube id.
import { describe, expect, it } from "vitest";

import { FRAME_HOSTS, embedMarkdown, fromBandcampCode, recognise, wordsFor, youtubeId } from "../../web/providers";
import cases from "../providers.cases.json";

type Recognised = { href: string; provider: string; kind: string; player: string; shape: string };
type Words = { href: string; text: string; words: string };
type Code = { name: string; code: string; href: string | null; words?: string };

describe("recognise", () => {
  it.each(cases.recognised as Recognised[])("takes $href as its provider's player", (each) => {
    const found = recognise(each.href);
    expect(found && [found.provider, found.kind, found.player, found.shape]).toEqual([
      each.provider,
      each.kind,
      each.player,
      each.shape,
    ]);
  });

  it.each(cases.refused)("leaves %j a link", (href) => {
    expect(recognise(href)).toBeNull();
  });

  it("builds every player on its provider's one frame host", () => {
    for (const each of cases.recognised as Recognised[]) {
      expect(FRAME_HOSTS.some((host) => each.player.startsWith(`${host}/`))).toBe(true);
    }
  });
});

describe("wordsFor", () => {
  it.each(cases.words as Words[])("gives $href with $text the words $words", (each) => {
    const found = recognise(each.href);
    if (!found) throw new Error(`${each.href} isn't a player.`);
    expect(wordsFor(found, each.text)).toBe(each.words);
  });
});

describe("embedMarkdown", () => {
  it("writes the link with the writer's words, Markdown's own marks escaped", () => {
    expect(embedMarkdown("https://youtu.be/aBcDeFgHiJk", "Our *spring* [tour]")).toBe(
      "[Our \\*spring\\* \\[tour\\]](https://youtu.be/aBcDeFgHiJk)",
    );
  });

  it("gives a bare player the kind's own words", () => {
    expect(embedMarkdown("https://youtu.be/aBcDeFgHiJk", "  ")).toBe("[A video on YouTube](https://youtu.be/aBcDeFgHiJk)");
  });

  it("names a link it can't play by its address when no words are given (CodeRabbit on #127)", () => {
    expect(embedMarkdown(" https://example.net/a ", "  ")).toBe("[https://example.net/a](https://example.net/a)");
  });

  it("writes the address recognise read, a pasted tab or line break taken out (CodeRabbit on #127)", () => {
    expect(embedMarkdown("https://youtu.be/aBcDe\tFgHi\nJk", "")).toBe(
      "[A video on YouTube](https://youtu.be/aBcDeFgHiJk)",
    );
  });

  it("encodes a space beyond ASCII as its UTF-8 bytes (CodeRabbit on #127)", () => {
    const nbsp = String.fromCharCode(0xa0);
    expect(embedMarkdown(`https://example.net/a${nbsp}b`, "x")).toBe("[x](https://example.net/a%C2%A0b)");
  });

  it("puts words that cross a line break on one line, so the link stays one paragraph (CodeRabbit on #127)", () => {
    expect(embedMarkdown("https://youtu.be/aBcDeFgHiJk", "First\n\n  Second\nThird")).toBe(
      "[First Second Third](https://youtu.be/aBcDeFgHiJk)",
    );
  });

  it("encodes the brackets and spaces that would end the link", () => {
    expect(embedMarkdown("https://example.net/a (b)", "Elsewhere")).toBe("[Elsewhere](https://example.net/a%20%28b%29)");
  });
});

describe("fromBandcampCode", () => {
  const code =
    '<iframe style="border: 0; width: 100%; height: 120px;" ' +
    'src="https://bandcamp.com/EmbeddedPlayer/album=1234567/size=large/bgcol=ffffff/linkcol=0687f5/tracklist=false/artwork=small/transparent=true/" seamless>' +
    '<a href="https://exampleband.bandcamp.com/album/weightless">Weightless by Example Band &amp; Friends</a></iframe>';

  it("reads the album's page, its player's id and its words from Bandcamp's own code", () => {
    expect(fromBandcampCode(code)).toEqual({
      href: "https://exampleband.bandcamp.com/album/weightless#bandcamp-album=1234567",
      words: "Weightless by Example Band & Friends",
    });
  });

  it.each(cases.bandcamp_codes as Code[])("reads $name as the server does (0.1.2)", (each) => {
    expect(fromBandcampCode(each.code)).toEqual(each.href ? { href: each.href, words: each.words } : null);
  });

  it("counts a paste's length in UTF-16, as the server does", () => {
    expect(fromBandcampCode(code + " ".repeat(4096 - code.length))).not.toBeNull();
    expect(fromBandcampCode(code + String.fromCodePoint(0x1f3b5).repeat(Math.floor((4096 - code.length) / 2) + 1))).toBeNull();
  });

  it("refuses a code whose player and page disagree, anything else, and a paste too long to be a code", () => {
    expect(fromBandcampCode(code.replace("album=1234567", "track=1234567"))).toBeNull();
    expect(fromBandcampCode("<p>Not a code</p>")).toBeNull();
    expect(fromBandcampCode(code + " ".repeat(5000))).toBeNull();
  });
});

describe("youtubeId", () => {
  it.each([
    ["aBcDeFgHiJk", "aBcDeFgHiJk"],
    ["https://youtu.be/aBcDeFgHiJk?t=30", "aBcDeFgHiJk"],
    ["https://www.youtube.com/watch?v=aBcDeFgHiJk&list=PL1", "aBcDeFgHiJk"],
    ["https://www.youtube.com/shorts/aBcDeFgHiJk", "aBcDeFgHiJk"],
    ["https://m.youtube.com/live/aBcDeFgHiJk", "aBcDeFgHiJk"],
  ])("reads %s", (link, id) => {
    expect(youtubeId(link)).toBe(id);
  });

  it("refuses a playlist, another provider and anything else", () => {
    expect(youtubeId("https://www.youtube.com/playlist?list=PLaBcDeFgH12345")).toBeNull();
    expect(youtubeId("https://open.spotify.com/track/0aBcDeFgHiJkLmNoPqRsTu")).toBeNull();
    expect(youtubeId("not a video")).toBeNull();
  });
});
