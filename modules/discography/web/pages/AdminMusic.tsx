// The releases, /admin/music (`dev plans/contracts/discography.md` §2; the canvas's
// AdminMusic board): what needs doing first (a live track that can't play, a
// tracklist still to come), then each release with its cover, its line and its
// badges, Preview and Edit; New release; and the Music settings beside them for
// whoever may change the site's settings.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import {
  AdminPage,
  ApiProblem,
  Attention,
  Button,
  Card,
  Dialog,
  Field,
  Input,
  LinkButton,
  LoadError,
  Pill,
  SaveConflict,
  Select,
  Switch,
  buttonClass,
  failureWords,
  useSession,
  useSettings,
  useToast,
} from "@/kernel";
import { Picture } from "@/modules/media/public";

import { KIND_WORDS, MAX_TITLE, RELEASES, SETTINGS, STATUS_TONE, STATUS_WORDS, api, pathOf, releaseLine, useApiQuery, type AdminRelease, type Kind } from "../api";
import "../music.css";

/** MP3's standard rates the stream may be made at, from 128 to 320 kbps. */
const BITRATES = [128, 160, 192, 224, 256, 320] as const;
const SETTING_LABELS = { show_lyrics: "Show lyrics on release pages", show_explicit_badge: "Parental Advisory label", stream_bitrate_kbps: "Stream quality" };

function Release({ release }: { release: AdminRelease }) {
  const live = release.status === "published";
  return (
    <li className="mf-music-release">
      {release.cover ? (
        <Picture image={release.cover} sizes="88px" className="mf-music-thumb" />
      ) : (
        <div className="mf-music-thumb-plain" aria-hidden="true">
          ♪
        </div>
      )}
      <div className="mf-music-release-words">
        <span className="mf-music-release-title">{release.title}</span>
        {release.artist_line ? <span>{release.artist_line}</span> : null}
        <span className="mf-music-release-line">{releaseLine(release)}</span>
        <span className="mf-music-row">
          <Pill tone={STATUS_TONE[release.status]}>{STATUS_WORDS[release.status]}</Pill>
          {release.tracklist_to_come ? <Pill tone="warning">Tracklist to come</Pill> : null}
          {release.unplayable ? <Pill tone="danger">{release.unplayable === 1 ? "1 track can't play" : `${String(release.unplayable)} tracks can't play`}</Pill> : null}
        </span>
      </div>
      <div className="mf-music-row mf-music-row--end mf-music-release-actions">
        {live ? (
          <a className={buttonClass({ size: "small" })} href={pathOf(release.slug)} target="_blank" rel="noreferrer" aria-label={`Preview ${release.title} on the site`}>
            Preview
          </a>
        ) : null}
        <LinkButton size="small" to={`/admin/music/${release.id}`} aria-label={`Edit ${release.title}`}>
          Edit
        </LinkButton>
      </div>
    </li>
  );
}

/** The two notes the board leads with: a live release's track that can't play, else a tracklist still to come. */
function Notes({ releases }: { releases: readonly AdminRelease[] }) {
  const silent = releases.find((each) => each.status === "published" && each.unplayable > 0) ?? releases.find((each) => each.unplayable > 0);
  if (silent) {
    return (
      <Attention
        tone="danger"
        what={silent.unplayable === 1 ? `A track on ${silent.title} can't play` : `${String(silent.unplayable)} tracks on ${silent.title} can't play`}
        why="Without an audio file or a link, a track is hidden from the release's page and the site's players skip it."
        action={{ label: "Add audio", to: `/admin/music/tracks?show=cant_play` }}
      />
    );
  }
  const waiting = releases.find((each) => each.tracklist_to_come);
  if (!waiting) return null;
  return (
    <Attention
      tone="warning"
      what={`${waiting.title}'s tracklist isn't in yet`}
      why="Its page says the tracklist is to come, under the tracks it has so far, until its tracks are added."
      action={{ label: "Add tracks", to: `/admin/music/${waiting.id}` }}
    />
  );
}

