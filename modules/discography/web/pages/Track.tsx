// A track that plays, at /music/:release/:track (`dev plans/contracts/discography.md`
// §2): its title, its release, audio-player's bar with its waveform (0.1.1; with
// audio-player off, the browser's own player for an upload or a link to
// SoundCloud), its credits, and its lyrics while the site shows them. The words
// are the server copy's own. An address it left moves on; any other is the 404 page.
import { useMemo } from "react";
import { Link, Navigate, useLocation, useParams } from "react-router";

import { ApiProblem, LoadError, NotFound, Seo, useModuleEnabled } from "@/kernel";
import { PlayerBar } from "@/modules/audio-player/public";
import { Picture } from "@/modules/media/public";

import { clock } from "../api";
import { Plays } from "../components/Plays";
import "../music.css";
import { playerItem } from "../player";
import { isMoved, useTrack } from "../reads";

export default function Track() {
  const { release: slug = "", track: trackSlug = "" } = useParams();
  const { search, hash } = useLocation();
  const found = useTrack(slug, trackSlug);
  // Off only when the site says so: discography is never on without it (its requirement).
  const player = useModuleEnabled("audio-player") !== false;
  const queue = useMemo(() => {
    const shown = found.data;
    if (!shown || isMoved(shown)) return [];
    return [playerItem(shown, { title: shown.release.title, artist_line: shown.artist_line, cover: shown.cover })];
  }, [found.data]);
  if (found.isPending) return null;
  if (found.error) {
    if (found.error instanceof ApiProblem && found.error.status === 404) return <NotFound />;
    return <LoadError what="This track" error={found.error} onRetry={() => void found.refetch()} />;
  }
  const track = found.data;
  if (isMoved(track)) return <Navigate to={`${track.moved}${search}${hash}`} replace />;
  const said = `${track.title}, track ${String(track.number)} of ${track.release.title}`;
  return (
    <article className="mf-music">
      <Seo
        title={`${track.title} · ${track.release.title}`}
        description={track.artist_line ? `${said}, by ${track.artist_line}.` : `${said}.`}
        path={track.path}
        {...(track.cover ? { image: track.cover.url } : {})}
      />
      <section className="mf-music-hero">
        {track.cover ? (
          <Picture image={track.cover} sizes="(min-width: 48rem) 40vw, 100vw" loading="eager" className="mf-music-art" />
        ) : (
          <div className="mf-music-art-plain" aria-hidden="true" />
        )}
        <div className="mf-music-words">
          <nav className="mf-music-crumbs" aria-label="Breadcrumb">
            <Link to="/music">Music</Link> / <Link to={track.release.path}>{track.release.title}</Link>
          </nav>
          <h1>{track.title}</h1>
          <p>
            <Link to={track.release.path}>{track.release.title}</Link>
          </p>
          <p className="mf-music-meta">
            <span>Track {track.number}</span>
            {track.duration_ms ? <span>{clock(track.duration_ms)}</span> : null}
            {track.explicit ? <span className="mf-music-advisory">Parental Advisory</span> : null}
          </p>
          {player ? null : <Plays track={track} label={track.title} />}
        </div>
      </section>
      {player ? <PlayerBar queue={queue} label="Player" /> : null}
      {track.credits.length ? (
        <section aria-labelledby="mf-music-credits" className="mf-music-words">
          <h2 id="mf-music-credits">Credits</h2>
          <ul className="mf-music-list">
            {track.credits.map((credit, index) => (
              <li key={`${credit.role}-${credit.name}-${String(index)}`}>
                {credit.role}: {credit.name}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {track.lyrics ? (
        <section aria-labelledby="mf-music-lyrics" className="mf-music-words">
          <h2 id="mf-music-lyrics">Lyrics</h2>
          {track.lyrics.split("\n\n").map((verse, index) => (
            <p key={index} className="mf-music-lyrics">
              {verse}
            </p>
          ))}
        </section>
      ) : null}
    </article>
  );
}
