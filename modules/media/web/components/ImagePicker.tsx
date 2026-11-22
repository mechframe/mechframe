// The library in a dialog, for another module to place an image (a post's
// cover, a member's photo): pick one, or upload one in place. Lifted from
// VybeSite's ImagePicker.tsx (`dev plans/contracts/media.md`), on the kit.
// An image placed without alt text is asked for some first, unless it's only
// decoration, since a screen reader would say nothing of it.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type ChangeEvent, type SubmitEvent } from "react";

import { ApiProblem, Button, Dialog, EmptyState, Field, Input, LoadError, Switch } from "@/kernel";

import { LIBRARY, type Image } from "../api";
import "../media.css";
import { useLibrary } from "./library";
import { Picture } from "./Picture";
import { ACCEPT, describeImage, tooLarge, uploadImage } from "./upload";

export type ImagePickerProps = {
  /** The dialog's heading: "Choose a cover image". */
  title: string;
  /** The image chosen, with its alt text as the library now has it. */
  onPick: (image: Image) => void;
  onClose: () => void;
};

/** A thumbnail's name for a screen reader: its alt text, else its file and size. */
export function nameOf(image: Image): string {
  const said = image.decorative ? "Only decoration" : image.alt?.trim() || image.filename;
  return `${said}, ${String(image.width)} × ${String(image.height)}`;
}

