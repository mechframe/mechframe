// embeds' players and its Embed button (dev plans/contracts/embeds.md §7): the
// facade until `media` is granted, the sandboxed iframe after, a lone link in
// Prose drawn as its player, the frame alone behind a page's own Listen
// (0.1.2, dev plans/contracts/bandcamp-player.md §7), and the editor's dialog.
import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { CONSENT_COOKIE, MarkdownEditor, Prose, useConsent } from "@/kernel";
import { renderWithKernel } from "@/kernel/testing";
import { Embed, EmbedFrame } from "@/modules/embeds/public";

import embeds from "../../web/module.web";

const VIDEO = "https://www.youtube.com/watch?v=aBcDeFgHiJk";

afterEach(() => {
  document.cookie = `${CONSENT_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax; Secure`;
});

describe("Embed", () => {
  it("is the site's own facade until the visitor plays, with the words linked to the original", () => {
    renderWithKernel(<Embed link={VIDEO} words="Our spring tour" />);
    expect(document.querySelector("iframe")).toBeNull();
    expect(screen.getByRole("button", { name: "Play: Our spring tour" })).toBeInTheDocument();
    expect(screen.getByText("Plays from YouTube, which may set cookies.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Our spring tour" })).toHaveAttribute("href", VIDEO);
  });

  it("draws the sandboxed player once Play is clicked, playing because it was asked, and grants media", async () => {
    renderWithKernel(<Embed link={VIDEO} words="Our spring tour" />);
    await userEvent.click(screen.getByRole("button", { name: "Play: Our spring tour" }));
    const player = screen.getByTitle("YouTube player: Our spring tour");
    expect(player).toHaveAttribute("src", "https://www.youtube-nocookie.com/embed/aBcDeFgHiJk?autoplay=1");
    expect(player).toHaveAttribute("loading", "lazy");
    expect(player).toHaveAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    expect(player.getAttribute("sandbox")).toBe(
      "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation",
    );
    expect(player.getAttribute("allow")).toContain("encrypted-media");
    expect(document.cookie).toContain(`${CONSENT_COOKIE}=media`);
  });

  it("plays at once only the link that was played, not one put in its place (CodeRabbit on #127)", async () => {
    const other = "https://youtu.be/zYxWvUtSrQp";
    function Swap() {
      const [link, setLink] = useState(VIDEO);
      return (
        <>
          <Embed link={link} words="A video" />
          <button
            type="button"
            onClick={() => {
              setLink(other);
            }}
          >
            Swap
          </button>
        </>
      );
    }
    renderWithKernel(<Swap />);
    await userEvent.click(screen.getByRole("button", { name: "Play: A video" }));
    await userEvent.click(screen.getByRole("button", { name: "Swap" }));
    expect(screen.getByTitle("YouTube player: A video")).toHaveAttribute(
      "src",
      "https://www.youtube-nocookie.com/embed/zYxWvUtSrQp",
    );
  });

  it("forgets a Play once media is withdrawn, so a later grant doesn't start it (CodeRabbit on #127)", async () => {
    function Choices() {
      const media = useConsent("media");
      return (
        <>
          <button type="button" onClick={media.withdraw}>
            Withdraw media
          </button>
          <button type="button" onClick={media.grant}>
            Allow media
          </button>
        </>
      );
    }
    renderWithKernel(
      <>
        <Embed link={VIDEO} words="A video" />
        <Choices />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Play: A video" }));
    await userEvent.click(screen.getByRole("button", { name: "Withdraw media" }));
    await userEvent.click(screen.getByRole("button", { name: "Allow media" }));
    expect(screen.getByTitle("YouTube player: A video")).toHaveAttribute(
      "src",
      "https://www.youtube-nocookie.com/embed/aBcDeFgHiJk",
    );
  });

  it("draws the player at once, never playing by itself, while consent isn't asked", () => {
    renderWithKernel(<Embed link="https://open.spotify.com/album/0aBcDeFgHiJkLmNoPqRsTu" />, {
      site: { consent: { mode: "off", categories: [] } },
    });
    const player = screen.getByTitle("Spotify player: An album on Spotify");
    expect(player).toHaveAttribute("src", "https://open.spotify.com/embed/album/0aBcDeFgHiJkLmNoPqRsTu");
    expect(player.closest("figure")).toHaveClass("mf-embed--strip-352");
  });

  it("asks a listener to Listen", () => {
    renderWithKernel(<Embed link="https://soundcloud.com/example-band/spring-tour" />);
    expect(screen.getByRole("button", { name: "Listen: A track on SoundCloud" })).toBeInTheDocument();
  });

  it("leaves a link it can't play as a link", () => {
    renderWithKernel(<Embed link="https://example.net/watch" words="Elsewhere" />);
    expect(screen.getByRole("link", { name: "Elsewhere" })).toHaveAttribute("href", "https://example.net/watch");
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("EmbedFrame", () => {
  const TRACK = "https://exampleband.bandcamp.com/track/one-more-time#bandcamp-track=987654321";

  /** A page's own Listen: it grants media, and the frame shows. */
  function Listen({ link }: { link: string }) {
    const media = useConsent("media");
    return (
      <>
        <button type="button" onClick={media.grant}>
          Listen
        </button>
        <EmbedFrame link={link} words="One More Time" />
      </>
    );
  }

  it("draws nothing until media is granted, then the sandboxed frame alone, sized by its shape", async () => {
    renderWithKernel(<Listen link={TRACK} />);
    expect(document.querySelector("iframe")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Listen" }));
    const frame = screen.getByTitle("Bandcamp player: One More Time");
    expect(frame).toHaveAttribute(
      "src",
      "https://bandcamp.com/EmbeddedPlayer/track=987654321/size=large/bgcol=ffffff/linkcol=0687f5/tracklist=false/artwork=small/transparent=true/",
    );
    expect(frame).toHaveClass("mf-embed-frame", "mf-embed-frame--strip-120");
    expect(frame).not.toHaveAttribute("style");
    expect(frame).toHaveAttribute("loading", "lazy");
    expect(frame).toHaveAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    expect(frame.getAttribute("sandbox")).toBe(
      "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation",
    );
    expect(frame).not.toHaveAttribute("allow");
    // No figure, facade or caption: the page draws its own.
    expect(document.querySelector("figure, figcaption, .mf-embed-facade")).toBeNull();
  });

  it("never plays by itself, even a YouTube video, and takes the kind's words when given none", () => {
    document.cookie = `${CONSENT_COOKIE}=media; Path=/; SameSite=Lax; Secure`;
    renderWithKernel(<EmbedFrame link={VIDEO} />);
    const frame = screen.getByTitle("YouTube player: A video on YouTube");
    expect(frame.getAttribute("src")).not.toContain("autoplay");
    expect(frame).toHaveClass("mf-embed-frame--video");
  });

  it("draws nothing for a link that isn't a player, granted or not", () => {
    document.cookie = `${CONSENT_COOKIE}=media; Path=/; SameSite=Lax; Secure`;
    renderWithKernel(<EmbedFrame link="https://exampleband.bandcamp.com/track/one-more-time" />);
    expect(document.querySelector("iframe")).toBeNull();
    expect(document.body.textContent).toBe("");
  });

  it("goes when media is withdrawn", async () => {
    function Withdraw() {
      const media = useConsent("media");
      return (
        <>
          <button type="button" onClick={media.withdraw}>
            Withdraw
          </button>
          <EmbedFrame link={TRACK} />
        </>
      );
    }
    document.cookie = `${CONSENT_COOKIE}=media; Path=/; SameSite=Lax; Secure`;
    renderWithKernel(<Withdraw />);
    expect(screen.getByTitle("Bandcamp player: A track on Bandcamp")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(document.querySelector("iframe")).toBeNull();
  });
});

describe("in Prose (prose.embed)", () => {
  it("draws a lone link it recognises as its player, and leaves the rest", async () => {
    renderWithKernel(
      <Prose
        html={`<p>Watch <a href="${VIDEO}">this</a> now.</p><p><a href="${VIDEO}">Our spring tour</a></p>`}
      />,
      { modules: [embeds] },
    );
    expect(await screen.findByRole("button", { name: "Play: Our spring tour" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "this" })).toBeInTheDocument();
  });

  it("leaves every link while embeds is off", () => {
    renderWithKernel(<Prose html={`<p><a href="${VIDEO}">Our spring tour</a></p>`} />, { modules: [embeds], on: [] });
    expect(screen.queryByRole("button")).toBeNull();
  });
});

function Editor() {
  const [value, setValue] = useState("Before.");
  return (
    <>
      <MarkdownEditor label="Post body" value={value} onChange={setValue} preview={(text) => Promise.resolve(text)} />
      <output data-testid="value">{value}</output>
    </>
  );
}

async function openDialog() {
  renderWithKernel(<Editor />, { modules: [embeds] });
  await userEvent.click(await screen.findByRole("button", { name: "Embed" }));
  return screen.getByRole("dialog", { name: "Embed a player" });
}

describe("the editor's Embed button (editor.tools)", () => {
  it("puts the link and its words in a paragraph of their own", async () => {
    const dialog = await openDialog();
    const text = screen.getByRole<HTMLTextAreaElement>("textbox", { name: "Post body" });
    text.setSelectionRange(7, 7);
    await userEvent.type(
      within(dialog).getByRole("textbox", { name: "Paste a link from YouTube, SoundCloud, Spotify or Bandcamp" }),
      VIDEO,
    );
    expect(within(dialog).getByRole("status")).toHaveTextContent("A video on YouTube.");
    await userEvent.type(within(dialog).getByRole("textbox", { name: "Words under the player (optional)" }), "Our tour");
    await userEvent.click(within(dialog).getByRole("button", { name: "Insert" }));
    expect(screen.getByTestId("value").textContent).toBe(`Before.\n\n[Our tour](${VIDEO})\n\n`);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("says when a link can't be played, and asks for Bandcamp's embed code", async () => {
    const dialog = await openDialog();
    const link = within(dialog).getByRole("textbox", { name: "Paste a link from YouTube, SoundCloud, Spotify or Bandcamp" });
    await userEvent.type(link, "https://example.net/");
    expect(within(dialog).getByRole("status")).toHaveTextContent("We can't play that link. It will stay a plain link.");
    await userEvent.clear(link);
    await userEvent.type(link, "https://exampleband.bandcamp.com/album/weightless");
    expect(within(dialog).getByRole("status")).toHaveTextContent("For Bandcamp, paste its embed code");
  });

  it("reads Bandcamp's embed code into its link and words", async () => {
    const dialog = await openDialog();
    const link = within(dialog).getByRole("textbox", { name: "Paste a link from YouTube, SoundCloud, Spotify or Bandcamp" });
    link.focus();
    await userEvent.paste(
      '<iframe src="https://bandcamp.com/EmbeddedPlayer/album=1234567/size=large/" seamless>' +
        '<a href="https://exampleband.bandcamp.com/album/weightless">Weightless</a></iframe>',
    );
    expect(link).toHaveValue("https://exampleband.bandcamp.com/album/weightless#bandcamp-album=1234567");
    expect(within(dialog).getByRole("textbox", { name: "Words under the player (optional)" })).toHaveValue("Weightless");
    expect(within(dialog).getByRole("status")).toHaveTextContent("An album on Bandcamp.");
  });

  it("takes an Enter that confirms a composed character as that, not as Insert (CodeRabbit on #127)", async () => {
    const dialog = await openDialog();
    const link = within(dialog).getByRole("textbox", { name: "Paste a link from YouTube, SoundCloud, Spotify or Bandcamp" });
    await userEvent.type(link, VIDEO);
    fireEvent.keyDown(link, { key: "Enter", isComposing: true });
    expect(screen.getByRole("dialog", { name: "Embed a player" })).toBeInTheDocument();
    expect(screen.getByTestId("value").textContent).toBe("Before.");
    fireEvent.keyDown(link, { key: "Enter" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("inserts nothing with no link, and Cancel leaves the text as it was", async () => {
    const dialog = await openDialog();
    expect(within(dialog).getByRole("button", { name: "Insert" })).toBeDisabled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.getByTestId("value").textContent).toBe("Before.");
  });
});
