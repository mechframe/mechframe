/**
 * A link that reads as a quiet action beside a row's buttons, as the boards
 * draw "Open the release" on Tracks' panel (VM Website's K11): the info
 * colour, the small size, no underline until it's hovered. Its box is at
 * least 24px each way, so it keeps WCAG 2.5.8's target size beside the buttons.
 * A link inside running text keeps the page's own look; this is for a link
 * that stands on its own.
 */
import type { ComponentPropsWithRef } from "react";
import { Link } from "react-router";

export type QuietLinkProps = ComponentPropsWithRef<typeof Link>;

export function QuietLink({ className, ...rest }: QuietLinkProps) {
  return <Link {...rest} className={["mf-quiet-link", className ?? ""].filter(Boolean).join(" ")} />;
}