export function ImagePicker({ title, onPick, onClose }: ImagePickerProps) {
  const id = useId();
  const queryClient = useQueryClient();
  const [q, setQ] = useState("");
  const library = useLibrary(q ? { q } : {});
  const listed = library.found;
  const [chosen, setChosen] = useState<Image | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Alt text typed but not saved: leaving asks first (CodeRabbit on #116).
  const [dirty, setDirty] = useState(false);
  const [leaving, setLeaving] = useState<(() => void) | null>(null);
  const input = useRef<HTMLInputElement>(null);

  function askToLeave(then: () => void) {
    if (chosen && dirty) {
      setLeaving(() => then);
      return;
    }
    then();
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const refused = tooLarge(file);
    if (refused) {
      setProblem(refused);
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const image = await uploadImage(file);
      await queryClient.invalidateQueries({ queryKey: ["get", LIBRARY] });
      take(image);
    } catch (error) {
      setProblem(error instanceof ApiProblem ? error.detail : "The upload didn't go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function take(image: Image) {
    if (image.decorative || image.alt?.trim()) {
      onPick(image);
      onClose();
      return;
    }
    setDirty(false);
    setChosen(image);
  }

  return (
    <Dialog
      title={title}
      onClose={() => {
        askToLeave(onClose);
      }}
      wide
    >
      {leaving ? (
        <div role="alert" className="mf-media-describe">
          <p>Your alt text isn&apos;t saved. Leave it?</p>
          <div className="mf-media-actions">
            <Button
              variant="primary"
              onClick={() => {
                const then = leaving;
                setLeaving(null);
                setDirty(false);
                then();
              }}
            >
              Leave it
            </Button>
            <Button
              onClick={() => {
                setLeaving(null);
              }}
            >
              Keep writing
            </Button>
          </div>
        </div>
      ) : null}
      {chosen ? (
        <DescribeFirst
          image={chosen}
          hidden={leaving !== null}
          onDirty={setDirty}
          onDone={(image) => {
            onPick(image);
            onClose();
          }}
          onBack={() => {
            askToLeave(() => {
              setChosen(null);
            });
          }}
        />
      ) : (
        <>
          <div className="mf-media-picker-upload">
            <input
              ref={input}
              id={`${id}-file`}
              type="file"
              accept={ACCEPT}
              className="mf-media-file"
              aria-label="Upload an image"
              tabIndex={-1}
              onChange={(event) => void upload(event)}
            />
            <Button icon="upload" onClick={() => input.current?.click()} disabled={busy}>
              {busy ? "Uploading…" : "Upload an image"}
            </Button>
            <span className="mf-media-muted">PNG, JPEG or WebP, up to 15 MB</span>
          </div>
          <Field id={`${id}-search`} label="Search the library">
            <Input
              type="search"
              value={q}
              onChange={(event) => {
                setQ(event.target.value);
              }}
            />
          </Field>
          {problem ? (
            <p role="alert" className="mf-media-problem">
              {problem}
            </p>
          ) : null}
          {listed.isError ? (
            <LoadError what="the library" error={listed.error} onRetry={() => void listed.refetch()} inline />
          ) : library.loaded && library.items.length === 0 ? (
            <EmptyState title={q ? "Nothing matches" : "No images yet"}>{q ? "Try other words." : "Upload the first one above."}</EmptyState>
          ) : (
            <ul role="list" className="mf-media-grid" aria-label="The library">
              {library.items.map((image) => (
                <li key={image.id}>
                  <button
                    type="button"
                    className="mf-media-thumb"
                    aria-label={nameOf(image)}
                    onClick={() => {
                      take(image);
                    }}
                  >
                    <Picture image={{ ...image, decorative: true }} sizes="10rem" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {listed.hasNextPage ? (
            <Button disabled={listed.isFetchingNextPage} onClick={() => void listed.fetchNextPage()}>
              {listed.isFetchingNextPage ? "Loading…" : "Show more"}
            </Button>
          ) : null}
        </>
      )}
    </Dialog>
  );
}

type DescribeProps = {
  image: Image;
  hidden: boolean;
  onDirty: (dirty: boolean) => void;
  onDone: (image: Image) => void;
  onBack: () => void;
};

function DescribeFirst({ image, hidden, onDirty, onDone, onBack }: DescribeProps) {
  const id = useId();
  // The image as the library has it now: a conflict brings in another's change (CodeRabbit on #116).
  const [current, setCurrent] = useState(image);
  const [alt, setAlt] = useState("");
  const [decorative, setDecorative] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // A save that answers after this step has closed reports nothing (CodeRabbit on #116).
  const open = useRef(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    open.current = true;
    return () => {
      open.current = false;
    };
  }, []);

  function change(next: { alt?: string; decorative?: boolean }) {
    const nextAlt = next.alt ?? alt;
    const nextDecorative = next.decorative ?? decorative;
    setAlt(nextAlt);
    setDecorative(nextDecorative);
    onDirty(nextAlt.trim() !== "" || nextDecorative);
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (saving) return;
    if (!decorative && !alt.trim()) {
      setProblem("Say what's in the picture, or mark it as only decoration.");
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      const saved = await describeImage(current, { alt, decorative });
      await queryClient.invalidateQueries({ queryKey: ["get", LIBRARY] });
      if (!open.current) return;
      onDirty(false);
      onDone(saved);
    } catch (error) {
      if (!open.current) return;
      if (error instanceof ApiProblem && error.code === "media.changed") {
        const theirs = error.extra;
        const version = typeof theirs.version === "number" ? theirs.version : current.version;
        const said = typeof theirs.alt === "string" ? theirs.alt : null;
        const only = theirs.decorative === true;
        setCurrent({ ...current, version, alt: said, decorative: only });
        await queryClient.invalidateQueries({ queryKey: ["get", LIBRARY] });
        if (said || only) {
          setProblem("Someone described this image while you were writing. Here is how it reads now: place it, or change it.");
          change({ alt: said ?? "", decorative: only });
        } else {
          setProblem("Someone changed this image while you were writing. Save again to keep yours.");
        }
        return;
      }
      setProblem(error instanceof ApiProblem ? error.detail : "That didn't save. Try again.");
    } finally {
      if (open.current) setSaving(false);
    }
  }

  return (
    <form onSubmit={(event) => void save(event)} className="mf-media-describe" noValidate hidden={hidden}>
      <Picture image={{ ...current, decorative: true }} sizes="16rem" className="mf-media-preview" />
      <Field
        id={`${id}-alt`}
        label="Alt text: what's in the picture, for screen readers"
        hint="Screen readers skip this image until it has alt text."
        error={problem ?? undefined}
      >
        <Input
          value={alt}
          disabled={decorative || saving}
          maxLength={250}
          onChange={(event) => {
            change({ alt: event.target.value });
          }}
        />
      </Field>
      <Switch
        label="Only decoration"
        checked={decorative}
        disabled={saving}
        onChange={(on) => {
          change({ decorative: on });
        }}
      />
      <div className="mf-media-actions">
        <Button variant="primary" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Place it"}
        </Button>
        <Button onClick={onBack} disabled={saving}>
          Back to the library
        </Button>
      </div>
    </form>
  );
}
