// The Art page, /art, /art/:discipline and /art/piece/:slug
// (`dev plans/contracts/portfolio.md` §2; VM Website's Art board): the title and
// the settings' lead, a chip for each discipline with something live (each a
// link, so a filter is an address), the grid newest first with Load more, and,
// at a piece's address, the board's panel above the grid: the big picture (and
// for a video, embeds' player behind its consent facade), the discipline, the
// title, "By petro, 2026", the words, "Commission work like this" while the
// settings have a link, and Close back to the list it came from. The words are
// the server copy's own, so a crawler reads what a person sees.
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { ApiProblem, Button, LoadError, NotFound, Seo, buttonClass, useSite } from "@/kernel";
import { Embed } from "@/modules/embeds/public";
import { Picture } from "@/modules/media/public";

import { ART, bylineOf, lineOf, pathOf, useApiQuery, type LivePiece } from "../api";
import { PieceCard } from "../components/PieceCard";
import { useDisciplines, usePiece, usePieces } from "../reads";
import "../portfolio.css";

type Came = { from?: string } | null;

function Panel({ piece, commission, back }: { piece: LivePiece; commission: string; back: string }) {
  const navigate = useNavigate();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [piece.id]);
  const byline = bylineOf(piece);
  const paragraphs = piece.about.split(/\n{2,}/).filter((each) => each.trim());
  return (
    <section className="mf-portfolio-panel" aria-labelledby="mf-portfolio-piece">
      <div className="mf-portfolio-panel-picture">
        {piece.picture ? (
          <Picture image={piece.picture} sizes="(min-width: 60rem) 55vw, 100vw" loading="eager" />
        ) : (
          <span className="mf-portfolio-card-plain" aria-hidden="true" />
        )}
        {piece.video ? <Embed link={piece.video.url} words={piece.title} /> : null}
      </div>
      <div className="mf-portfolio-panel-words">
        {piece.discipline ? (
          <p className="mf-portfolio-panel-discipline">
            <Link to={`${ART}/${piece.discipline.slug}`}>{piece.discipline.label}</Link>
          </p>
        ) : null}
        <h2 id="mf-portfolio-piece" ref={heading} tabIndex={-1} className="mf-portfolio-panel-title">
          {piece.title}
        </h2>
        {byline ? <p className="mf-portfolio-panel-byline">{byline}</p> : null}
        {paragraphs.map((each, index) => (
          <p key={index} className="mf-portfolio-panel-about">
            {each}
          </p>
        ))}
        <div className="mf-portfolio-panel-actions">
          {commission ? (
            commission.startsWith("/") ? (
              <Link to={commission} className={buttonClass({ variant: "primary" })}>
                Commission work like this
              </Link>
            ) : (
              <a href={commission} className={buttonClass({ variant: "primary" })} rel="noreferrer">
                Commission work like this
              </a>
            )
          ) : null}
          <Button
            onClick={() => {
              void navigate(back, { state: { closed: piece.slug } });
            }}
          >
            Close
          </Button>
        </div>
      </div>
    </section>
  );
}

export default function Art() {
  const site = useSite();
  const params = useParams();
  const location = useLocation();
  const slug = params.slug ?? "";
  const came = location.state as Came;
  // At a piece's address the grid stays the list it came from; else the address's own.
  const fromList = slug ? (came?.from ?? ART) : location.pathname;
  const discipline = slug ? (fromList.startsWith(`${ART}/`) ? fromList.slice(ART.length + 1) : "") : (params.discipline ?? "");
  const page = useApiQuery("get", "/api/portfolio/art");
  const disciplines = useDisciplines();
  const pieces = usePieces({ discipline });
  const piece = usePiece(slug);
  const cards = pieces.data?.pages.flatMap((each) => each.items) ?? [];
  const chips = disciplines.data?.items ?? [];
  const named = chips.find((each) => each.slug === discipline);
  // A first load holds back until the list, the chips and the words answer, so
  // <main> stays empty and the footer comes with the page (decision 0066).
  const settled = !pieces.isPending && !disciplines.isPending && !page.isPending && (!slug || !piece.isPending);
  const [drawn, setDrawn] = useState(settled);
  if (settled && !drawn) setDrawn(true);
  const lead = page.data?.lead ?? "";
  const commission = page.data?.commission_link ?? "";

  const missingDiscipline = pieces.error instanceof ApiProblem && pieces.error.code === "portfolio.discipline_not_found";
  const missingPiece = slug !== "" && piece.error instanceof ApiProblem && piece.error.status === 404;
  if (missingDiscipline || missingPiece) return <NotFound />;
  if (!drawn) return null;

  const title = piece.data ? (piece.data.artist ? `${piece.data.title}, by ${piece.data.artist}` : piece.data.title) : named ? `${named.label} · Art` : "Art";
  const description = piece.data ? piece.data.about || lineOf(piece.data) || piece.data.title : named ? `${named.label} from ${site?.name ?? "the site"}.` : lead || `Art from ${site?.name ?? "the site"}.`;
  const closed = (location.state as { closed?: string } | null)?.closed;

  return (
    <div className="mf-portfolio">
      <Seo title={site ? `${title} · ${site.name}` : title} description={description} path={slug ? pathOf(slug) : location.pathname} />
      <h1>Art</h1>
      {lead ? <p className="mf-portfolio-lead">{lead}</p> : null}
      {chips.length ? (
        <nav className="mf-portfolio-chips" aria-label="Show">
          <Link to={ART} className="mf-portfolio-chip" aria-current={discipline === "" ? "page" : undefined}>
            All
          </Link>
          {chips.map((each) => (
            <Link key={each.slug} to={`${ART}/${each.slug}`} className="mf-portfolio-chip" aria-current={discipline === each.slug ? "page" : undefined}>
              {each.label}
            </Link>
          ))}
        </nav>
      ) : null}
      {piece.data ? <Panel piece={piece.data} commission={commission} back={fromList} /> : null}
      {piece.error ? <LoadError what="The piece" error={piece.error} onRetry={() => void piece.refetch()} /> : null}
      {pieces.error ? (
        <LoadError what="The art" error={pieces.error} onRetry={() => void pieces.refetch()} />
      ) : cards.length ? (
        <>
          <ul className="mf-portfolio-cards" aria-label="Artwork">
            {cards.map((card) => (
              <li key={card.id}>
                <PieceCard card={card} current={card.slug === slug} focus={card.slug === closed} from={fromList} />
              </li>
            ))}
          </ul>
          {pieces.hasNextPage ? (
            <Button disabled={pieces.isFetchingNextPage} onClick={() => void pieces.fetchNextPage()}>
              Load more
            </Button>
          ) : null}
        </>
      ) : (
        <p className="mf-portfolio-empty">Nothing here yet.</p>
      )}
    </div>
  );
}
