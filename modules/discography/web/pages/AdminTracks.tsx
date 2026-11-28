// Every track on every release, /admin/music/tracks (`dev plans/contracts/
// discography.md` §2; the canvas's AdminTracks board): Search tracks, the four
// filters, the table, and the picked track's panel beside it, where its audio is
// uploaded, replaced, removed or tried again, and its title, address, Explicit,
// SoundCloud link, lyrics and credits are saved. `?track=` picks one and `?show=`
// a filter, so the album editor and the dashboard can send someone straight there.
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { useSearchParams } from "react-router";

import {
  AdminPage,
  ApiProblem,
  Attention,
  Button,
  Card,
  Chip,
  Dialog,
  Field,
  Input,
  LoadError,
  Pill,
  QuietLink,
  SaveConflict,
  SearchBox,
  Switch,
  Table,
  TextArea,
  UnsavedDialog,
  failureWords,
  useToast,
  useUnsavedGuard,
  type Column,
  type SettingsConflict,
  type UnsavedGuard,
} from "@/kernel";

import {
  ACCEPT,
  MAX_LYRICS,
  MAX_PASTE,
  MAX_SLUG,
  MAX_TITLE,
  MAX_URL,
  PUBLIC_RELEASES,
  RELEASE,
  RELEASES,
  ROLES,
  TRACK,
  TRACKS,
  api,
  audioWords,
  pathOf,
  replaceAudio,
  trackState,
  useApiQuery,
  type AdminTrack,
  type FullTrack,
} from "../api";
import { Credits } from "../components/Credits";
import { TRACK_LABELS, changed, conflictOf, merged, mineOf, rebased, said, trackBody, trackFormOf, trackProblems, type TrackForm } from "../editing";
import "../music.css";

type Show = "all" | "cant_play" | "no_lyrics" | "no_credits";
type FormField = keyof TrackForm;

const FILTERS: readonly { value: Show; label: string }[] = [
  { value: "all", label: "All" },
  { value: "cant_play", label: "Can't play" },
  { value: "no_lyrics", label: "No lyrics" },
  { value: "no_credits", label: "No credits" },
];
const SHOWS = new Set<string>(FILTERS.map((each) => each.value));
const WHILE_PROCESSING = 3000;

function fieldErrors(problem: unknown, ...fields: string[]): string | undefined {
  if (!(problem instanceof ApiProblem)) return undefined;
  const found = fields.flatMap((field) => [...(problem.errors[field] ?? []), ...(problem.errors[`body.${field}`] ?? [])]);
  return found.length ? found.join(" ") : undefined;
}

