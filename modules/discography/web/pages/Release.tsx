// A live release at /music/:release (`dev plans/contracts/discography.md` §2; the
// site's Release board): its front cover (and back, behind Front and Back), kind,
// year and Parental Advisory, the title, artist and credit lines, where else it
// plays, then the tracks that play, and the credits. With audio-player on (0.1.1),
// Play album and each row's play start the release's tracks, the row that plays
// shows the three bars, and the Player docks after the footer; with it off, each
// track plays in the browser's own player or as a SoundCloud link. A track in
// Bandcamp's own player shows it behind a Listen either way (0.1.5). The words are
// the server copy's own. An address the release left moves on; any other is the
// 404 page.
import { useMemo, useState } from "react";
import { Link, Navigate, useLocation, useParams } from "react-router";

import { ApiProblem, LoadError, NotFound, Seo, useModuleEnabled } from "@/kernel";
import { Picture } from "@/modules/media/public";

import { KIND_WORDS, clock } from "../api";
import { BandcampPlayer } from "../components/BandcampPlayer";
import { PlayAlbum, PlayTrack, ReleaseDock } from "../components/Listen";
import { Plays } from "../components/Plays";
import "../music.css";
import { SOURCE, bandcampPlayer, playerQueue } from "../player";
import { isMoved, useRelease } from "../reads";

export default function Release() {
  const { release: slug = "" } = useParams();
  const { search, hash } = useLocation();
  const found = useRelease(slug);
  const [back, setBack] = useState(false);
  // Off only when the site says so: discography is never on without it (its requirement).
  const player = useModuleEnabled("audio-player") !== false;
  const queue = useMemo(() => (found.data && !isMoved(found.data) ? playerQueue(found.data) : []), [found.data]);
  if (found.isPending) return null;
  if (found.error) {
    if (found.error instanceof ApiProblem && found.error.status === 404) return <NotFound />;
    return <LoadError what="This release" error={found.error} onRetry={() => void found.refetch()} />;
  }
  const release = found.data;
  if (isMoved(release)) return <Navigate to={`${release.moved}${search}${hash}`} replace />;
  const shown = back && release.back_cover ? release.back_cover : release.cover;
  const description = release.summary || release.credit_line || (release.artist_line ? `${KIND_WORDS[release.kind]} by ${release.artist_line}.` : `${KIND_WORDS[release.kind]}.`);
  const count = release.tracks.length === 1 ? "1 track" : `${String(release.tracks.length)} tracks`;
  return (
    <article className="mf-music">
      <Seo
        title={release.title}
        description={description}
        path={release.path}
        published={release.published_at}
        modified={release.updated_at}
        {...(release.cover ? { image: release.cover.url } : {})}
      />
      <section className="mf-music-hero">
        <div className="mf-music-stack">
          {shown ? (
            <Picture image={shown} sizes="(min-width: 48rem) 40vw, 100vw" loading="eager" className="mf-music-art" />
          ) : (
            <div className="mf-music-art-plain" aria-hidden="true" />
          )}
          {release.cover && release.back_cover ? (
            <div className="mf-music-row" role="group" aria-label="Album art">
              <button
                type="button"
                className="mf-music-pick"
                aria-pressed={!back}
                onClick={() => {
                  setBack(false);
                }}
              >
                Front
              </button>
              <button
                type="button"
                className="mf-music-pick"
                aria-pressed={back}
                onClick={() => {
                  setBack(true);
                }}
              >
                Back
              </button>
            </div>
          ) : null}
        </div>
        <div className="mf-music-words">
          <nav className="mf-music-crumbs" aria-label="Breadcrumb">
            <Link to="/music">Music</Link> / <span aria-current="page">{release.title}</span>
          </nav>
          <p className="mf-music-meta">
            <span>{KIND_WORDS[release.kind]}</span>
            {release.year ? <span>{release.year}</span> : null}
            {release.explicit ? <span className="mf-music-advisory">Parental Advisory</span> : null}
          </p>
          <h1>{release.title}</h1>
          {release.artist_line ? <p>{release.artist_line}</p> : null}
          {release.credit_line ? <p>{release.credit_line}</p> : null}
          {release.summary ? <p>{release.summary}</p> : null}
          {release.links.length ? (
            <section aria-labelledby="mf-music-on" className="mf-music-words">
              <h2 id="mf-music-on">Listen on</h2>
              <ul className="mf-music-links">
                {release.links.map((link) => (
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
      </section>
      <section aria-labelledby="mf-music-tracks" className="mf-music-words">
        <h2 id="mf-music-tracks">Tracks</h2>
        {release.tracks.length ? (
          <>
            <p className="mf-music-lead">{release.tracklist_to_come ? `${count} for now. The full tracklist is to come.` : count}</p>
            {player && queue.length ? <PlayAlbum queue={queue} /> : null}
            <ol className="mf-music-tracklist">
              {release.tracks.map((track) => {
                const number = String(track.number).padStart(2, "0");
                const bandcamp = bandcampPlayer(track);
                // Its place in the queue, which leaves Bandcamp's tracks out.
                const index = queue.findIndex((item) => item.key === `${SOURCE}:${track.id}`);
                return (
                  <li key={track.slug} className="mf-music-track">
                    <div className="mf-music-track-head">
                      {player && index >= 0 ? <PlayTrack queue={queue} index={index} label={`${number} ${track.title}`} /> : null}
                      <span className="mf-music-number">{number}</span>
                      <Link to={track.path}>{track.title}</Link>
                      {track.explicit ? <span className="mf-music-advisory">Explicit</span> : null}
                      <span className="mf-music-number">{track.duration_ms ? clock(track.duration_ms) : ""}</span>
                    </div>
                    {bandcamp ? (
                      <BandcampPlayer link={bandcamp} label={`${number} ${track.title}`} />
                    ) : player ? null : (
                      <Plays track={track} label={track.title} />
                    )}
                  </li>
                );
              })}
            </ol>
            {player ? <ReleaseDock queue={queue} /> : null}
          </>
        ) : (
          <p>The tracklist is to come.</p>
        )}
      </section>
      {release.credits.length ? (
        <section aria-labelledby="mf-music-credits" className="mf-music-words">
          <h2 id="mf-music-credits">Credits</h2>
          <ul className="mf-music-list">
            {release.credits.map((credit, index) => (
              <li key={`${credit.role}-${credit.name}-${String(index)}`}>
                {credit.role}: {credit.name}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
