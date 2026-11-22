/**
 * Prose (decision 0055): the HTML the server made from someone's Markdown
 * (`kernel.markdown.render`, cleaned by nh3), drawn in the theme's type. It
 * only ever takes HTML from the API: never a string made in the browser.
 *
 * A link to a page on this site moves inside the app, as the kit's links do,
 * unless it's opened elsewhere (a modifier key, another button) or asks to
 * download.
 *
 * A paragraph that holds only a link a player claims (`prose.embed`, decision
 * 0060) gives way to that player, given the link and its words; a part that
 * fails shows the link again. Nothing else changes, and without players every
 * link stays as the server drew it.
 */
import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router";

import { ErrorBoundary } from "./ErrorBoundary";
import { useTextParts, type ProseEmbedPart } from "./textParts";

export type ProseProps = {
  /** Cleaned HTML from the server. */
  html: string;
  className?: string;
};

/** A player drawn where its paragraph was. */
type Placed = { key: string; host: HTMLElement; href: string; words: string; Part: ProseEmbedPart["Part"] };

/** The paragraph's one link, when it holds nothing else (and no image). */
function loneLink(paragraph: HTMLParagraphElement): Element | null {
  const nodes = Array.from(paragraph.childNodes).filter(
    (node) => !(node.nodeType === Node.TEXT_NODE && (node.textContent ?? "").trim() === ""),
  );
  const only = nodes.length === 1 ? nodes[0] : undefined;
  if (!(only instanceof Element) || only.tagName !== "A" || only.querySelector("img")) return null;
  return only.getAttribute("href") ? only : null;
}

export function Prose({ html, className }: ProseProps) {
  const box = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { embeds } = useTextParts();
  const [placed, setPlaced] = useState<readonly Placed[]>([]);
  // One object per text: React sets the HTML again whenever this object is a new one, which would take the players out.
  const inner = useMemo(() => ({ __html: html }), [html]);

  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const onClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      const anchor = event.target instanceof Element ? event.target.closest("a") : null;
      if (!anchor || !element.contains(anchor) || anchor.hasAttribute("download")) return;
      const href = anchor.getAttribute("href") ?? "";
      if (!href.startsWith("/") || href.startsWith("//") || href.includes("\\")) return;
      event.preventDefault();
      void navigate(href);
    };
    element.addEventListener("click", onClick);
    return () => {
      element.removeEventListener("click", onClick);
    };
  }, [navigate]);

  // Each lone link a player claims: its paragraph swapped for the player's
  // place, and given back when the text or the players change (StrictMode's
  // second run then finds the paragraphs again).
  useLayoutEffect(() => {
    const element = box.current;
    if (!element || embeds.length === 0) {
      setPlaced((was) => (was.length === 0 ? was : []));
      return;
    }
    const swapped: { paragraph: HTMLParagraphElement; host: HTMLElement }[] = [];
    const found: Placed[] = [];
    element.querySelectorAll("p").forEach((paragraph, at) => {
      const anchor = loneLink(paragraph);
      const href = anchor?.getAttribute("href") ?? "";
      const player = anchor ? embeds.find((embed) => embed.claims(href)) : undefined;
      if (!anchor || !player) return;
      const host = document.createElement("div");
      host.className = "mf-prose-embed";
      paragraph.replaceWith(host);
      swapped.push({ paragraph, host });
      found.push({ key: `${player.key}:${String(at)}`, host, href, words: anchor.textContent.trim(), Part: player.Part });
    });
    setPlaced(found);
    return () => {
      for (const { paragraph, host } of swapped) if (host.isConnected) host.replaceWith(paragraph);
    };
  }, [html, embeds]);

  return (
    <>
      <div
        ref={box}
        className={className ? `mf-prose ${className}` : "mf-prose"}
        // The server's HTML, cleaned to the body's allowlist (kernel.markdown).
        dangerouslySetInnerHTML={inner}
      />
      {placed.map(({ key, host, href, words, Part }) =>
        createPortal(
          <ErrorBoundary
            where={`The player for ${href}`}
            fallback={() => (
              <p>
                <a href={href}>{words || href}</a>
              </p>
            )}
          >
            <Suspense fallback={null}>
              <Part href={href} words={words} />
            </Suspense>
          </ErrorBoundary>,
          host,
          key,
        ),
      )}
    </>
  );
}
