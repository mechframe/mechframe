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
  EmptyState,
  Field,
  Input,
  LoadError,
  Pill,
  Switch,
  useToast,
} from "@/kernel";

import { LIBRARY, useApiQuery, type Image } from "../api";
import { nameOf } from "../components/ImagePicker";
import { Picture } from "../components/Picture";
import { ACCEPT, deleteImage, describeImage, replaceImage, tooLarge, uploadImage } from "../components/upload";
import "../media.css";

const ONE = "/api/media/admin/images/{image_id}";

function missingAlt(image: Image): boolean {
  return !image.decorative && !image.alt?.trim();
}

function kilobytes(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${String(Math.max(1, Math.round(bytes / 1024)))} KB`;
}

export default function AdminMedia() {
  const [search, setSearch] = useSearchParams();
  const onlyMissing = search.get("missing_alt") === "1";
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const listed = useApiQuery("get", LIBRARY, { params: { query: { ...(q ? { q } : {}), missing_alt: onlyMissing } } });
  const queryClient = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const items = listed.data?.items ?? [];
  const missing = listed.data?.missing_alt ?? 0;
  // "Fix the first": with the filter on and nothing picked, the first without alt text is open.
  const shown = selected ?? (onlyMissing ? (items[0]?.id ?? null) : null);


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
      setSelected(image.id);
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
          <input ref={input} type="file" accept={ACCEPT} className="mf-media-file" aria-label="Upload an image" onChange={(event) => void upload(event)} />
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
            <Field id="media-search" label="Search files">
              <Input type="search" value={q} onChange={(event) => { setQ(event.target.value); }} />
            </Field>
            <Chip
              pressed={onlyMissing}
              onPressedChange={(pressed) => {
                setSelected(null);
                setSearch(pressed ? { missing_alt: "1" } : {});
              }}
            >
              No alt text
            </Chip>
          </div>
          {listed.isError ? (
            <LoadError what="the library" error={listed.error} onRetry={() => void listed.refetch()} />
          ) : listed.data && items.length === 0 ? (
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
                    aria-label={nameOf(image) + (missingAlt(image) ? ", no alt text" : "")}
                    onClick={() => { setSelected(image.id); }}
                  >
                    <Picture image={{ ...image, decorative: true }} sizes="10rem" />
                    {missingAlt(image) ? <Pill tone="warning">No alt text</Pill> : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        {shown ? <Panel key={shown} id={shown} onGone={() => { setSelected(null); }} onChanged={refresh} /> : null}
      </div>
    </AdminPage>
  );
}

function Panel({ id, onGone, onChanged }: { id: string; onGone: () => void; onChanged: () => Promise<void> }) {
  const fields = useId();
  const one = useApiQuery("get", ONE, { params: { path: { image_id: id } } });
  const queryClient = useQueryClient();
  const toast = useToast();
  const replacing = useRef<HTMLInputElement>(null);
  const [alt, setAlt] = useState<string | null>(null);
  const [decorative, setDecorative] = useState<boolean | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const image = one.data;

  if (one.isError) return <LoadError what="the image" error={one.error} onRetry={() => void one.refetch()} />;
  if (!image) return null;
  const shownAlt = alt ?? image.alt ?? "";
  const shownDecorative = decorative ?? image.decorative;
  const uses = image.uses ?? [];

  async function settle(fresh: Image) {
    queryClient.setQueryData(["get", ONE, { params: { path: { image_id: id } } }], fresh);
    setAlt(null);
    setDecorative(null);
    await onChanged();
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (!image) return;
    setProblem(null);
    try {
      await settle(await describeImage(image, { alt: shownAlt, decorative: shownDecorative }));
      toast({ tone: "success", text: "Saved." });
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "media.changed") {
        setProblem("Someone changed this image since you opened it. It now reads as they left it.");
        await one.refetch();
        setAlt(null);
        setDecorative(null);
        return;
      }
      setProblem(error instanceof ApiProblem ? error.detail : "That didn't save. Try again.");
    }
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
    try {
      await settle(await replaceImage(image, file));
      toast({ tone: "success", text: "Replaced: every page that places it shows the new file." });
    } catch (error) {
      toast({ tone: "danger", text: error instanceof ApiProblem ? error.detail : "The replace didn't go through. Try again." });
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
    <Card title={image.filename} className="mf-media-panel">
      <Picture image={{ ...image, decorative: true }} sizes="24rem" className="mf-media-preview" />
      <form onSubmit={(event) => void save(event)} noValidate>
        <Field
          id={`${fields}-alt`}
          label="Alt text: what's in the picture, for screen readers"
          hint={missingAlt(image) ? "Screen readers skip this image until it has alt text." : undefined}
          error={problem ?? undefined}
        >
          <Input value={shownAlt} maxLength={250} disabled={shownDecorative} onChange={(event) => { setAlt(event.target.value); }} />
        </Field>
        <Switch label="Only decoration" checked={shownDecorative} onChange={setDecorative} />
        <Button type="submit" variant="primary">
          Save
        </Button>
      </form>
      <dl className="mf-media-facts">
        <dt>File</dt>
        <dd>{image.filename}</dd>
        <dt>Size</dt>
        <dd>
          {image.width} × {image.height}, {kilobytes(image.bytes)}
        </dd>
        <dt>Added</dt>
        <dd>
          {new Date(image.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
          {image.uploaded_by ? ` by ${image.uploaded_by}` : ""}
        </dd>
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
      </dl>
      <div className="mf-media-actions">
        <Button
          icon="link"
          onClick={() => {
            void navigator.clipboard.writeText(image.url).then(() => { toast({ tone: "success", text: "The link is copied." }); });
          }}
        >
          Copy link
        </Button>
        <input ref={replacing} type="file" accept={ACCEPT} className="mf-media-file" aria-label="Replace the file" onChange={(event) => void replace(event)} />
        <Button onClick={() => replacing.current?.click()}>Replace</Button>
        <Button disabled={uses.length > 0} onClick={() => void remove()}>
          Delete
        </Button>
      </div>
      {uses.length > 0 ? <p className="mf-media-muted">A file that's in use can't be deleted until it's removed from those pages.</p> : null}
    </Card>
  );
}
