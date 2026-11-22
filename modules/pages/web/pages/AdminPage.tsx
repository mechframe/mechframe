// One page's editor, /admin/pages/:id and /admin/pages/new (`dev plans/contracts/pages.md`;
// the canvas's AdminPost board, which pages share with blog posts): the title and
// the body in the kit's MarkdownEditor, then Publish, Details and Search and sharing
// beside them. A live page's save changes the site at once (the owner, §8, 3): its
// panel says Live, and its button Update. A save someone else got to first asks
// field by field (the kit's SaveConflict); leaving with changes asks first.
import { useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import {
  AdminPage,
  ApiProblem,
  Button,
  buttonClass,
  Card,
  Dialog,
  Field,
  Input,
  LoadError,
  MarkdownEditor,
  Pill,
  SaveBar,
  SaveConflict,
  SearchFields,
  Select,
  UnsavedDialog,
  failureWords,
  useSession,
  useSite,
  useToast,
  useUnsavedGuard,
  when,
  type SettingsConflict,
} from "@/kernel";

import { LIST, ONE, STATUS_WORDS, api, preview, useApiQuery, type Full, type NewPage } from "../api";
import {
  BLANK,
  LABELS,
  MAX_ADDRESS,
  MAX_BODY,
  MAX_TITLE,
  MENUS,
  PRIVACY_START,
  addressFor,
  body,
  changed,
  conflictOf,
  formOf,
  merged,
  openingWords,
  problems,
  type Form,
  type FormField,
  type Menu,
} from "../editing";
import "../pages.css";

const TONE = { draft: "neutral", scheduled: "info", published: "success" } as const;

export default function PageEditor() {
  const { id = "" } = useParams();
  const [search] = useSearchParams();
  const location = useLocation();
  const isNew = id === "new";
  // A page just made here keeps its editor as the address becomes its own, so
  // what follows the first save (a Publish) lands in the same editor.
  const created = (location.state as { created?: boolean } | null)?.created === true;
  const read = useApiQuery("get", ONE, { params: { path: { page_id: id } } }, { enabled: !isNew });
  if (isNew) {
    const start = search.get("address") === "privacy" ? PRIVACY_START : BLANK;
    return <Editor key="new" saved={null} start={start} />;
  }
  if (read.error) {
    const gone = read.error instanceof ApiProblem && read.error.status === 404;
    return (
      <AdminPage page="Page" title="Edit page">
        <LoadError what={gone ? "That page" : "The page"} error={read.error} onRetry={() => void read.refetch()} />
      </AdminPage>
    );
  }
  if (!read.data) return null;
  return <Editor key={created ? "new" : read.data.id} saved={read.data} start={formOf(read.data)} />;
}

/** A field's errors from a refused save: the server's, by its name or as `body.<name>`. */
function fieldErrors(problem: unknown, field: string): string[] | undefined {
  if (!(problem instanceof ApiProblem)) return undefined;
  const found = [...(problem.errors[field] ?? []), ...(problem.errors[`body.${field}`] ?? [])];
  return found.length ? found : undefined;
}

function Editor({ saved: first, start }: { saved: Full | null; start: Form }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const session = useSession();
  const site = useSite();
  const mayPublish = session.status === "signed-in" && session.can("pages.page.publish");
  const [saved, setSaved] = useState<Full | null>(first);
  const base = useMemo(() => (saved ? formOf(saved) : BLANK), [saved]);
  const [form, setForm] = useState<Form>(start);
  // A new page's address follows its title until someone types one.
  const [addressTyped, setAddressTyped] = useState(start.address !== "");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<unknown>(null);
  const [checked, setChecked] = useState<Partial<Record<FormField, string>>>({});
  const [conflict, setConflict] = useState<{ said: SettingsConflict; theirs: Full; mine: Form } | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [at, setAt] = useState("");
  const [deleting, setDeleting] = useState(false);
  const saveButton = useRef<HTMLButtonElement>(null);
  const atId = useId();

  const edits = changed(form, base);
  const dirty = edits.length > 0;
  const status = saved?.status ?? "draft";
  const live = status === "published";

  function set<Name extends FormField>(field: Name, value: Form[Name]) {
    setForm((now) => {
      const next = { ...now, [field]: value };
      if (field === "title" && saved === null && !addressTyped) next.address = addressFor(String(value));
      return next;
    });
  }

  function remember(page: Full) {
    queryClient.setQueryData(["get", ONE, { params: { path: { page_id: page.id } } }], page);
    void queryClient.invalidateQueries({ queryKey: ["get", LIST] });
  }

  /** Saves what changed; the page as the server now has it, or throws why not. */
  async function save(from: Form = form, onto: Full | null = saved): Promise<Full> {
    const found = problems(from);
    setChecked(found);
    if (Object.keys(found).length > 0) throw new Error("Some fields need fixing first: they're marked.");
    setRefused(null);
    if (onto === null) {
      const { data } = await api.POST("/api/pages/admin/pages", {
        body: body(from, Object.keys(from) as FormField[]) as NewPage,
      });
      if (!data) throw new Error("The site answered without the page.");
      remember(data);
      setSaved(data);
      setForm(formOf(data));
      guard.release();
      void navigate(`/admin/pages/${data.id}`, { replace: true, state: { created: true } });
      return data;
    }
    const sent = changed(from, formOf(onto));
    if (sent.length === 0) return onto;
    try {
      const { data } = await api.PATCH(ONE, {
        params: { path: { page_id: onto.id } },
        body: { version: onto.version, ...body(from, sent) },
      });
      if (!data) throw new Error("The site answered without the page.");
      remember(data);
      setSaved(data);
      setForm(formOf(data));
      setConflict(null);
      return data;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "pages.changed") {
        const theirs = error.extra.page as Full;
        const said = conflictOf(error.detail, formOf(onto), from, theirs);
        if (said.conflicts.length === 0) {
          // They changed only what you didn't: theirs, with yours on top, saved again.
          setSaved(theirs);
          return save(merged(formOf(onto), from, theirs, new Set()), theirs);
        }
        setConflict({ said, theirs, mine: from });
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
      if (!(error instanceof ApiProblem && error.code === "pages.changed")) {
        toast({ tone: "danger", text: error instanceof Error ? failureWords(error) : "That didn't go through. Try again." });
      }
    } finally {
      setBusy(false);
    }
  }

  async function publish(schedule: boolean) {
    if (schedule && !at) throw new Error("Choose when it goes live.");
    const page = dirty || saved === null ? await save() : saved;
    const { data } = await api.POST("/api/pages/admin/pages/{page_id}/publish", {
      params: { path: { page_id: page.id } },
      body: schedule ? { at: new Date(at).toISOString() } : {},
    });
    if (!data) throw new Error("The site answered without the page.");
    remember(data);
    setSaved(data);
    setScheduling(false);
  }

  async function unpublish() {
    if (!saved) return;
    const { data } = await api.POST("/api/pages/admin/pages/{page_id}/unpublish", {
      params: { path: { page_id: saved.id } },
    });
    if (!data) throw new Error("The site answered without the page.");
    remember(data);
    setSaved(data);
  }

  async function remove() {
    if (!saved) return;
    await api.DELETE(ONE, { params: { path: { page_id: saved.id } } });
    queryClient.removeQueries({ queryKey: ["get", ONE, { params: { path: { page_id: saved.id } } }] });
    await queryClient.invalidateQueries({ queryKey: ["get", LIST] });
    guard.release();
    toast({ tone: "success", text: `${saved.title} is deleted.` });
    void navigate("/admin/pages");
  }

  const guard = useUnsavedGuard(dirty, async () => {
    try {
      await save();
      return null;
    } catch (error) {
      return error instanceof Error ? failureWords(error) : "";
    }
  });

  const saveLabel = live ? "Update" : "Save draft";
  const errorOf = (field: FormField) => checked[field] ?? fieldErrors(refused, field);
  const lead =
    saved === null
      ? "A new page. Nothing is on the site until you publish it."
      : status === "scheduled"
        ? `Scheduled for ${when(saved.publish_at)}. Saving changes what goes live then.`
        : live
          ? "Live. Saving changes the page on the site at once."
          : "Saved as a draft. Nothing changes on the site until you publish.";

  return (
    <AdminPage
      page={saved?.title ?? "New page"}
      crumb={saved?.title ?? "New page"}
      title={saved === null ? "New page" : "Edit page"}
      lead={lead}
      actions={
        <>
          {live && saved ? (
            <a className={buttonClass({})} href={saved.address} target="_blank" rel="noreferrer">
              View on the site
            </a>
          ) : null}
          <Button ref={saveButton} variant="primary" disabled={busy || (!dirty && saved !== null)} onClick={() => void act(() => save(), live ? "The page is updated on the site." : "Saved.")}>
            {saveLabel}
          </Button>
        </>
      }
    >
      {conflict ? (
        <SaveConflict
          conflict={conflict.said}
          labels={LABELS}
          saving={busy}
          returnTo={saveButton}
          format={(field, value) => (field === "menu" ? MENUS.find((each) => each.value === value)?.label : field === "body" ? openingWords(String(value), 120) : undefined) ?? String(value)}
          onResolve={(choices) => {
            const keep = new Set(Object.entries(choices).filter(([, choice]) => choice === "theirs").map(([field]) => field));
            const next = merged(formOf(saved ?? conflict.theirs), conflict.mine, conflict.theirs, keep);
            setSaved(conflict.theirs);
            setForm(next);
            void act(() => save(next, conflict.theirs), "Saved.");
          }}
          onCancel={() => {
            setConflict(null);
          }}
        />
      ) : null}
      <div className="mf-page-editor">
        <div className="mf-page-main">
          <Field label="Title" error={errorOf("title")}>
            <Input
              value={form.title}
              maxLength={MAX_TITLE}
              onChange={(event) => {
                set("title", event.target.value);
              }}
            />
          </Field>
          <MarkdownEditor
            label="Page body"
            value={form.body}
            onChange={(text) => {
              set("body", text);
            }}
            preview={preview}
            previewTitle={form.title || "Untitled page"}
            previewNote="This is how the page looks on the site."
            hint="Markdown works here: ## for a heading, **bold**, *italic*, > for a quote and [words](address) for a link."
            maxLength={MAX_BODY}
            error={errorOf("body")}
          />
        </div>
        <div className="mf-page-side">
          <Card title="Publish" level={2}>
            <div className="mf-page-panel">
              <p className="mf-page-state">
                <Pill tone={TONE[status]}>{STATUS_WORDS[status]}</Pill>
                {saved?.status === "scheduled" ? <span>{when(saved.publish_at)}</span> : null}
                {live && saved?.published_at ? <span>since {when(saved.published_at)}</span> : null}
              </p>
              {mayPublish && !live ? (
                <fieldset className="mf-page-when">
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
                    Schedule
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
              <div className="mf-page-actions">
                {mayPublish && !live ? (
                  <Button variant="primary" disabled={busy} onClick={() => void act(() => publish(scheduling), scheduling ? "The page is scheduled." : "The page is live.")}>
                    {scheduling ? "Schedule" : "Publish"}
                  </Button>
                ) : null}
                {live ? (
                  <Button variant="primary" disabled={busy || !dirty} onClick={() => void act(() => save(), "The page is updated on the site.")}>
                    Update
                  </Button>
                ) : null}
                {mayPublish && saved && status !== "draft" ? (
                  <Button disabled={busy} onClick={() => void act(unpublish, live ? "The page is a draft again." : "The schedule is cleared.")}>
                    {live ? "Unpublish" : "Back to a draft"}
                  </Button>
                ) : null}
              </div>
              {mayPublish && saved ? (
                <Button
                  size="small"
                  className="mf-page-delete"
                  disabled={busy}
                  onClick={() => {
                    setDeleting(true);
                  }}
                >
                  Delete page
                </Button>
              ) : null}
            </div>
          </Card>
          <Card title="Details" level={2}>
            <div className="mf-page-panel">
              <Field
                label="Address"
                error={errorOf("address")}
                hint={
                  live && saved && form.address !== saved.address
                    ? `${saved.address} will send visitors here.`
                    : "A slash, then lowercase letters, digits and hyphens, such as /press-kit."
                }
              >
                <Input
                  value={form.address}
                  maxLength={MAX_ADDRESS}
                  spellCheck={false}
                  autoCapitalize="none"
                  onChange={(event) => {
                    setAddressTyped(true);
                    set("address", event.target.value);
                  }}
                />
              </Field>
              {saved && saved.moves.length > 0 ? (
                <p className="mf-field-hint">Also reached from {saved.moves.join(", ")}.</p>
              ) : null}
              <Field label="Menu">
                <Select
                  value={form.menu}
                  onChange={(event) => {
                    set("menu", event.target.value as Menu);
                  }}
                >
                  {MENUS.map((each) => (
                    <option key={each.value} value={each.value}>
                      {each.label}
                    </option>
                  ))}
                </Select>
              </Field>
              {form.menu !== "none" ? (
                <Field label="Place in the menu" hint="Lower comes first; pages with the same place go by title.">
                  <Input
                    type="number"
                    min={0}
                    max={10000}
                    value={form.menu_order}
                    onChange={(event) => {
                      set("menu_order", Math.max(0, Math.min(10_000, Math.trunc(Number(event.target.value) || 0))));
                    }}
                  />
                </Field>
              ) : null}
            </div>
          </Card>
          <Card title="Search and sharing" level={2}>
            <SearchFields
              title={form.search_title}
              description={form.search_description}
              onTitle={(text) => {
                set("search_title", text);
              }}
              onDescription={(text) => {
                set("search_description", text);
              }}
              fallbackTitle={site ? `${form.title || "Untitled page"} · ${site.name}` : form.title}
              fallbackDescription={openingWords(form.body)}
              hint="Left empty, these use the title and the page's opening words."
              errors={{ title: errorOf("search_title"), description: errorOf("search_description") }}
            />
          </Card>
        </div>
      </div>
      {dirty ? (
        <SaveBar
          changes={Math.max(edits.length, 1)}
          saving={busy}
          saveLabel={saveLabel}
          onSave={() => void act(() => save(), live ? "The page is updated on the site." : "Saved.")}
          onDiscard={() => {
            setForm(saved ? formOf(saved) : start);
            setChecked({});
            setRefused(null);
          }}
        />
      ) : null}
      <UnsavedDialog guard={guard} what="This page" />
      {deleting && saved ? (
        <Dialog
          title={`Delete ${saved.title}?`}
          onClose={() => {
            setDeleting(false);
          }}
        >
          <p className="mf-dialog-lead">
            {live ? `${saved.address} stops working at once` : "It's gone for good"}
            {saved.moves.length > 0 ? ", and so do the addresses it moved from" : ""}. This can't be undone.
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
              Delete page
            </Button>
          </div>
        </Dialog>
      ) : null}
    </AdminPage>
  );
}
