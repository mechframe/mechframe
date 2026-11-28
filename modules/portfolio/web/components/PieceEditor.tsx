// A piece's editor, the board's panel beside the grid (`dev plans/contracts/portfolio.md`
// §2; VM Website's AdminPortfolio board): the picture with Change picture, Title,
// Discipline, By, Year, About the piece, Video and Address, then Save, Publish
// or Unpublish (with Schedule), View on the site and Delete. A save someone else
// got to first asks which to keep (the kit's SaveConflict); leaving with changes
// asks first (blog's editor is the pattern).
import { useQueryClient } from "@tanstack/react-query";
import { useId, useLayoutEffect, useRef, useState } from "react";

import {
  ApiProblem,
  Button,
  Dialog,
  Field,
  Input,
  SaveConflict,
  Select,
  TextArea,
  UnsavedDialog,
  buttonClass,
  failureWords,
  useToast,
  useUnsavedGuard,
  when,
  type SettingsConflict,
} from "@/kernel";
import { ImagePicker, Picture as Shown, type Image } from "@/modules/media/public";

import {
  ARTISTS,
  DISCIPLINES,
  LIST,
  ONE,
  PUBLIC_DISCIPLINES,
  PUBLIC_LIST,
  api,
  pathOf,
  useApiQuery,
  type AdminDiscipline,
  type AdminPiece,
  type Picture,
} from "../api";
import {
  LABELS,
  MAX_ABOUT,
  MAX_SLUG,
  MAX_TITLE,
  blank,
  body,
  changed,
  conflictOf,
  created,
  formOf,
  merged,
  problems,
  said,
  slugFor,
  type Form,
  type FormField,
} from "../editing";

export type PieceEditorProps = {
  /** The piece to edit; null for a new one. */
  piece: AdminPiece | null;
  /** A new piece's picture, chosen before the editor opened. */
  picked: Picture | null;
  disciplines: readonly AdminDiscipline[];
  /** Who's signed in: a new piece is theirs unless they may credit others. */
  me: { id: string; name: string };
  /** Holds `portfolio.piece.manage`: may credit the piece to anyone who may add pieces. */
  manages: boolean;
  onSaved: (piece: AdminPiece) => void;
  onDeleted: () => void;
};

type Conflict = { said: SettingsConflict; theirs: AdminPiece; mine: Form; fields: FormField[] };

/** media's image as a piece's picture holds it. */
export function pictureOf(image: Image): Picture {
  return { id: image.id, url: image.url, srcset: image.srcset, width: image.width, height: image.height, alt: image.alt, decorative: image.decorative };
}

function fieldErrors(problem: unknown, field: FormField): string | undefined {
  if (!(problem instanceof ApiProblem)) return undefined;
  const sent = field === "picture" ? "image_id" : field;
  const found = problem.errors[sent];
  return found?.[0];
}

