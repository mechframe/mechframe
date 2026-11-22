/**
 * Prose (decision 0055): the HTML the server made from someone's Markdown
 * (`kernel.markdown.render`, cleaned by nh3), drawn in the theme's type. It
 * only ever takes HTML from the API: never a string made in the browser.
 *
 * A link to a page on this site moves inside the app, as the kit's links do,
 * unless it's opened elsewhere (a modifier key, another button) or asks to
 * download.
 */
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router";

export type ProseProps = {
  /** Cleaned HTML from the server. */
  html: string;
  className?: string;
};

export function Prose({ html, className }: ProseProps) {
  const box = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

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

  return (
    <div
      ref={box}
      className={className ? `mf-prose ${className}` : "mf-prose"}
      // The server's HTML, cleaned to the body's allowlist (kernel.markdown).
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
