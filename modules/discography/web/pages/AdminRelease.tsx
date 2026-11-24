// The album editor, /admin/music/:id (`dev plans/contracts/discography.md` §2; the
// canvas's AdminAlbum board): the front and back covers from the media library,
// the release's words, its tracks in order (Upload tracks, Add SoundCloud link,
// moved up and down), its credits and streaming links, and Publish beside them. A
// live release's save changes the site at once. A save someone else got to first
// asks field by field (the kit's SaveConflict), and leaving with changes asks
// first. Tracks being made into stream files are read again until they're done.
import { useQueryClient } from "@tanstack/react-query";
import { useId, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  Accordion,
  AdminPage,
  ApiProblem,
  Attention,
  Button,
  Card,
  Dialog,
  Field,
  Input,
  LoadError,
  Pill,
  SaveBar,
  SaveConflict,
  Select,
  Switch,
  TextArea,
  UnsavedDialog,
  buttonClass,
  failureWords,
  useToast,
  useUnsavedGuard,
  when,
  type SettingsConflict,
} from "@/kernel";
import { ImagePicker, Picture } from "@/modules/media/public";

import {
  ACCEPT,
  KIND_WORDS,
  MAX_ARTIST,
  MAX_LINE,
  MAX_SLUG,
  MAX_TITLE,
  MAX_URL,
  PUBLIC_RELEASES,
  RELEASE,
  RELEASES,
  ROLES,
  STATUS_TONE,
  STATUS_WORDS,
  TRACKS,
  api,
  audioWords,
  clock,
  pathOf,
  trackState,
  uploadTrack,
  useApiQuery,
  type FullRelease,
  type Kind,
  type MusicCover,
} from "../api";
import {
  RELEASE_LABELS,
  changed,
  conflictOf,
  merged,
  mineOf,
  movedTrack,
  rebased,
  releaseBody,
  releaseFormOf,
  releaseProblems,
  said,
  type ReleaseForm,
} from "../editing";
import { Credits } from "../components/Credits";
import "../music.css";

type FormField = keyof ReleaseForm;

/** Read again every few seconds while a track's stream file is being made. */
const WHILE_PROCESSING = 3000;

export default function AdminRelease() {
  const { id = "" } = useParams();
  const read = useApiQuery(
    "get",
    RELEASE,
    { params: { path: { release_id: id } } },
    { refetchInterval: (query) => (query.state.data?.tracks.some((track) => track.audio.state === "processing") ? WHILE_PROCESSING : false) },
  );
  if (read.error && !read.data) {
    const gone = read.error instanceof ApiProblem && read.error.status === 404;
    return (
      <AdminPage page="Release" title="Edit release">
        <LoadError what={gone ? "That release" : "The release"} error={read.error} onRetry={() => void read.refetch()} />
      </AdminPage>
    );
  }
  if (!read.data) return null;
  // A read again that failed keeps the editor and what's typed in it, and says so (CodeRabbit on #145).
  const stale = read.error ? <LoadError what="The release" error={read.error} onRetry={() => void read.refetch()} inline /> : null;
  return <Editor key={read.data.id} server={read.data} notice={stale} />;
}

/** A field's errors from a refused save: the server's, by its name or as `body.<name>`. */
function fieldErrors(problem: unknown, ...fields: string[]): string | undefined {
  if (!(problem instanceof ApiProblem)) return undefined;
  const found = fields.flatMap((field) => [...(problem.errors[field] ?? []), ...(problem.errors[`body.${field}`] ?? [])]);
  return found.length ? found.join(" ") : undefined;
}

/** `form`'s track order with the server's tracks: kept where they're still there, new ones last. */
function withTracks(form: ReleaseForm, server: FullRelease): ReleaseForm {
  const ids = server.tracks.map((track) => track.id);
  const kept = form.track_ids.filter((each) => ids.includes(each));
  return { ...form, track_ids: [...kept, ...ids.filter((each) => !kept.includes(each))] };
}

function coverOf(image: { id: string; url: string; srcset: string; width: number; height: number; alt?: string | null; decorative: boolean }): MusicCover {
  return { id: image.id, url: image.url, srcset: image.srcset, width: image.width, height: image.height, alt: image.decorative ? "" : (image.alt ?? null), decorative: image.decorative };
}

