// The media library's admin page, /admin/media (`dev plans/contracts/media.md`;
// the canvas's AdminMedia board): every image the site uses, the ones without
// alt text called out, and one at a time in a side panel to describe, replace,
// copy the link of, or delete once nothing places it.
import { useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState, type ChangeEvent, type SubmitEvent } from "react";
import { useSearchParams } from "react-router";

import {
  AdminPage,
  ApiProblem,
  Attention,
  Button,
  Card,
  Chip,
  Dialog,
  EmptyState,
  Field,
  LoadError,
  Pill,
  SearchBox,
  Switch,
  TextArea,
  UnsavedDialog,
  useToast,
  useUnsavedGuard,
} from "@/kernel";

import { LIBRARY, useApiQuery, type Image } from "../api";
import { useLibrary } from "../components/library";
import { Picture } from "../components/Picture";
import { ACCEPT, deleteImage, describeImage, replaceImage, tooLarge, uploadImage } from "../components/upload";
import "../media.css";

const ONE = "/api/media/admin/images/{image_id}";

function missingAlt(image: Image): boolean {
  return !image.decorative && !image.alt?.trim();
}

/** A tile's name: the file name it shows first, then what's in it, or that nothing says so yet. */
function tileName(image: Image): string {
  const alt = image.alt?.trim();
  if (missingAlt(image)) return `${image.filename}, no alt text`;
  if (image.decorative) return `${image.filename}: only decoration`;
  return alt ? `${image.filename}: ${alt}` : image.filename;
}