function NewRelease({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<Kind>("album");
  const [refused, setRefused] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function make() {
    setBusy(true);
    setRefused(null);
    try {
      const { data } = await api.POST(RELEASES, { body: { title: title.trim(), kind } });
      if (!data) throw new Error("The site answered without the release.");
      void queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
      void navigate(`/admin/music/${data.id}`);
    } catch (error) {
      setRefused(error);
      setBusy(false);
    }
  }
  const titleError = refused instanceof ApiProblem ? [...(refused.errors.title ?? []), ...(refused.errors["body.title"] ?? [])].join(" ") || undefined : undefined;
  const other = refused && !titleError ? (refused instanceof Error ? failureWords(refused) : "That didn't go through. Try again.") : null;
  // Kept open while the draft is made: its answer opens the draft (CodeRabbit on #145).
  const close = busy ? () => undefined : onClose;
  return (
    <Dialog title="New release" onClose={close}>
      <form
        className="mf-music-stack"
        onSubmit={(event) => {
          event.preventDefault();
          void make();
        }}
      >
        <Field label="Title" error={titleError}>
          <Input
            value={title}
            maxLength={MAX_TITLE}
            required
            onChange={(event) => {
              setTitle(event.target.value);
            }}
          />
        </Field>
        <Field label="Kind">
          <Select
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as Kind);
            }}
          >
            {(Object.keys(KIND_WORDS) as Kind[]).map((each) => (
              <option key={each} value={each}>
                {KIND_WORDS[each]}
              </option>
            ))}
          </Select>
        </Field>
        <p className="mf-music-hint">It starts as a draft: nothing is on the site until you publish it.</p>
        {other ? <p className="mf-music-error">{other}</p> : null}
        <div className="mf-dialog-actions">
          <Button type="button" disabled={busy} onClick={close}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !title.trim()}>
            Make the draft
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** The Music settings: what plays first is fixed (the upload, then the link); these three change. */
function MusicSettings() {
  const form = useSettings("discography");
  const toast = useToast();
  if (form.read === "failed") return <LoadError what="The music settings" error={form.problem} onRetry={form.retry} inline />;
  if (form.read === "loading") return <p className="mf-music-hint">Loading…</p>;
  const bitrate = typeof form.values.stream_bitrate_kbps === "number" ? form.values.stream_bitrate_kbps : 256;
  return (
    <div className="mf-music-stack">
      <p className="mf-music-hint">Tracks play from their uploaded file, or from their SoundCloud link where they have none, else in Bandcamp's own player.</p>
      {/* The kit's switch rows, which touch with a rule between (0.1.3, VM Website's P2). */}
      <div className="mf-switch-rows">
        <Switch
          label="Show lyrics on release pages"
          hint="Only for tracks that have them."
          checked={form.values.show_lyrics !== false}
          onChange={(on) => {
            form.set("show_lyrics", on);
          }}
        />
        <Switch
          label="Parental Advisory label"
          hint="On releases and tracks marked explicit."
          checked={form.values.show_explicit_badge !== false}
          onChange={(on) => {
            form.set("show_explicit_badge", on);
          }}
        />
      </div>
      <Field label="Stream quality" hint="New uploads' stream files are made at this. MP3, a constant rate." error={form.errors.stream_bitrate_kbps}>
        <Select
          value={String(bitrate)}
          onChange={(event) => {
            form.set("stream_bitrate_kbps", Number(event.target.value));
          }}
        >
          {BITRATES.map((each) => (
            <option key={each} value={each}>
              {each} kbps
            </option>
          ))}
        </Select>
      </Field>
      {form.conflict ? (
        <SaveConflict
          conflict={form.conflict}
          labels={SETTING_LABELS}
          saving={form.saving}
          onResolve={(choices) => void form.resolve(choices)}
          onCancel={form.dropConflict}
        />
      ) : null}
      {form.dirty ? (
        <div className="mf-music-row">
          <Button
            variant="primary"
            size="small"
            disabled={form.saving}
            onClick={() =>
              void form.save().then((outcome) => {
                if (outcome.status === "saved") toast({ tone: "success", text: "The music settings are saved." });
              })
            }
          >
            Save settings
          </Button>
          <Button size="small" disabled={form.saving} onClick={form.discard}>
            Discard
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default function AdminMusic() {
  const session = useSession();
  const listed = useApiQuery("get", RELEASES);
  const [making, setMaking] = useState(false);
  const releases = listed.data?.items ?? [];
  const maySettle = session.status === "signed-in" && session.can(SETTINGS);
  return (
    <AdminPage
      page="Albums"
      title="Music"
      lead="Albums, EPs and singles. Each one gets a page on the site once it's live."
      actions={
        <Button
          variant="primary"
          icon="plus"
          onClick={() => {
            setMaking(true);
          }}
        >
          New release
        </Button>
      }
    >
      <div className="mf-music-board mf-music-board--panel">
        <div className="mf-music-main">
          {listed.error ? (
            <LoadError what="The releases" error={listed.error} onRetry={() => void listed.refetch()} />
          ) : listed.data ? (
            <>
              <Notes releases={releases} />
              {releases.length ? (
                <Card title="Releases" level={2}>
                  <ul className="mf-music-list">
                    {releases.map((release) => (
                      <Release key={release.id} release={release} />
                    ))}
                  </ul>
                </Card>
              ) : (
                <Card title="Releases" level={2}>
                  <p className="mf-music-hint">No releases yet. New release makes the first, as a draft.</p>
                </Card>
              )}
            </>
          ) : null}
        </div>
        <div className="mf-music-side">
          <Card title="Music settings" level={2}>
            {maySettle ? <MusicSettings /> : <p className="mf-music-hint">An admin changes these: lyrics on release pages, the Parental Advisory label and the stream's quality.</p>}
          </Card>
        </div>
      </div>
      {making ? (
        <NewRelease
          onClose={() => {
            setMaking(false);
          }}
        />
      ) : null}
    </AdminPage>
  );
}
