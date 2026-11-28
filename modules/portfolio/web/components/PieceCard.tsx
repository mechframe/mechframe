// A live piece as a grid shows it (`dev plans/contracts/portfolio.md` §2; the Art
// board's tile): its picture, its title, and "Graphic design, by petro". The Art
// page draws its grid with it, and roster's profile may too (`public.ts`).
import { useEffect, useRef } from "react";
import { Link } from "react-router";

import { Picture } from "@/modules/media/public";

import { pathOf, type Card } from "../api";

export type PieceCardProps = {
  card: Card;
  /** Shown as the one open now: the Art page's panel is its own. */
  current?: boolean;
  /** Takes the focus as it's drawn: the piece whose panel was just closed. */
  focus?: boolean;
  /** The list it's in, which the piece's page goes back to on Close. */
  from?: string;
  /** The layout's `sizes` for the picture; a grid's column by default. */
  sizes?: string;
};

/** "Graphic design, by petro": the tile's line under its title. */
function tileLine(card: Card): string {
  const parts = [card.discipline?.label, card.artist ? `by ${card.artist}` : null].filter(Boolean);
  return parts.join(", ");
}

export function PieceCard({ card, current = false, focus = false, from, sizes = "(min-width: 60rem) 25vw, (min-width: 40rem) 33vw, 50vw" }: PieceCardProps) {
  const line = tileLine(card);
  const link = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (focus) link.current?.focus();
  }, [focus]);
  return (
    <article className={current ? "mf-portfolio-card mf-portfolio-card--current" : "mf-portfolio-card"}>
      <Link ref={link} to={pathOf(card.slug)} state={from ? { from } : undefined} className="mf-portfolio-card-link" aria-current={current ? "page" : undefined}>
        {card.picture ? (
          <Picture image={{ ...card.picture, decorative: true }} sizes={sizes} className="mf-portfolio-card-picture" />
        ) : (
          <span className="mf-portfolio-card-plain" aria-hidden="true" />
        )}
        <span className="mf-portfolio-card-title">{card.title}</span>
      </Link>
      {line ? <p className="mf-portfolio-card-line">{line}</p> : null}
    </article>
  );
}