function kilobytes(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${String(Math.max(1, Math.round(bytes / 1024)))} KB`;
}

export default function AdminMedia() {
  const [search, setSearch] = useSearchParams();
  const onlyMissing = search.get("missing_alt") === "1";
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  // The panel's alt text typed but not saved (CodeRabbit on #116): moving to
  // another image asks first, and leaving the page asks through the guard.
  const [dirty, setDirty] = useState(false);
  const [asking, setAsking] = useState<string | null>(null);
  const library = useLibrary({ ...(q ? { q } : {}), missing_alt: onlyMissing });
  const listed = library.found;
  const queryClient = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const items = library.items;
  const missing = library.missing;
  // "Fix the first": with the filter on and nothing picked, the first without alt text is open.
  const shown = selected ?? (onlyMissing ? (items[0]?.id ?? null) : null);


  function choose(next: string) {
    if (dirty && next !== shown) {
      setAsking(next);
      return;
    }
    setSelected(next);
  }

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["get", LIBRARY] });
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const refused = tooLarge(file);
    if (refused) {
      toast({ tone: "danger", text: refused });
      return;
    }
    setUploading(true);
    try {
      const image = await uploadImage(file);
      await refresh();
      choose(image.id);
      toast({ tone: "success", text: `${image.filename} is in the library.` });
    } catch (error) {
      toast({ tone: "danger", text: error instanceof ApiProblem ? error.detail : "The upload didn't go through. Try again." });
    } finally {
      setUploading(false);
    }
  }

  return (
    <AdminPage
      page="Media"
      title="Media"
      lead="Every image the site uses. Upload once, use it anywhere."
      actions={
        <>
          <input ref={input} type="file" accept={ACCEPT} className="mf-media-file" aria-label="Upload an image" tabIndex={-1} onChange={(event) => void upload(event)} />
          <Button variant="primary" icon="upload" disabled={uploading} onClick={() => input.current?.click()}>
            {uploading ? "Uploading…" : "Upload"}
          </Button>
        </>
      }
    >
      {missing > 0 ? (
        <Attention
          tone="warning"
          what={`${String(missing)} ${missing === 1 ? "image has" : "images have"} no alt text`}
          why="People using screen readers hear nothing for them, and search engines can't tell what they show."
          action={{ label: "Fix the first", to: "/admin/media?missing_alt=1" }}
        />
      ) : null}
      <div className="mf-media-layout">
        <section aria-label="The library" className="mf-media-library">
          <div className="mf-media-filters">
            <SearchBox
              label="Search files"
              value={q}
              onChange={(event) => {
                setQ(event.target.value);
              }}
            />
            <Chip
              pressed={onlyMissing}
              onPressedChange={(pressed) => {
                setSearch(pressed ? { missing_alt: "1" } : {});
              }}
            >
              No alt text
            </Chip>
          </div>
          {listed.isError ? (
            <LoadError what="the library" error={listed.error} onRetry={() => void listed.refetch()} />
          ) : library.loaded && items.length === 0 ? (
            <EmptyState title={q || onlyMissing ? "Nothing matches" : "No images yet"}>
              {q || onlyMissing ? "Try other words, or clear the filter." : "Upload the first one: it's then here for every page."}
            </EmptyState>
          ) : (
            <ul role="list" className="mf-media-grid">
              {items.map((image) => (
                <li key={image.id}>
                  <button
                    type="button"
                    className="mf-media-thumb"
                    aria-pressed={shown === image.id}
                    aria-label={tileName(image)}
                    onClick={() => {
                      choose(image.id);
                    }}
                  >
                    <Picture image={{ ...image, decorative: true }} sizes="10rem" />
                    <span className="mf-media-thumb-name">{image.filename}</span>
                    {missingAlt(image) ? <Pill tone="warning">No alt text</Pill> : null}
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
        </section>
        {shown ? (
          <Panel
            key={shown}
            id={shown}
            onDirty={setDirty}
            onGone={() => {
              setDirty(false);
              setSelected(null);
            }}
            onChanged={refresh}
          />
        ) : null}
      </div>
      {asking ? (
        <Dialog
          title="Your alt text isn't saved"
          onClose={() => {
            setAsking(null);
          }}
        >
          <p>Open the other image and leave this one as it was?</p>
          <div className="mf-media-actions">
            <Button
              variant="primary"
              onClick={() => {
                setDirty(false);
                setSelected(asking);
                setAsking(null);
              }}
            >
              Leave it
            </Button>
            <Button
              onClick={() => {
                setAsking(null);
              }}
            >
              Keep editing
            </Button>
          </div>
        </Dialog>
      ) : null}
    </AdminPage>
  );
}

type PanelProps = { id: string; onDirty: (dirty: boolean) => void; onGone: () => void; onChanged: () => Promise<void> };

function Panel({ id, onDirty, onGone, onChanged }: PanelProps) {
  const fields = useId();
  const hintId = `${fields}-alt-hint`;
  const one = useApiQuery("get", ONE, { params: { path: { image_id: id } } });
  const queryClient = useQueryClient();
  const toast = useToast();
  const replacing = useRef<HTMLInputElement>(null);
  const [alt, setAlt] = useState<string | null>(null);
  const [decorative, setDecorative] = useState<boolean | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  // While a write is under way the form waits, so nothing typed meanwhile is lost (CodeRabbit on #116).
  const [busy, setBusy] = useState(false);
  // The version a draft was typed against: a refresh meanwhile mustn't turn it
  // into a save over another's change (CodeRabbit on #116).
  const [base, setBase] = useState<number | null>(null);
  const image = one.data;
  const dirty = alt !== null || decorative !== null;
  const guard = useUnsavedGuard(dirty, saveDraft);

  function edit(next: { alt?: string; decorative?: boolean }) {
    if (base === null && image) setBase(image.version);
    if (next.alt !== undefined) setAlt(next.alt);
    if (next.decorative !== undefined) setDecorative(next.decorative);
    onDirty(true);
  }

  async function saveDraft(): Promise<string | null> {
    if (!image) return null;
    setBusy(true);
    setProblem(null);
    try {
      await settle(
        await describeImage({ ...image, version: base ?? image.version }, { alt: alt ?? image.alt ?? "", decorative: decorative ?? image.decorative }),
      );
      return null;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "media.changed") {
        await one.refetch();
        setAlt(null);
        setDecorative(null);
        setBase(null);
        onDirty(false);
        const said = "Someone changed this image since you opened it. It now reads as they left it.";
        setProblem(said);
        return said;
      }
      const said = error instanceof ApiProblem ? error.detail : "That didn't save. Try again.";
      setProblem(said);
      return said;
    } finally {
      setBusy(false);
    }
  }

  if (one.isError) return <LoadError what="the image" error={one.error} onRetry={() => void one.refetch()} />;
  if (!image) return null;
  const shownAlt = alt ?? image.alt ?? "";
  const shownDecorative = decorative ?? image.decorative;
  const uses = image.uses ?? [];

  async function settle(fresh: Image) {
    queryClient.setQueryData(["get", ONE, { params: { path: { image_id: id } } }], fresh);
    setAlt(null);
    setDecorative(null);
    setBase(null);
    onDirty(false);
    await onChanged();
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (busy) return;
    if ((await saveDraft()) === null) toast({ tone: "success", text: "Saved." });
  }

  async function replace(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !image) return;
    const refused = tooLarge(file);
    if (refused) {
      toast({ tone: "danger", text: refused });
      return;
    }
    setBusy(true);
    try {
      await settle(await replaceImage(image, file));
      toast({ tone: "success", text: "Replaced: every page that places it shows the new file." });
    } catch (error) {
      toast({ tone: "danger", text: error instanceof ApiProblem ? error.detail : "The replace didn't go through. Try again." });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!image) return;
    try {
      await deleteImage(image);
      await onChanged();
      onGone();
      toast({ tone: "success", text: `${image.filename} is deleted.` });
    } catch (error) {
      toast({ tone: "danger", text: error instanceof ApiProblem ? error.detail : "That didn't delete. Try again." });
    }
  }

  return (
    <Card className="mf-media-panel">
      <Picture image={{ ...image, decorative: true }} sizes="20rem" className="mf-media-preview" />
      <form className="mf-media-describe" onSubmit={(event) => void save(event)} noValidate>
        <Field id={`${fields}-alt`} label="Alt text: what's in the picture, for screen readers" error={problem ?? undefined}>
          <TextArea
            className="mf-media-alt"
            rows={3}
            value={shownAlt}
            maxLength={250}
            disabled={shownDecorative || busy}
            aria-describedby={missingAlt(image) ? hintId : undefined}
            onChange={(event) => {
              edit({ alt: event.target.value });
            }}
          />
        </Field>
        {/* Under the box, as the board draws it (VM Website's AdminMedia board). */}
        {missingAlt(image) ? (
          <p id={hintId} className="mf-media-hint">
            Screen readers skip this image until it has alt text.
          </p>
        ) : null}
        <Switch
          label="Only decoration"
          checked={shownDecorative}
          disabled={busy}
          onChange={(on) => {
            edit({ decorative: on });
          }}
        />
        <div>
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
      <dl className="mf-media-facts">
        <div>
          <dt>File</dt>
          <dd>{image.filename}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>
            {image.width} × {image.height}, {kilobytes(image.bytes)}
          </dd>
        </div>
        <div>
          <dt>Added</dt>
          <dd>
            {new Date(image.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
            {image.uploaded_by ? ` by ${image.uploaded_by}` : ""}
          </dd>
        </div>
        <div>
          <dt>Used in</dt>
          <dd>
            {uses.length ? (
              <ul role="list" className="mf-media-uses">
                {uses.map((use) => (
                  <li key={use.link}>
                    <a href={use.link}>{use.label}</a>
                  </li>
                ))}
              </ul>
            ) : (
              "Nowhere yet"
            )}
          </dd>
        </div>
      </dl>
      <div className="mf-media-actions">
        <Button
          onClick={() => {
            void navigator.clipboard.writeText(image.url).then(() => { toast({ tone: "success", text: "The link is copied." }); });
          }}
        >
          Copy link
        </Button>
        <input ref={replacing} type="file" accept={ACCEPT} className="mf-media-file" aria-label="Replace the file" tabIndex={-1} onChange={(event) => void replace(event)} />
        <Button disabled={busy} onClick={() => replacing.current?.click()}>
          Replace
        </Button>
        <Button disabled={uses.length > 0 || busy} onClick={() => void remove()}>
          Delete
        </Button>
      </div>
      {uses.length > 0 ? <p className="mf-media-muted">A file that's in use can't be deleted until it's removed from those pages.</p> : null}
      <UnsavedDialog guard={guard} what="This image's alt text" />
    </Card>
  );
}