export default function AdminTracks() {
  const [search, setSearch] = useSearchParams();
  const picked = search.get("track") ?? "";
  const asked = search.get("show") ?? "all";
  const show: Show = SHOWS.has(asked) ? (asked as Show) : "all";
  const [q, setQ] = useState("");
  const words = useDeferredValue(q.trim());
  const query = { ...(words ? { q: words } : {}), ...(show === "all" ? {} : { show }) };
  const listed = useInfiniteQuery({
    queryKey: ["get", TRACKS, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET(TRACKS, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The site answered without the tracks.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    // A row still making its stream file is read again until it's done, panel open or not (CodeRabbit on #145).
    refetchInterval: (query) => (query.state.data?.pages.some((page) => page.items.some((each) => each.audio.state === "processing")) ? WHILE_PROCESSING : false),
  });
  const first = listed.data?.pages[0];
  const tracks = listed.data?.pages.flatMap((page) => page.items) ?? [];
  const silent = tracks.find((track) => !track.audio.plays_from && track.audio.state !== "processing");
  // Whether the open panel holds changes, once a save it's waiting on is answered,
  // and the track picked while it did: another pick asks first, as a move to
  // another page does (Codex and CodeRabbit on #145).
  const settle = useRef<(() => Promise<boolean>) | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  function go(id: string) {
    setPending(null);
    const next = new URLSearchParams(search);
    if (id) next.set("track", id);
    else next.delete("track");
    setSearch(next, { replace: true });
  }

  async function pick(id: string) {
    const changes = id !== picked && settle.current ? await settle.current() : false;
    if (changes) setPending(id);
    else go(id);
  }

  function filter(value: Show) {
    const next = new URLSearchParams(search);
    if (value === "all") next.delete("show");
    else next.set("show", value);
    setSearch(next, { replace: true });
  }

  const columns: readonly Column<AdminTrack>[] = [
    {
      key: "track",
      header: "Track",
      cell: (track) => (
        <span>
          <button
            type="button"
            className="mf-music-pick"
            aria-pressed={track.id === picked}
            onClick={() => {
              void pick(track.id);
            }}
          >
            {track.title}
          </button>
          <span className="mf-music-sub">{track.release_title}</span>
        </span>
      ),
    },
    { key: "audio", header: "Audio", cell: (track) => audioWords(track.audio) },
    { key: "lyrics", header: "Lyrics", cell: (track) => (track.has_lyrics ? "Added" : "None yet") },
    { key: "credits", header: "Credits", cell: (track) => (track.credit_count === 0 ? "None yet" : track.credit_count === 1 ? "1 credit" : `${String(track.credit_count)} credits`) },
    {
      key: "status",
      header: "Status",
      cell: (track) => {
        const state = trackState(track.audio);
        return <Pill tone={state.tone}>{state.label}</Pill>;
      },
    },
  ];

  return (
    <AdminPage page="Tracks" title="Tracks" lead="Every track on every release. Pick one to change its audio, lyrics or credits.">
      {silent && silent.id !== picked ? (
        <div className="mf-music-note">
          <Attention
            tone="danger"
            what={`${silent.title} can't play`}
            why="It has no audio file or link, so it's hidden from its release's page and the site's players skip it."
            action={{ label: "Add audio", to: `/admin/music/tracks?track=${silent.id}` }}
          />
        </div>
      ) : null}
      <div className="mf-music-board mf-music-board--panel mf-music-board--tracks">
        <div className="mf-music-main">
          <div className="mf-music-row">
            <SearchBox
              label="Search tracks"
              value={q}
              onChange={(event) => {
                setQ(event.target.value);
              }}
            />
            <div className="mf-music-row" role="group" aria-label="Show">
              {FILTERS.map((each) => (
                <Chip
                  key={each.value}
                  pressed={show === each.value}
                  onPressedChange={() => {
                    filter(each.value);
                  }}
                >
                  {each.label}
                </Chip>
              ))}
            </div>
          </div>
          {listed.error ? (
            <LoadError what="The tracks" error={listed.error} onRetry={() => void listed.refetch()} />
          ) : listed.data ? (
            <>
              <Card flush>
                <Table
                  caption="Tracks"
                  captionHidden
                  columns={columns}
                  rows={tracks}
                  rowKey={(track) => track.id}
                  rowHeader="track"
                  empty={words || show !== "all" ? "No tracks match. Try other words, or show all." : "No tracks yet. Upload them from a release's editor."}
                />
              </Card>
              {listed.hasNextPage ? (
                <div>
                  <Button disabled={listed.isFetchingNextPage} onClick={() => void listed.fetchNextPage()}>
                    More tracks
                  </Button>
                </div>
              ) : null}
              {first ? (
                <p className="mf-music-hint">
                  {first.total === 1 ? "1 track" : `${String(first.total)} tracks`} on {first.releases === 1 ? "1 release" : `${String(first.releases)} releases`}.
                </p>
              ) : null}
            </>
          ) : null}
        </div>
        <div className="mf-music-side">
          {picked ? (
            <TrackPanel
              key={picked}
              id={picked}
              settle={settle}
              asked={pending !== null}
              onGo={() => {
                go(pending ?? "");
              }}
              onStay={() => {
                setPending(null);
              }}
              onGone={() => {
                go("");
              }}
            />
          ) : (
            <Card title="A track" level={2}>
              <p className="mf-music-hint">Pick a track to change its audio, lyrics or credits.</p>
            </Card>
          )}
        </div>
      </div>
    </AdminPage>
  );
}

type Switching = {
  /** Set to the panel's question for the board's next pick: once any save it's waiting on is answered, does it hold changes? */
  settle: RefObject<(() => Promise<boolean>) | null>;
  /** Another track was picked while it did: the panel asks. */
  asked: boolean;
  onGo: () => void;
  onStay: () => void;
};

function TrackPanel({ id, onGone, ...switching }: { id: string; onGone: () => void } & Switching) {
  const read = useApiQuery(
    "get",
    TRACK,
    { params: { path: { track_id: id } } },
    { refetchInterval: (query) => (query.state.data?.audio.state === "processing" ? WHILE_PROCESSING : false) },
  );
  if (read.error && !read.data) {
    const gone = read.error instanceof ApiProblem && read.error.status === 404;
    return (
      <Card title="A track" level={2}>
        <LoadError what={gone ? "That track" : "The track"} error={read.error} onRetry={() => void read.refetch()} inline />
      </Card>
    );
  }
  if (!read.data) return null;
  // A read again that failed keeps the editor and what's typed in it, and says so (CodeRabbit on #145).
  const stale = read.error ? <LoadError what="The track" error={read.error} onRetry={() => void read.refetch()} inline /> : null;
  return <TrackEditor server={read.data} notice={stale} onGone={onGone} {...switching} />;
}

function TrackEditor({ server, notice, onGone, settle: settleRef, asked, onGo, onStay }: { server: FullTrack; notice: ReactNode; onGone: () => void } & Switching) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const roles = useApiQuery("get", ROLES);
  const [saved, setSaved] = useState<FullTrack>(server);
  const base = useMemo(() => trackFormOf(saved), [saved]);
  const [form, setForm] = useState<TrackForm>(base);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<unknown>(null);
  const [checked, setChecked] = useState<Partial<Record<FormField, string>>>({});
  const [conflict, setConflict] = useState<{ said: SettingsConflict; theirs: FullTrack; mine: TrackForm; fields: FormField[] } | null>(null);
  const [deleting, setDeleting] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const saveButton = useRef<HTMLButtonElement>(null);
  const formNow = useRef(form);
  // The track as saved, kept at once by each answer, and the save still waiting:
  // a save or a pick waits for it, then reads what it answered (CodeRabbit on #145).
  const savedNow = useRef(saved);
  const inflight = useRef<Promise<FullTrack> | null>(null);
  useLayoutEffect(() => {
    formNow.current = form;
    savedNow.current = saved;
  });
  const roleNames = useMemo(() => new Map((roles.data?.items ?? []).map((each) => [each.id, each.name])), [roles.data]);

  // The track read again while its stream file is made: the same version, its
  // audio moved on. A field the person left follows it, the length a link's
  // track shows among them (CodeRabbit on #145). Only a new read counts: a draw
  // with the read from before an answer the panel took in never undoes it.
  const [seen, setSeen] = useState(server);
  if (seen !== server) {
    setSeen(server);
    if (server.version === saved.version && server.audio !== saved.audio) {
      setSaved(server);
      setForm((now) => rebased(now, trackFormOf(saved), trackFormOf(server)));
    }
  }
  // Its stream file made: the Tracks table reads it again, as it says "Making" until then.
  const state = server.audio.state;
  const was = useRef(state);
  useEffect(() => {
    if (was.current === "processing" && state !== "processing") void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
    was.current = state;
  }, [state, queryClient]);

  // While a save waits, the form is held against what it sent, as that's what
  // the track will be: a field typed back to what was saved before is a change,
  // and nothing typed since is none (CodeRabbit on #145).
  const [sending, setSending] = useState<TrackForm | null>(null);
  const edits = changed(form, base);
  const dirty = sending !== null ? changed(form, sending).length > 0 : edits.length > 0;
  const audio = (server.version === saved.version ? server : saved).audio;
  const [switchSaving, setSwitchSaving] = useState(false);
  const [switchError, setSwitchError] = useState("");
  const switchTurn = useRef(0);

  /** For the board's pick: once a save that's waiting is answered, are there changes past it? */
  async function settleChanges(): Promise<boolean> {
    const waiting = inflight.current;
    if (waiting) {
      try {
        await waiting;
      } catch {
        return true; // refused: what was sent is still the person's
      }
    }
    return changed(formNow.current, trackFormOf(savedNow.current)).length > 0;
  }
  useLayoutEffect(() => {
    settleRef.current = settleChanges;
  });
  useEffect(
    () => () => {
      settleRef.current = null;
    },
    [settleRef],
  );

  /** The track as saved now: kept at once, for a save or a pick that reads it before the next draw. */
  function keep(track: FullTrack) {
    savedNow.current = track;
    setSaved(track);
  }
  const errorOf = (field: FormField, ...also: string[]) => checked[field] ?? fieldErrors(refused, field, ...also);

  function set<Name extends FormField>(field: Name, value: TrackForm[Name]) {
    setForm((now) => ({ ...now, [field]: value }));
  }

  function remember(track: FullTrack) {
    queryClient.setQueryData(["get", TRACK, { params: { path: { track_id: track.id } } }], track);
    void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
    void queryClient.invalidateQueries({ queryKey: ["get", RELEASE, { params: { path: { release_id: track.release_id } } }] });
    void queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
    void queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_RELEASES] });
  }

  /**
   * A track an audio change answered with: the fields keep what the person
   * changed, and a field someone else saved differently since asks, as a save
   * would, rather than being saved over next (CodeRabbit on #145). The length
   * moves with the audio itself, so it never asks.
   */
  function adopt(track: FullTrack) {
    remember(track);
    const held = savedNow.current;
    const before = trackFormOf(held);
    const latest = formNow.current;
    const now = trackFormOf(track);
    const fields = changed(latest, before).filter((field) => field !== "length");
    const crossed = conflictOf("Someone saved this track while its audio changed. Here is how it reads now.", before, latest, now, track, fields);
    setForm(rebased(latest, before, now));
    if (crossed.conflicts.length === 0) {
      keep(track);
      return;
    }
    // Only the new audio is taken in: the fields stay at the version they were
    // read at, the SoundCloud link among them though it rides in `audio`, so a
    // save that passes the choice by, from the form or after Back to the form,
    // is refused and asks again (CodeRabbit on #145).
    const link = { soundcloud_url: held.audio.soundcloud_url, soundcloud_kind: held.audio.soundcloud_kind, bandcamp_url: held.audio.bandcamp_url };
    keep({ ...held, audio: { ...track.audio, ...link }, peaks: track.peaks });
    setConflict({ said: crossed, theirs: track, mine: latest, fields });
  }

  /**
   * Saves the form as it is now onto the track as saved now, once a save that's
   * still waiting is answered: a second save never reads what the first one
   * replaces (CodeRabbit on #145). The conflict dialog's choice passes both.
   */
  async function save(from?: TrackForm, onto?: FullTrack): Promise<FullTrack> {
    const waiting = inflight.current;
    if (waiting) await waiting.catch(() => undefined);
    const run = send(from ?? formNow.current, onto ?? savedNow.current);
    inflight.current = run;
    try {
      return await run;
    } finally {
      if (inflight.current === run) inflight.current = null;
    }
  }

  async function send(from: TrackForm, onto: FullTrack): Promise<FullTrack> {
    const found = trackProblems(from);
    setChecked(found);
    if (Object.keys(found).length > 0) throw new Error("Some fields need fixing first: they're marked.");
    setRefused(null);
    const sent = changed(from, trackFormOf(onto));
    if (sent.length === 0) return onto;
    try {
      setSending(from);
      const answered = await api.PATCH(TRACK, { params: { path: { track_id: onto.id } }, body: { version: onto.version, ...trackBody(from, sent) } }).finally(() => {
        setSending(null);
      });
      const { data } = answered;
      if (!data) throw new Error("The site answered without the track.");
      remember(data);
      keep(data);
      setForm((now) => rebased(now, from, trackFormOf(data)));
      setConflict(null);
      return data;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "discography.changed" && error.extra.track) {
        const theirs = error.extra.track as FullTrack;
        const latest = formNow.current;
        const fields = mineOf(latest, trackFormOf(onto), from);
        const now = trackFormOf(theirs);
        const conflicting = conflictOf(error.detail, trackFormOf(onto), latest, now, theirs, fields);
        if (conflicting.conflicts.length === 0) {
          const next = merged(latest, now, new Set(), fields);
          keep(theirs);
          setForm(next);
          return send(next, theirs);
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

  async function upload(list: FileList | null) {
    const picked = list?.[0];
    if (file.current) file.current.value = "";
    if (!picked) return;
    await act(async () => {
      adopt(await replaceAudio(saved.id, picked));
    }, "The file is up. Its stream file is being made.");
  }

  async function removeAudio() {
    const { data } = await api.DELETE("/api/discography/admin/tracks/{track_id}/audio", { params: { path: { track_id: saved.id } } });
    if (!data) throw new Error("The site answered without the track.");
    adopt(data);
  }

  async function retry() {
    const { data } = await api.POST("/api/discography/admin/tracks/{track_id}/audio/retry", { params: { path: { track_id: saved.id } } });
    if (!data) throw new Error("The site answered without the track.");
    adopt(data);
  }

  async function remove() {
    await api.DELETE(TRACK, { params: { path: { track_id: saved.id } } });
    queryClient.removeQueries({ queryKey: ["get", TRACK, { params: { path: { track_id: saved.id } } }] });
    void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
    void queryClient.invalidateQueries({ queryKey: ["get", RELEASE, { params: { path: { release_id: saved.release_id } } }] });
    void queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
    toast({ tone: "success", text: `${saved.title} is deleted.` });
    onGone();
  }

  /** Saves for a leave: null once saved, or why it isn't. */
  async function saveToLeave(): Promise<string | null> {
    try {
      await save();
      return null;
    } catch (error) {
      return error instanceof Error ? failureWords(error) : "";
    }
  }

  const guard = useUnsavedGuard(dirty, saveToLeave);
  const switching: UnsavedGuard = {
    asking: asked,
    saving: switchSaving,
    error: switchError,
    saveAndLeave: () => {
      // A Stay while the save waits keeps the person here: the save's answer
      // doesn't move them on (CodeRabbit on #145, as the kit's guard counts turns).
      const turn = (switchTurn.current += 1);
      setSwitchSaving(true);
      setSwitchError("");
      void saveToLeave().then((why) => {
        if (turn !== switchTurn.current) return;
        setSwitchSaving(false);
        if (why === null) onGo();
        else setSwitchError(why);
      });
    },
    leave: onGo,
    stay: () => {
      switchTurn.current += 1;
      setSwitchSaving(false);
      setSwitchError("");
      onStay();
    },
    release: () => undefined,
  };

  const hasUpload = Boolean(audio.master_name);
  return (
    <Card title={saved.title} level={2} description={`Track ${String(saved.number)} of ${saved.release_title}`}>
      {notice}
      {conflict ? (
        <SaveConflict
          conflict={conflict.said}
          labels={TRACK_LABELS}
          saving={busy}
          returnTo={saveButton}
          format={(_field, value) => said(value, roleNames)}
          onResolve={(choices) => {
            const taken = new Set(Object.entries(choices).filter(([, choice]) => choice === "theirs").map(([field]) => field));
            const next = merged(conflict.mine, trackFormOf(conflict.theirs), taken, conflict.fields);
            keep(conflict.theirs);
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
      <div className="mf-music-stack">
        <section aria-label="Audio" className="mf-music-stack">
          <p className="mf-music-row">
            <strong>Audio</strong>
            <span>{audioWords(audio)}</span>
          </p>
          {audio.master_name ? <p className="mf-music-hint">Uploaded: {audio.master_name}</p> : null}
          {audio.state === "failed" && audio.error_words ? <p className="mf-music-error">{audio.error_words}</p> : null}
          {audio.stream_url ? (
            <audio controls preload="none" src={audio.stream_url} aria-label={`Hear ${saved.title}`}>
              <a href={audio.stream_url}>Hear {saved.title}</a>
            </audio>
          ) : null}
          <div className="mf-music-row">
            <Button
              size="small"
              icon="upload"
              disabled={busy}
              onClick={() => {
                file.current?.click();
              }}
            >
              {hasUpload ? "Replace the file" : "Upload a file"}
            </Button>
            <input ref={file} className="mf-music-file" type="file" accept={ACCEPT} tabIndex={-1} aria-label="Upload a file" onChange={(event) => void upload(event.target.files)} />
            {hasUpload ? (
              <Button size="small" disabled={busy} onClick={() => void act(removeAudio, "The upload is removed.")}>
                Remove the upload
              </Button>
            ) : null}
            {audio.state === "failed" ? (
              <Button size="small" disabled={busy} onClick={() => void act(retry, "Trying it again.")}>
                Try again
              </Button>
            ) : null}
          </div>
          <p className="mf-music-hint">An upload gets a stream file and a waveform made from it. The original file is never public. Up to 60 MB: over that, export it as FLAC.</p>
        </section>
        <Field label="Title" error={errorOf("title")}>
          <Input
            value={form.title}
            maxLength={MAX_TITLE}
            onChange={(event) => {
              set("title", event.target.value);
            }}
          />
        </Field>
        <Field label="Address" hint={`On its release's page at ${pathOf("…", form.slug || "…")}.`} error={errorOf("slug")}>
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
        <Switch
          label="Explicit"
          hint="It shows the Parental Advisory label while the site does."
          checked={form.explicit}
          onChange={(on) => {
            set("explicit", on);
          }}
        />
        <Field label="SoundCloud link" hint="A track's or a playlist's page. An upload plays first once its stream file is ready." error={errorOf("soundcloud_url")}>
          <Input
            type="url"
            value={form.soundcloud_url}
            maxLength={MAX_URL}
            spellCheck={false}
            onChange={(event) => {
              set("soundcloud_url", event.target.value);
            }}
          />
        </Field>
        <Field
          label="Bandcamp player"
          hint="Paste the embed code from its Bandcamp page (Share, then Embed). It plays in Bandcamp's own player when the track has no upload or SoundCloud link."
          error={errorOf("bandcamp_url")}
        >
          <Input
            value={form.bandcamp_url}
            maxLength={MAX_PASTE}
            spellCheck={false}
            autoComplete="off"
            onChange={(event) => {
              set("bandcamp_url", event.target.value);
            }}
          />
        </Field>
        {audio.state !== "ready" ? (
          <Field label="Length" hint="For a track that plays from its link: 3:42. An upload's is read from its file." error={errorOf("length", "duration_ms")}>
            <Input
              value={form.length}
              inputMode="numeric"
              maxLength={8}
              onChange={(event) => {
                set("length", event.target.value);
              }}
            />
          </Field>
        ) : null}
        <Field label="Lyrics" hint="A blank line between verses. They show on the track's page while the site shows lyrics." error={errorOf("lyrics")}>
          <TextArea
            value={form.lyrics}
            maxLength={MAX_LYRICS}
            rows={8}
            onChange={(event) => {
              set("lyrics", event.target.value);
            }}
          />
        </Field>
        <fieldset className="mf-music-stack mf-music-group">
          <legend className="mf-field-label">Credits</legend>
          <Credits rows={form.credits} roles={roles.data?.items ?? []} error={errorOf("credits")} onChange={(rows) => {
              set("credits", rows);
            }} />
        </fieldset>
        <div className="mf-music-row">
          {/* Small, as the panel's other buttons (0.1.3, VM Website's P4). */}
          <Button ref={saveButton} variant="primary" size="small" disabled={busy || !dirty} onClick={() => void act(() => save(), "Saved.")}>
            Save
          </Button>
          {dirty ? (
            <Button
              size="small"
              disabled={busy}
              onClick={() => {
                setForm(trackFormOf(saved));
                setChecked({});
                setRefused(null);
              }}
            >
              Discard
            </Button>
          ) : null}
          {/* The kit's quiet link, as the board draws it (0.1.4, VM Website's K11). */}
          <QuietLink to={`/admin/music/${saved.release_id}`}>Open the release</QuietLink>
        </div>
        <div>
          <Button
            size="small"
            disabled={busy}
            onClick={() => {
              setDeleting(true);
            }}
          >
            Delete track
          </Button>
        </div>
      </div>
      <UnsavedDialog guard={guard} what={saved.title} />
      <UnsavedDialog guard={switching} what={saved.title} />
      {deleting ? (
        <Dialog
          title={`Delete ${saved.title}?`}
          onClose={() => {
            setDeleting(false);
          }}
        >
          <p className="mf-dialog-lead">It goes from {saved.release_title}, with its uploaded file. This can't be undone.</p>
          <div className="mf-dialog-actions">
            <Button
              onClick={() => {
                setDeleting(false);
              }}
            >
              Keep it
            </Button>
            <Button variant="primary" disabled={busy} onClick={() => void act(remove)}>
              Delete track
            </Button>
          </div>
        </Dialog>
      ) : null}
    </Card>
  );
}
