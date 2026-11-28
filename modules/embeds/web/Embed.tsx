/**
 * A link as its provider's player (`dev plans/contracts/embeds.md` §2; from
 * VybeSite's `MediaEmbed.tsx`): a figure, the facade until the visitor plays
 * (hook 6, `media`), then the provider's iframe, with the writer's words
 * under it linked to the original. That link still works if a player is
 * refused, and it's the backlink SoundCloud's and Spotify's terms ask for.
 *
 * The facade is the site's own: nothing loads from the provider until its
 * Play is clicked, which grants `media` for the site. The iframe never plays
 * by itself (WCAG 1.4.2), except a YouTube player just after that click.
 * Its shape is a class, never a style, for the CSP.
 *
 * `EmbedFrame` (0.1.2, `dev plans/contracts/bandcamp-player.md`) is the same
 * iframe alone, for a page that draws its own facade, such as a site's Listen
 * in place of its player's controls: it draws nothing until `media` is
 * granted, so the page's Listen grants it.
 */
import { Button, ConsentGate, useConsent } from "@/kernel";
import { useState } from "react";

import "./embeds.css";
import { recognise, wordsFor, type Embed as Found } from "./providers";

/** The sandbox every player runs in: its own scripts, storage and pop-ups
 * (YouTube's "Watch on YouTube" and the others' links open in a tab of their
 * own), never a form, a download or our page's navigation. */
const SANDBOX = "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-presentation";

export type EmbedProps = {
  /** The link as the writer gave it. */
  link: string;
  /** The writer's words; the kind's own ("A video on YouTube") when blank or the address. */
  words?: string;
};

/** The player's address, playing at once when the visitor has just asked. */
function playing(found: Found, now: boolean): string {
  if (!now || found.provider !== "youtube") return found.player;
  return `${found.player}${found.player.includes("?") ? "&" : "?"}autoplay=1`;
}

function Facade({ found, words, onPlay }: { found: Found; words: string; onPlay: () => void }) {
  const play = found.verb === "Listen" ? "Listen" : "Play";
  return (
    <div className="mf-embed-facade">
      <p className="mf-embed-from">{found.name}</p>
      <p className="mf-embed-words">{words}</p>
      <Button variant="primary" icon="play" aria-label={`${play}: ${words}`} onClick={onPlay}>
        {play}
      </Button>
      <p className="mf-embed-note">Plays from {found.name}, which may set cookies.</p>
    </div>
  );
}

/** The provider's player: one sandbox, title and loading for `Embed` and `EmbedFrame`. */
function Frame({ className, found, words, src }: { className: string; found: Found; words: string; src: string }) {
  return (
    <iframe
      className={className}
      src={src}
      title={`${found.name} player: ${words}`}
      loading="lazy"
      referrerPolicy="strict-origin-when-cross-origin"
      sandbox={SANDBOX}
      allow={found.allow || undefined}
      allowFullScreen={found.allow.includes("fullscreen") || undefined}
    />
  );
}

export type EmbedFrameProps = {
  /** The link, as `Embed` takes it: Bandcamp's with its player's id in the fragment. */
  link: string;
  /** Its words for the frame's title; the kind's own ("A track on Bandcamp") when blank. */
  words?: string;
};

/**
 * The provider's iframe alone: no figure, no facade, no caption. Nothing at
 * all until `media` is granted, and nothing for a link that isn't a player.
 * It never plays by itself: the visitor presses the provider's own play.
 * Unmounting it stops it, which is how a page takes turns with it.
 */
export function EmbedFrame({ link, words = "" }: EmbedFrameProps) {
  const { granted } = useConsent("media");
  const found = recognise(link);
  if (!granted || !found) return null;
  return (
    <Frame
      className={`mf-embed-frame mf-embed-frame--${found.shape}`}
      found={found}
      words={wordsFor(found, words)}
      src={found.player}
    />
  );
}

export function Embed({ link, words = "" }: EmbedProps) {
  // The link the visitor played: a link put in its place doesn't play by itself (CodeRabbit on #127).
  const [asked, setAsked] = useState<string | null>(null);
  // A withdrawn grant forgets the Play, so a later grant doesn't start it (CodeRabbit on #127).
  const { granted } = useConsent("media");
  const [wasGranted, setWasGranted] = useState(granted);
  if (granted !== wasGranted) {
    setWasGranted(granted);
    if (!granted) setAsked(null);
  }
  const found = recognise(link);
  if (!found) {
    return (
      <p>
        <a href={link}>{words.trim() || link}</a>
      </p>
    );
  }
  const said = wordsFor(found, words);
  return (
    <figure className={`mf-embed mf-embed--${found.shape}`}>
      <ConsentGate
        category="media"
        fallback={(grant) => (
          <Facade
            found={found}
            words={said}
            onPlay={() => {
              setAsked(link);
              grant();
            }}
          />
        )}
      >
        <Frame className="mf-embed-player" found={found} words={said} src={playing(found, asked === link)} />
      </ConsentGate>
      <figcaption className="mf-embed-caption">
        <a href={link}>{said}</a>
      </figcaption>
    </figure>
  );
}
