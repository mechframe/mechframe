// The library in a dialog, for another module to place an image (a post's
// cover, a member's photo): pick one, or upload one in place. Lifted from
// VybeSite's ImagePicker.tsx (`dev plans/contracts/media.md`), on the kit.
// An image placed without alt text is asked for some first, unless it's only
// decoration, since a screen reader would say nothing of it.
import { useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type ChangeEvent, type SubmitEvent } from "react";

import { ApiProblem, Button, Dialog, EmptyState, Field, Input, LoadError, Switch } from "@/kernel";

import { LIBRARY, useApiQuery, type Image } from "../api";
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
  const listed = useApiQuery("get", LIBRARY, {});
  const [chosen, setChosen] = useState<Image | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

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
    setChosen(image);
  }

  return (
    <Dialog title={title} onClose={onClose} wide>
      {chosen ? (
        <DescribeFirst
          image={chosen}
          onDone={(image) => {
            onPick(image);
            onClose();
          }}
          onBack={() => { setChosen(null); }}
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
              onChange={(event) => void upload(event)}
            />
            <Button icon="upload" onClick={() => input.current?.click()} disabled={busy}>
              {busy ? "Uploading…" : "Upload an image"}
            </Button>
            <span className="mf-media-muted">PNG, JPEG or WebP, up to 15 MB</span>
          </div>
          {problem ? (
            <p role="alert" className="mf-media-problem">
              {problem}
            </p>
          ) : null}
          {listed.isError ? (
            <LoadError what="the library" error={listed.error} onRetry={() => void listed.refetch()} inline />
          ) : listed.data && listed.data.items.length === 0 ? (
            <EmptyState title="No images yet">Upload the first one above.</EmptyState>
          ) : (
            <ul role="list" className="mf-media-grid" aria-label="The library">
              {(listed.data?.items ?? []).map((image) => (
                <li key={image.id}>
                  <button type="button" className="mf-media-thumb" aria-label={nameOf(image)} onClick={() => { take(image); }}>
                    <Picture image={{ ...image, decorative: true }} sizes="10rem" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Dialog>
  );
}

function DescribeFirst({ image, onDone, onBack }: { image: Image; onDone: (image: Image) => void; onBack: () => void }) {
  const id = useId();
  const [alt, setAlt] = useState("");
  const [decorative, setDecorative] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const queryClient = useQueryClient();

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (!decorative && !alt.trim()) {
      setProblem("Say what's in the picture, or mark it as only decoration.");
      return;
    }
    try {
      const saved = await describeImage(image, { alt, decorative });
      await queryClient.invalidateQueries({ queryKey: ["get", LIBRARY] });
      onDone(saved);
    } catch (error) {
      setProblem(error instanceof ApiProblem ? error.detail : "That didn't save. Try again.");
    }
  }

  return (
    <form onSubmit={(event) => void save(event)} className="mf-media-describe" noValidate>
      <Picture image={{ ...image, decorative: true }} sizes="16rem" className="mf-media-preview" />
      <Field
        id={`${id}-alt`}
        label="Alt text: what's in the picture, for screen readers"
        hint="Screen readers skip this image until it has alt text."
        error={problem ?? undefined}
      >
        <Input value={alt} disabled={decorative} maxLength={250} onChange={(event) => { setAlt(event.target.value); }} />
      </Field>
      <Switch label="Only decoration" checked={decorative} onChange={setDecorative} />
      <div className="mf-media-actions">
        <Button variant="primary" type="submit">
          Place it
        </Button>
        <Button onClick={onBack}>Back to the library</Button>
      </div>
    </form>
  );
}