function Editor({ server, notice }: { server: FullRelease; notice: ReactNode }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const roles = useApiQuery("get", ROLES);
  const [saved, setSaved] = useState<FullRelease>(server);
  const base = useMemo(() => releaseFormOf(saved), [saved]);
  const [form, setForm] = useState<ReleaseForm>(base);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<unknown>(null);
  const [checked, setChecked] = useState<Partial<Record<FormField, string>>>({});
  const [conflict, setConflict] = useState<{ said: SettingsConflict; theirs: FullRelease; mine: ReleaseForm; fields: FormField[] } | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [at, setAt] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [picking, setPicking] = useState<"cover" | "back_cover" | null>(null);
  const [linking, setLinking] = useState(false);
  const [uploadProblems, setUploadProblems] = useState<string[]>([]);
  const files = useRef<HTMLInputElement>(null);
  const saveButton = useRef<HTMLButtonElement>(null);
  const atId = useId();
  const formNow = useRef(form);
  useLayoutEffect(() => {
    formNow.current = form;
  });

  // The server's tracks, read again (a track added, removed or processed): the
  // fields keep what the person changed, and the order theirs, new tracks last.
  // Someone else's save of the release isn't taken in here: the next Save asks.
  const [seen, setSeen] = useState(server);
  if (seen !== server) {
    setSeen(server);
    if (server.version === saved.version) {
      setSaved(server);
      setForm((now) => withTracks(rebased(now, releaseFormOf(saved), releaseFormOf(server)), server));
    }
  }

  // While a save waits, the form is held against what it sent: a field typed back
  // to what's saved since then is still a change (CodeRabbit on #145).
  const [sending, setSending] = useState<ReleaseForm | null>(null);
  const edits = changed(form, base);
  const dirty = edits.length > 0 || (sending !== null && changed(form, sending).length > 0);
  const live = saved.status === "published";
  const titles = useMemo(
    () => new Map([...(conflict?.theirs.tracks ?? []), ...saved.tracks, ...server.tracks].map((track) => [track.id, track.title])),
    [conflict, saved.tracks, server.tracks],
  );
  const roleNames = useMemo(() => new Map((roles.data?.items ?? []).map((each) => [each.id, each.name])), [roles.data]);
  const tracks = useMemo(() => {
    const byId = new Map(server.tracks.map((track) => [track.id, track]));
    return form.track_ids.flatMap((each) => byId.get(each) ?? []);
  }, [form.track_ids, server.tracks]);
  const silent = tracks.find((track) => !track.audio.plays_from && track.audio.state !== "processing");

  function set<Name extends FormField>(field: Name, value: ReleaseForm[Name]) {
    setForm((now) => ({ ...now, [field]: value }));
  }

  function remember(release: FullRelease) {
    queryClient.setQueryData(["get", RELEASE, { params: { path: { release_id: release.id } } }], release);
    void queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
    void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
    void queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_RELEASES] });
  }

  async function reread() {
    await queryClient.invalidateQueries({ queryKey: ["get", RELEASE, { params: { path: { release_id: saved.id } } }] });
    void queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
    void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
  }

  /** Saves what changed; the release as the server now has it, or throws why not. */
  async function save(from: ReleaseForm = form, onto: FullRelease = saved): Promise<FullRelease> {
    const found = releaseProblems(from);
    setChecked(found);
    if (Object.keys(found).length > 0) throw new Error("Some fields need fixing first: they're marked.");
    setRefused(null);
    const sent = changed(from, releaseFormOf(onto));
    if (sent.length === 0) return onto;
    try {
      setSending(from);
      const answered = await api
        .PATCH(RELEASE, {
          params: { path: { release_id: onto.id } },
          body: { version: onto.version, ...releaseBody(from, sent) },
        })
        .finally(() => {
          setSending(null);
        });
      const { data } = answered;
      if (!data) throw new Error("The site answered without the release.");
      remember(data);
      setSaved(data);
      setForm((now) => withTracks(rebased(now, from, releaseFormOf(data)), data));
      setConflict(null);
      return data;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "discography.changed" && error.extra.release) {
        const theirs = error.extra.release as FullRelease;
        // The form as it is when the answer lands, typing since the save went included.
        const latest = formNow.current;
        const fields = mineOf(latest, releaseFormOf(onto), from);
        const now = releaseFormOf(theirs);
        const conflicting = conflictOf(error.detail, releaseFormOf(onto), latest, now, theirs, fields);
        if (conflicting.conflicts.length === 0) {
          const next = withTracks(merged(latest, now, new Set(), fields), theirs);
          setSaved(theirs);
          setForm(next);
          return save(next, theirs);
        }
        setConflict({ said: conflicting, theirs, mine: latest, fields });
      }
      throw error;
    }
  }

  async function act(what: () => Promise<unknown>, done?: string) {
    setBusy(true);
    try {
      await what();
      if (done) toast({ tone: "success", text: done });
    } catch (error) {
      setRefused(error);
      if (!(error instanceof ApiProblem && error.code === "discography.changed")) {
        toast({ tone: "danger", text: error instanceof Error ? failureWords(error) : "That didn't go through. Try again." });
      }
    } finally {
      setBusy(false);
    }
  }

  /** Takes in the release a Publish or Unpublish answered with: someone else's save since asks, as a Save would. */
  function adopt(answer: FullRelease, held: FullRelease) {
    if (answer.version === held.version) {
      setSaved(answer);
      return;
    }
    const before = releaseFormOf(held);
    const latest = formNow.current;
    const fields = changed(latest, before);
    const now = releaseFormOf(answer);
    const conflicting = conflictOf("Someone saved this release since you opened it. Here is how it reads now.", before, latest, now, answer, fields);
    if (conflicting.conflicts.length > 0) {
      setSaved({ ...held, status: answer.status, publish_at: answer.publish_at, published_at: answer.published_at });
      setConflict({ said: conflicting, theirs: answer, mine: latest, fields });
      return;
    }
    setForm((mine) => withTracks(merged(mine, now, new Set(), fields), answer));
    setSaved(answer);
  }

  async function publish(schedule: boolean) {
    if (schedule && !at) throw new Error("Choose its release day.");
    const release = dirty ? await save() : saved;
    const { data } = await api.POST("/api/discography/admin/releases/{release_id}/publish", {
      params: { path: { release_id: release.id } },
      body: schedule ? { at: new Date(at).toISOString() } : {},
    });
    if (!data) throw new Error("The site answered without the release.");
    remember(data);
    adopt(data, release);
    setScheduling(false);
  }

  async function unpublish() {
    const { data } = await api.POST("/api/discography/admin/releases/{release_id}/unpublish", { params: { path: { release_id: saved.id } } });
    if (!data) throw new Error("The site answered without the release.");
    remember(data);
    adopt(data, saved);
  }

  async function remove() {
    await api.DELETE(RELEASE, { params: { path: { release_id: saved.id } } });
    queryClient.removeQueries({ queryKey: ["get", RELEASE, { params: { path: { release_id: saved.id } } }] });
    await queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
    void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
    void queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_RELEASES] });
    guard.release();
    toast({ tone: "success", text: `${saved.title} is deleted.` });
    void navigate("/admin/music");
  }

  /** Each file a track, one after another; a file too large isn't sent at all. */
  async function upload(list: FileList | null) {
    const picked = Array.from(list ?? []);
    if (files.current) files.current.value = "";
    if (picked.length === 0) return;
    setBusy(true);
    const problems: string[] = [];
    let taken = 0;
    for (const file of picked) {
      try {
        await uploadTrack(saved.id, file);
        taken += 1;
      } catch (error) {
        problems.push(error instanceof ApiProblem ? `${file.name}: ${error.detail}` : error instanceof Error ? error.message : `${file.name} didn't go up.`);
      }
    }
    setUploadProblems(problems);
    setBusy(false);
    if (taken) {
      toast({ tone: "success", text: taken === 1 ? "The track is up. Its stream file is being made." : `${String(taken)} tracks are up. Their stream files are being made.` });
      await reread();
    }
  }

  /** By id: the form's order may hold a track the server no longer shows (CodeRabbit on #145). */
  function move(id: string, by: -1 | 1) {
    set(
      "track_ids",
      movedTrack(
        form.track_ids,
        tracks.map((track) => track.id),
        id,
        by,
      ),
    );
  }

  const guard = useUnsavedGuard(dirty, async () => {
    try {
      await save();
      return null;
    } catch (error) {
      return error instanceof Error ? failureWords(error) : "";
    }
  });

  const saveLabel = live ? "Update" : "Save";
  const savedWords = live ? "The release is updated on the site." : "Saved.";
  const errorOf = (field: FormField, ...also: string[]) => checked[field] ?? fieldErrors(refused, field, ...also);
  const count = server.tracks.length === 1 ? "1 track" : `${String(server.tracks.length)} tracks`;
  const lead =
    saved.status === "scheduled"
      ? `${KIND_WORDS[saved.kind]}, ${count}. Out on ${when(saved.publish_at)}: saving changes what goes live then.`
      : live
        ? `${KIND_WORDS[saved.kind]}${saved.year ? `, ${String(saved.year)}` : ""}. ${count}. Live: saving changes its page at once.`
        : `${KIND_WORDS[saved.kind]}, ${count}. A draft: nothing is on the site until you publish it.`;
  const roleChoices = roles.data?.items ?? [];

  return (
    <AdminPage
      page={saved.title}
      crumb={saved.title}
      title={saved.title}
      lead={lead}
      actions={
        <>
          {live ? (
            <a className={buttonClass({})} href={pathOf(saved.slug)} target="_blank" rel="noreferrer">
              View on the site
            </a>
          ) : null}
          <Button ref={saveButton} variant="primary" disabled={busy || !dirty} onClick={() => void act(() => save(), savedWords)}>
            {saveLabel}
          </Button>
        </>
      }
    >
      {notice}
      {conflict ? (
        <SaveConflict
          conflict={conflict.said}
          labels={RELEASE_LABELS}
          saving={busy}
          returnTo={saveButton}
          format={(field, value) =>
            // An order by its tracks' titles, as the list names them (CodeRabbit on #145).
            field === "track_ids" && Array.isArray(value) ? (value as string[]).map((each) => titles.get(each) ?? each).join(", ") || "None" : said(value, roleNames)
          }
          onResolve={(choices) => {
            const keep = new Set(Object.entries(choices).filter(([, choice]) => choice === "theirs").map(([field]) => field));
            const next = withTracks(merged(conflict.mine, releaseFormOf(conflict.theirs), keep, conflict.fields), conflict.theirs);
            setSaved(conflict.theirs);
            setForm(next);
            void act(async () => {
              await save(next, conflict.theirs);
              setConflict(null);
            }, "Saved.");
          }}
          onCancel={() => {
            setConflict(null);
          }}
        />
      ) : null}
      {silent ? (
        <Attention
          tone="warning"
          what={`${silent.title} can't play`}
          why="It has no audio file or link, so it's hidden from the release's page and the site's players skip it."
          action={{ label: "Add audio", to: `/admin/music/tracks?track=${silent.id}` }}
        />
      ) : null}
      <div className="mf-music-editor">
        <div className="mf-music-main">
          <Card title="Release" level={2}>
            <div className="mf-music-stack">
              <div className="mf-music-covers">
                {(["cover", "back_cover"] as const).map((which) => {
                  const image = form[which];
                  const label = which === "cover" ? "Front cover" : "Back cover";
                  return (
                    <div key={which} className="mf-music-cover">
                      <span className="mf-music-cover-label">{label}</span>
                      {image ? <Picture image={image} sizes="240px" className="mf-music-thumb" /> : <p className="mf-music-hint">None yet.</p>}
                      {fieldErrors(refused, `${which}_id`) ? <p className="mf-music-error">{fieldErrors(refused, `${which}_id`)}</p> : null}
                      <div className="mf-music-row">
                        <Button
                          size="small"
                          onClick={() => {
                            setPicking(which);
                          }}
                        >
                          {image ? `Replace ${label.toLowerCase()}` : `Choose a ${label.toLowerCase()}`}
                        </Button>
                        {image ? (
                          <Button
                            size="small"
                            onClick={() => {
                              set(which, null);
                            }}
                          >
                            Remove
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mf-music-fields mf-music-fields--two">
                <Field label="Title" error={errorOf("title")}>
                  <Input
                    value={form.title}
                    maxLength={MAX_TITLE}
                    onChange={(event) => {
                      set("title", event.target.value);
                    }}
                  />
                </Field>
                <Field label="Kind" error={errorOf("kind")}>
                  <Select
                    value={form.kind}
                    onChange={(event) => {
                      set("kind", event.target.value as Kind);
                    }}
                  >
                    {(Object.keys(KIND_WORDS) as Kind[]).map((kind) => (
                      <option key={kind} value={kind}>
                        {KIND_WORDS[kind]}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Year" error={errorOf("year")}>
                  <Input
                    value={form.year}
                    inputMode="numeric"
                    maxLength={4}
                    onChange={(event) => {
                      set("year", event.target.value);
                    }}
                  />
                </Field>
                <Field label="Artist line" hint="Who it's by, as the page says it." error={errorOf("artist_line")}>
                  <Input
                    value={form.artist_line}
                    maxLength={MAX_ARTIST}
                    onChange={(event) => {
                      set("artist_line", event.target.value);
                    }}
                  />
                </Field>
              </div>
              <Field label="Credit" hint="One line under the artist: “Produced by Vibrant Mindz.”" error={errorOf("credit_line")}>
                <Input
                  value={form.credit_line}
                  maxLength={MAX_LINE}
                  onChange={(event) => {
                    set("credit_line", event.target.value);
                  }}
                />
              </Field>
              <Field label="Summary" hint="A line for its card and when it's shared." error={errorOf("summary")}>
                <TextArea
                  value={form.summary}
                  maxLength={MAX_LINE}
                  rows={2}
                  onChange={(event) => {
                    set("summary", event.target.value);
                  }}
                />
              </Field>
              <Field
                label="Address"
                error={errorOf("slug")}
                hint={live && form.slug !== saved.slug ? `${pathOf(saved.slug)} will send visitors here.` : `The release is at ${pathOf(form.slug || "…")}.`}
              >
                <Input
                  value={form.slug}
                  maxLength={MAX_SLUG}
                  spellCheck={false}
                  autoCapitalize="none"
                  onChange={(event) => {
                    set("slug", event.target.value);
                  }}
                />
              </Field>
              {saved.moves.length > 0 ? <p className="mf-music-hint">Also reached from {saved.moves.join(", ")}.</p> : null}
              <Switch
                label="Tracklist to come"
                hint="Its page says the tracklist is still to come, under the tracks it has so far."
                checked={form.tracklist_to_come}
                onChange={(on) => {
                  set("tracklist_to_come", on);
                }}
              />
            </div>
          </Card>
          <Card
            title="Tracks"
            level={2}
            description="Each track plays from an uploaded file or a SoundCloud link; an upload gets a stream file and a waveform made from it."
            actions={
              <div className="mf-music-row">
                <Button
                  size="small"
                  icon="link"
                  disabled={busy}
                  onClick={() => {
                    setLinking(true);
                  }}
                >
                  Add SoundCloud link
                </Button>
                <Button
                  size="small"
                  icon="upload"
                  disabled={busy}
                  onClick={() => {
                    files.current?.click();
                  }}
                >
                  Upload tracks
                </Button>
                <input
                  ref={files}
                  className="mf-music-file"
                  type="file"
                  multiple
                  accept={ACCEPT}
                  tabIndex={-1}
                  aria-label="Upload tracks"
                  onChange={(event) => void upload(event.target.files)}
                />
              </div>
            }
          >
            <div className="mf-music-stack">
              <p className="mf-music-hint">WAV, AIFF, FLAC, Ogg or MP3, up to 60 MB a file. Over that, export it as FLAC: it keeps every bit at about half the size.</p>
              {uploadProblems.length ? (
                <ul className="mf-music-list" aria-label="Files that didn't go up">
                  {uploadProblems.map((each) => (
                    <li key={each} className="mf-music-error">
                      {each}
                    </li>
                  ))}
                </ul>
              ) : null}
              {errorOf("track_ids") ? <p className="mf-music-error">{errorOf("track_ids")}</p> : null}
              {tracks.length ? (
                <ol className="mf-music-list" aria-label="Tracks, in the order they play">
                  {tracks.map((track, index) => {
                    const state = trackState(track.audio);
                    return (
                      <li key={track.id} className="mf-music-release">
                        <span className="mf-music-order">
                          <Button
                            size="small"
                            icon="chevron-down"
                            className="mf-music-up"
                            aria-label={`Move ${track.title} up`}
                            disabled={index === 0}
                            onClick={() => {
                              move(track.id, -1);
                            }}
                          />
                          <Button
                            size="small"
                            icon="chevron-down"
                            aria-label={`Move ${track.title} down`}
                            disabled={index === tracks.length - 1}
                            onClick={() => {
                              move(track.id, 1);
                            }}
                          />
                        </span>
                        <span className="mf-music-release-words">
                          <span>
                            <span className="mf-music-number">{String(index + 1).padStart(2, "0")}</span>{" "}
                            <Link to={`/admin/music/tracks?track=${track.id}`}>{track.title}</Link>
                          </span>
                          <span className="mf-music-sub">
                            {audioWords(track.audio)} · {clock(track.audio.duration_ms)}
                          </span>
                        </span>
                        <span className="mf-music-release-actions">
                          <Pill tone={state.tone}>{state.label}</Pill>
                        </span>
                      </li>
                    );
                  })}
                </ol>
              ) : (
                <p className="mf-music-hint">No tracks yet. Upload them, or add a SoundCloud link.</p>
              )}
            </div>
          </Card>
          <Accordion id="mf-music-credits" title="Credits" level={2} meta="Who made it: a role and a name a row. A track's own credits are on the Tracks board.">
            <Credits rows={form.credits} roles={roleChoices} error={errorOf("credits")} onChange={(rows) => {
              set("credits", rows);
            }} />
          </Accordion>
          <Accordion id="mf-music-links" title="Streaming links" level={2} meta="Where else it plays: Spotify, Apple Music, YouTube, Amazon, SoundCloud, Bandcamp, Tidal or Deezer, one each.">
            <Links rows={form.links} error={errorOf("links")} onChange={(rows) => {
              set("links", rows);
            }} />
          </Accordion>
        </div>
        <div className="mf-music-side">
          <Card title="Publish" level={2}>
            <div className="mf-music-stack">
              <p className="mf-music-row">
                <Pill tone={STATUS_TONE[saved.status]}>{STATUS_WORDS[saved.status]}</Pill>
                {saved.status === "scheduled" ? <span>{when(saved.publish_at)}</span> : null}
                {live && saved.published_at ? <span>since {when(saved.published_at)}</span> : null}
              </p>
              {!live ? (
                <fieldset className="mf-music-stack">
                  <legend>When</legend>
                  <label>
                    <input
                      type="radio"
                      name="when"
                      checked={!scheduling}
                      onChange={() => {
                        setScheduling(false);
                      }}
                    />{" "}
                    Publish now
                  </label>
                  <label>
                    <input
                      type="radio"
                      name="when"
                      checked={scheduling}
                      onChange={() => {
                        setScheduling(true);
                      }}
                    />{" "}
                    On its release day
                  </label>
                  {scheduling ? (
                    <Field label="Goes live at" id={atId}>
                      <Input
                        type="datetime-local"
                        value={at}
                        onChange={(event) => {
                          setAt(event.target.value);
                        }}
                      />
                    </Field>
                  ) : null}
                </fieldset>
              ) : null}
              <div className="mf-music-row">
                {!live ? (
                  <Button variant="primary" disabled={busy} onClick={() => void act(() => publish(scheduling), scheduling ? "The release is scheduled." : "The release is live.")}>
                    {scheduling ? "Schedule" : "Publish"}
                  </Button>
                ) : null}
                {saved.status !== "draft" ? (
                  <Button disabled={busy} onClick={() => void act(unpublish, live ? "The release is a draft again." : "Its release day is cleared.")}>
                    {live ? "Unpublish" : "Back to a draft"}
                  </Button>
                ) : null}
              </div>
              <Button
                size="small"
                disabled={busy}
                onClick={() => {
                  setDeleting(true);
                }}
              >
                Delete release
              </Button>
            </div>
          </Card>
        </div>
      </div>
      {dirty ? (
        <SaveBar
          changes={Math.max(edits.length, 1)}
          saving={busy}
          saveLabel={saveLabel}
          onSave={() => void act(() => save(), savedWords)}
          onDiscard={() => {
            setForm(withTracks(releaseFormOf(saved), server));
            setChecked({});
            setRefused(null);
          }}
        />
      ) : null}
      <UnsavedDialog guard={guard} what="This release" />
      {picking ? (
        <ImagePicker
          title={picking === "cover" ? "Choose a front cover" : "Choose a back cover"}
          onPick={(image) => {
            set(picking, coverOf(image));
            setPicking(null);
          }}
          onClose={() => {
            setPicking(null);
          }}
        />
      ) : null}
      {linking ? (
        <NewLinkedTrack
          releaseId={saved.id}
          onClose={() => {
            setLinking(false);
          }}
          onMade={async () => {
            setLinking(false);
            toast({ tone: "success", text: "The track is added." });
            await reread();
          }}
        />
      ) : null}
      {deleting ? (
        <Dialog
          title={`Delete ${saved.title}?`}
          onClose={() => {
            setDeleting(false);
          }}
        >
          <p className="mf-dialog-lead">
            {live ? `${pathOf(saved.slug)} stops working at once` : "It's gone for good"}, with its {count} and their uploaded files. This can't be undone.
          </p>
          <div className="mf-dialog-actions">
            <Button
              onClick={() => {
                setDeleting(false);
              }}
            >
              Keep it
            </Button>
            <Button variant="primary" disabled={busy} onClick={() => void act(remove)}>
              Delete release
            </Button>
          </div>
        </Dialog>
      ) : null}
    </AdminPage>
  );
}

/** The release's streaming links: an address a row, its platform read from it. */
function Links({ rows, error, onChange }: { rows: readonly string[]; error?: string | undefined; onChange: (rows: string[]) => void }) {
  return (
    <div className="mf-music-stack">
      {rows.length ? (
        <ul className="mf-music-list">
          {rows.map((row, index) => (
            <li key={index} className="mf-music-credit">
              <Field label={`Link ${String(index + 1)}`}>
                <Input
                  type="url"
                  value={row}
                  maxLength={MAX_URL}
                  spellCheck={false}
                  onChange={(event) => {
                    onChange(rows.map((each, at) => (at === index ? event.target.value : each)));
                  }}
                />
              </Field>
              <span />
              <Button
                size="small"
                icon="close"
                aria-label={`Remove link ${String(index + 1)}`}
                onClick={() => {
                  onChange(rows.filter((_, at) => at !== index));
                }}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mf-music-hint">No streaming links yet.</p>
      )}
      {error ? <p className="mf-music-error">{error}</p> : null}
      <div>
        <Button
          size="small"
          icon="plus"
          onClick={() => {
            onChange([...rows, ""]);
          }}
        >
          Add a link
        </Button>
      </div>
    </div>
  );
}

function NewLinkedTrack({ releaseId, onClose, onMade }: { releaseId: string; onClose: () => void; onMade: () => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [link, setLink] = useState("");
  const [refused, setRefused] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function add() {
    setBusy(true);
    setRefused(null);
    try {
      await api.POST("/api/discography/admin/releases/{release_id}/tracks", {
        params: { path: { release_id: releaseId } },
        body: { title: title.trim(), soundcloud_url: link.trim() },
      });
      await onMade();
    } catch (error) {
      setRefused(error);
    } finally {
      setBusy(false);
    }
  }
  const linkError = fieldErrors(refused, "soundcloud_url");
  const titleError = fieldErrors(refused, "title");
  const other = refused && !linkError && !titleError ? (refused instanceof Error ? failureWords(refused) : "That didn't go through. Try again.") : null;
  return (
    <Dialog title="Add a SoundCloud link" onClose={onClose}>
      <form
        className="mf-music-stack"
        onSubmit={(event) => {
          event.preventDefault();
          void add();
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
        <Field label="SoundCloud link" hint="A track's or a playlist's page: a playlist plays as one track." error={linkError}>
          <Input
            type="url"
            value={link}
            maxLength={MAX_URL}
            required
            spellCheck={false}
            onChange={(event) => {
              setLink(event.target.value);
            }}
          />
        </Field>
        {other ? <p className="mf-music-error">{other}</p> : null}
        <div className="mf-dialog-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !title.trim() || !link.trim()}>
            Add the track
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