export function PieceEditor({ piece, picked, disciplines, me, manages, onSaved, onDeleted }: PieceEditorProps) {
  const id = useId();
  const queryClient = useQueryClient();
  const toast = useToast();
  const artists = useApiQuery("get", ARTISTS, {}, { enabled: manages });
  const [saved, setSaved] = useState<AdminPiece | null>(piece);
  const [form, setForm] = useState<Form>(() => (piece ? formOf(piece) : blank(picked, me.id)));
  // The fields as they stand now, for an answer that lands after more typing.
  const formNow = useRef(form);
  useLayoutEffect(() => {
    formNow.current = form;
  });
  const [slugTyped, setSlugTyped] = useState(false);
  const [checked, setChecked] = useState<Partial<Record<FormField, string>>>({});
  const [refused, setRefused] = useState<unknown>(null);
  const [conflict, setConflict] = useState<Conflict | null>(null);
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false);
  const [scheduling, setScheduling] = useState(false);
  const [at, setAt] = useState("");
  const [deleting, setDeleting] = useState(false);
  const saveButton = useRef<HTMLButtonElement>(null);

  const dirty = saved === null || changed(form, formOf(saved)).length > 0;
  const live = saved?.status === "published";
  const names = new Map<string, string>([
    ...disciplines.map((each) => [each.slug, each.label] as const),
    ...(artists.data?.items ?? []).map((each) => [each.id, each.name] as const),
    [me.id, me.name],
  ]);

  function set<K extends FormField>(field: K, value: Form[K]) {
    setForm((now) => {
      const next = { ...now, [field]: value };
      if (field === "title" && saved === null && !slugTyped) next.slug = slugFor(value as string);
      return next;
    });
  }

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["get", LIST] }),
      queryClient.invalidateQueries({ queryKey: ["get", DISCIPLINES] }),
      queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_LIST] }),
      queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_DISCIPLINES] }),
    ]);
  }

  /**
   * Takes in a piece the server answered with: what was typed that `sent` didn't
   * hold stays as typed. A save's `sent` is what it sent; a Publish's or an
   * Unpublish's is the piece as saved before it, so edits not yet saved survive
   * it, still unsaved (Codex on #171).
   */
  function took(data: AdminPiece, sent: Form) {
    queryClient.setQueryData(["get", ONE, { params: { path: { piece_id: data.id } } }], data);
    setSaved(data);
    // What was typed after the save went stays as typed (blog's `rebased`).
    setForm((now) => {
      const answer = formOf(data);
      for (const field of changed(now, sent)) (answer as Record<FormField, unknown>)[field] = now[field];
      return answer;
    });
    setConflict(null);
    onSaved(data);
    void refresh();
  }

  async function save(from: Form = form, onto: AdminPiece | null = saved, carried: readonly FormField[] = []): Promise<AdminPiece> {
    const found = problems(from, onto === null);
    setChecked(found);
    if (Object.keys(found).length > 0) throw new Error("Some fields need fixing first: they're marked.");
    setRefused(null);
    if (onto === null) {
      const { data } = await api.POST(LIST, { body: created(from, { credits: manages, slugTyped }) });
      if (!data) throw new Error("The site answered without the piece.");
      guard.release();
      took(data, from);
      return data;
    }
    const sent = changed(from, formOf(onto));
    if (sent.length === 0) return onto;
    try {
      const { data } = await api.PATCH(ONE, { params: { path: { piece_id: onto.id } }, body: { version: onto.version, ...body(from, sent) } });
      if (!data) throw new Error("The site answered without the piece.");
      took(data, from);
      return data;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "portfolio.changed") {
        const theirs = error.extra.piece as AdminPiece;
        const latest = formNow.current;
        const fields = [...new Set([...carried, ...changed(latest, formOf(onto))])];
        const conflicting = conflictOf(error.detail, formOf(onto), latest, theirs, fields);
        if (conflicting.conflicts.length === 0) {
          // They changed only what you didn't: theirs, with yours on top, saved again.
          const next = merged(formOf(onto), latest, theirs, new Set(), fields);
          setSaved(theirs);
          setForm(next);
          formNow.current = next;
          return save(next, theirs, fields);
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
      if (!(error instanceof ApiProblem && error.code === "portfolio.changed")) {
        toast({ tone: "danger", text: error instanceof Error ? failureWords(error) : "That didn't go through. Try again." });
      }
    } finally {
      setBusy(false);
    }
  }

  async function publish(schedule: boolean) {
    if (schedule && !at) throw new Error("Choose when it goes live.");
    const current = dirty ? await save() : saved;
    const { data } = await api.POST("/api/portfolio/admin/pieces/{piece_id}/publish", {
      params: { path: { piece_id: current.id } },
      body: schedule ? { at: new Date(at).toISOString() } : {},
    });
    if (!data) throw new Error("The site answered without the piece.");
    took(data, formOf(current));
    setScheduling(false);
  }

  async function unpublish() {
    if (!saved) return;
    const before = formOf(saved);
    const { data } = await api.POST("/api/portfolio/admin/pieces/{piece_id}/unpublish", { params: { path: { piece_id: saved.id } } });
    if (!data) throw new Error("The site answered without the piece.");
    took(data, before);
  }

  async function remove() {
    if (!saved) return;
    await api.DELETE(ONE, { params: { path: { piece_id: saved.id } } });
    queryClient.removeQueries({ queryKey: ["get", ONE, { params: { path: { piece_id: saved.id } } }] });
    await refresh();
    guard.release();
    setDeleting(false);
    toast({ tone: "success", text: `${saved.title} is deleted.` });
    onDeleted();
  }

  const guard = useUnsavedGuard(dirty, async () => {
    try {
      await save();
      return null;
    } catch (error) {
      return error instanceof Error ? failureWords(error) : "";
    }
  });

  const errorOf = (field: FormField) => checked[field] ?? fieldErrors(refused, field);
  const state =
    saved === null
      ? "A new piece. Nothing shows on the Art page until you publish it."
      : saved.status === "scheduled"
        ? `Scheduled for ${when(saved.publish_at)}. Saving changes what goes live then.`
        : live
          ? "Live on the Art page. Saving changes it there at once."
          : "A draft. Nothing shows on the Art page until you publish it.";
  const artistChoices = artists.data?.items ?? [];

  return (
    <form
      className="mf-portfolio-editor"
      aria-labelledby={`${id}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        void act(() => save(), live ? "The piece is updated on the Art page." : "Saved.");
      }}
    >
      <h2 id={`${id}-title`} className="mf-portfolio-editor-title">
        {saved?.title ?? "New piece"}
      </h2>
      <p className="mf-portfolio-hint">{state}</p>
      {conflict ? (
        <SaveConflict
          conflict={conflict.said}
          labels={LABELS}
          saving={busy}
          returnTo={saveButton}
          format={(field, value) => said(field as FormField, value, names)}
          onResolve={(choices) => {
            const keep = new Set(Object.entries(choices).filter(([, choice]) => choice === "theirs").map(([field]) => field));
            const next = merged(formOf(saved ?? conflict.theirs), conflict.mine, conflict.theirs, keep, conflict.fields);
            const carried = conflict.fields.filter((field) => !keep.has(field));
            setSaved(conflict.theirs);
            setForm(next);
            formNow.current = next;
            void act(() => save(next, conflict.theirs, carried), "Saved.");
          }}
          onCancel={() => {
            setConflict(null);
          }}
        />
      ) : null}
      <div className="mf-portfolio-editor-picture">
        {form.picture ? <Shown image={form.picture} sizes="320px" /> : <span className="mf-portfolio-no-photo">No picture yet</span>}
        <Button
          size="small"
          icon="upload"
          onClick={() => {
            setPicking(true);
          }}
        >
          Change picture
        </Button>
        {errorOf("picture") ? <p className="mf-field-error">{errorOf("picture")}</p> : null}
      </div>
      <Field label="Title" error={errorOf("title")}>
        <Input
          value={form.title}
          maxLength={MAX_TITLE}
          onChange={(event) => {
            set("title", event.target.value);
          }}
        />
      </Field>
      <Field label="Discipline" error={errorOf("discipline")}>
        <Select
          value={form.discipline}
          onChange={(event) => {
            set("discipline", event.target.value);
          }}
        >
          <option value="">Choose a discipline</option>
          {disciplines.map((each) => (
            <option key={each.id} value={each.slug}>
              {each.label}
            </option>
          ))}
        </Select>
      </Field>
      {manages ? (
        <Field label="By" hint="They may edit the piece too." error={errorOf("artist_id")}>
          <Select
            value={form.artist_id}
            onChange={(event) => {
              set("artist_id", event.target.value);
            }}
          >
            <option value="">No one</option>
            {artistChoices.map((each) => (
              <option key={each.id} value={each.id}>
                {each.name}
              </option>
            ))}
            {form.artist_id && !artistChoices.some((each) => each.id === form.artist_id) ? (
              <option value={form.artist_id}>{saved?.artist?.name ?? names.get(form.artist_id) ?? "Someone"}</option>
            ) : null}
          </Select>
        </Field>
      ) : (
        <Field label="By" hint="Your pieces are credited to you.">
          <Input value={saved?.artist?.name ?? me.name} readOnly />
        </Field>
      )}
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
      <Field label="About the piece" hint="A few words about it." error={errorOf("about")}>
        <TextArea
          value={form.about}
          rows={4}
          maxLength={MAX_ABOUT}
          onChange={(event) => {
            set("about", event.target.value);
          }}
        />
      </Field>
      <Field label="Video" hint="A YouTube video's address. Its page plays it, once a visitor allows YouTube." error={errorOf("video_url")}>
        <Input
          type="url"
          value={form.video_url}
          maxLength={500}
          onChange={(event) => {
            set("video_url", event.target.value);
          }}
        />
      </Field>
      <Field label="Address" hint={form.slug ? pathOf(form.slug) : "Made from the title."} error={errorOf("slug")}>
        <Input
          value={form.slug}
          maxLength={MAX_SLUG}
          onChange={(event) => {
            setSlugTyped(true);
            set("slug", event.target.value);
          }}
        />
      </Field>
      <div className="mf-portfolio-editor-actions">
        <Button ref={saveButton} type="submit" variant="primary" disabled={busy || !dirty}>
          {live ? "Update" : "Save"}
        </Button>
        {live ? (
          <Button disabled={busy} onClick={() => void act(unpublish, "It's a draft again: it's gone from the Art page.")}>
            Unpublish
          </Button>
        ) : (
          <>
            <Button disabled={busy} onClick={() => void act(() => publish(false), "It's live on the Art page.")}>
              Publish
            </Button>
            <Button
              disabled={busy}
              aria-expanded={scheduling}
              onClick={() => {
                setScheduling((now) => !now);
              }}
            >
              Schedule
            </Button>
          </>
        )}
        {saved?.status === "published" ? (
          <a className={buttonClass({})} href={pathOf(saved.slug)} target="_blank" rel="noreferrer">
            View on the site
          </a>
        ) : null}
        {saved ? (
          <Button
            disabled={busy}
            onClick={() => {
              setDeleting(true);
            }}
          >
            Delete
          </Button>
        ) : null}
      </div>
      {scheduling && !live ? (
        <div className="mf-portfolio-schedule">
          <Field label="Goes live at">
            <Input
              type="datetime-local"
              value={at}
              onChange={(event) => {
                setAt(event.target.value);
              }}
            />
          </Field>
          <Button disabled={busy || !at} onClick={() => void act(() => publish(true), "It's scheduled.")}>
            Schedule it
          </Button>
        </div>
      ) : null}
      {picking ? (
        <ImagePicker
          title="Choose the piece's picture"
          onPick={(image) => {
            set("picture", pictureOf(image));
            setPicking(false);
          }}
          onClose={() => {
            setPicking(false);
          }}
        />
      ) : null}
      {deleting && saved ? (
        <Dialog
          title={`Delete ${saved.title}?`}
          onClose={() => {
            setDeleting(false);
          }}
        >
          <p className="mf-dialog-lead">It goes from the Art page and from here. This can&rsquo;t be undone.</p>
          <div className="mf-dialog-actions">
            <Button
              onClick={() => {
                setDeleting(false);
              }}
            >
              Keep it
            </Button>
            <Button variant="primary" disabled={busy} onClick={() => void act(remove)}>
              Delete
            </Button>
          </div>
        </Dialog>
      ) : null}
      <UnsavedDialog guard={guard} what="This piece" />
    </form>
  );
}
