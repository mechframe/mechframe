// The library, /music (`dev plans/contracts/discography.md` §2; the site's Music
// board): each live release newest first with its cover, kind, year and the
// Parental Advisory label while the site shows it, then Older releases, and the
// artist's own links as "Listen everywhere". The words are the server copy's own
// (`server_copy.py`), so a crawler reads what a person sees.
import { Link } from "react-router";

import { Button, LoadError, Seo, useSite } from "@/kernel";
import { Picture } from "@/modules/media/public";

import { KIND_WORDS, type ReleaseCard } from "../api";
import "../music.css";
import { useArtistLinks, useReleases } from "../reads";

function Card({ card }: { card: ReleaseCard }) {
  return (
    <article className="mf-music-card">
      {card.cover ? (
        <Picture image={card.cover} sizes="(min-width: 48rem) 45vw, 100vw" className="mf-music-art" />
      ) : (
        <div className="mf-music-art-plain" aria-hidden="true" />
      )}
      <p className="mf-music-meta">
        <span>{KIND_WORDS[card.kind]}</span>
        {card.year ? <span>{card.year}</span> : null}
        {card.explicit ? <span className="mf-music-advisory">Parental Advisory</span> : null}
      </p>
      <h2>
        <Link to={card.path}>{card.title}</Link>
      </h2>
      <div className="mf-music-words">
        {card.artist_line ? <p>{card.artist_line}</p> : null}
        {card.credit_line ? <p>{card.credit_line}</p> : null}
        {card.summary ? <p>{card.summary}</p> : null}
        {card.tracklist_to_come ? <p className="mf-music-lead">The tracklist is to come.</p> : null}
      </div>
    </article>
  );
}

export default function Music() {
  const site = useSite();
  const releases = useReleases();
  const links = useArtistLinks();
  const cards = releases.data?.pages.flatMap((page) => page.items) ?? [];
  const lead = site?.name ? `Music from ${site.name}.` : "Music.";
  return (
    <div className="mf-music">
      <Seo title={site?.name ? `Music · ${site.name}` : "Music"} description={lead} path="/music" />
      <section className="mf-music-words">
        <h1>Music</h1>
        <p className="mf-music-lead">{lead}</p>
      </section>
      {releases.error ? (
        <LoadError what="The releases" error={releases.error} onRetry={() => void releases.refetch()} />
      ) : releases.data ? (
        cards.length ? (
          <section aria-label="Releases" className="mf-music-stack">
            <div className="mf-music-grid">
              {cards.map((card) => (
                <Card key={card.slug} card={card} />
              ))}
            </div>
            {releases.hasNextPage ? (
              <div>
                <Button disabled={releases.isFetchingNextPage} onClick={() => void releases.fetchNextPage()}>
                  Older releases
                </Button>
              </div>
            ) : null}
          </section>
        ) : (
          <p>No releases yet.</p>
        )
      ) : null}
      {links.data?.items.length ? (
        <section aria-labelledby="mf-music-everywhere" className="mf-music-words">
          <h2 id="mf-music-everywhere">Listen everywhere</h2>
          <ul className="mf-music-links">
            {links.data.items.map((link) => (
              <li key={link.platform}>
                <a href={link.url} target="_blank" rel="noreferrer">
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
