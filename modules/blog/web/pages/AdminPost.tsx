// One post's editor, /admin/blog/:id and /admin/blog/new (`dev plans/contracts/blog.md`;
// the canvas's AdminPost board): the title and the body in the kit's MarkdownEditor,
// whose Write with AI (the kernel's, decision 0058) may fill the title, summary and search words,
// then Publish, Details (Category, Author, Address, Summary, Cover image), Related
// posts, Search and sharing, and After publishing beside them. A live post's save
// changes the site at once (pages' contract §8, 3): its panel says Live, and its
// button Update. A save someone else got to first asks field by field (the kit's
// SaveConflict); leaving with changes asks first. pages' editor is the pattern.
import { useQueryClient } from "@tanstack/react-query";
import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";

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
  Switch,
  TextArea,
  UnsavedDialog,
  failureWords,
  useModuleEnabled,
  useSession,
  useSite,
  useToast,
  useUnsavedGuard,
  when,
  type SettingsConflict,
} from "@/kernel";
import { ImagePicker, Picture } from "@/modules/media/public";

import { CATEGORIES, LIST, ONE, PUBLIC_LIST, STATUS_TONE, STATUS_WORDS, api, pathOf, preview, useApiQuery, type Full, type NewPost } from "../api";
import "../blog.css";
import { RelatedPicker } from "../components/RelatedPicker";
import {
  BLANK,
  LABELS,
  MAX_BODY,
  MAX_SLUG,
  MAX_SUMMARY,
  MAX_TITLE,
  body,
  changed,
  conflictOf,
  formOf,
  merged,
  mineOf,
  openingWords,
  problems,
  rebased,
  said,
  slugFor,
  type Form,
  type FormField,
} from "../editing";

export default function PostEditor() {
  const { id = "" } = useParams();
  const location = useLocation();
  const session = useSession();
  const isNew = id === "new";
  // A post just made here keeps its editor as the address becomes its own, so
  // what follows the first save (a Publish) lands in the same editor.
  const created = (location.state as { created?: boolean } | null)?.created === true;
  const read = useApiQuery("get", ONE, { params: { path: { post_id: id } } }, { enabled: !isNew });
  if (isNew) {
    const me = session.status === "signed-in" ? session.user.id : "";
    return <Editor key="new" saved={null} start={{ ...BLANK, author_id: me }} />;
  }
  if (read.error) {
    const gone = read.error instanceof ApiProblem && read.error.status === 404;
    return (
      <AdminPage page="Post" title="Edit post">
        <LoadError what={gone ? "That post" : "The post"} error={read.error} onRetry={() => void read.refetch()} />
      </AdminPage>
    );
  }
  if (!read.data) return null;
  return <Editor key={created ? "new" : read.data.id} saved={read.data} start={formOf(read.data)} />;
}

/** A field's errors from a refused save: the server's, by its name or as `body.<name>`. */
function fieldErrors(problem: unknown, ...fields: string[]): string[] | undefined {
  if (!(problem instanceof ApiProblem)) return undefined;
  const found = fields.flatMap((field) => [...(problem.errors[field] ?? []), ...(problem.errors[`body.${field}`] ?? [])]);
  return found.length ? found : undefined;
}

function Editor({ saved: first, start }: { saved: Full | null; start: Form }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const session = useSession();
  const site = useSite();
  const comments = useModuleEnabled("comments");
  const community = useModuleEnabled("community");
  const campaigns = useModuleEnabled("campaigns");
  const mayPublish = session.status === "signed-in" && session.can("blog.post.publish");
  const categories = useApiQuery("get", CATEGORIES);
  const authors = useApiQuery("get", "/api/blog/admin/authors");
  const [saved, setSaved] = useState<Full | null>(first);
  const base = useMemo(() => (saved ? formOf(saved) : BLANK), [saved]);
  const [form, setForm] = useState<Form>(start);
  // A new post's address follows its title until someone types one.
  const [slugTyped, setSlugTyped] = useState(start.slug !== "");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<unknown>(null);
  const [checked, setChecked] = useState<Partial<Record<FormField, string>>>({});
  // `mine` is the form when the conflict came, typing since the save included; `fields` what the person changed.
  const [conflict, setConflict] = useState<{ said: SettingsConflict; theirs: Full; mine: Form; fields: FormField[] } | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [at, setAt] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [picking, setPicking] = useState(false);
  const saveButton = useRef<HTMLButtonElement>(null);
  const atId = useId();
  // The fields as they stand now, for an answer that lands after more typing.
  const formNow = useRef(form);
  useLayoutEffect(() => {
    formNow.current = form;
  });

  const edits = changed(form, base);
  const dirty = edits.length > 0;
  const status = saved?.status ?? "draft";
  const live = status === "published";
  // Post it in Community and Email it go with the first publish, then can't change.
  const announced = Boolean(saved?.published_at);
  const names = useMemo(() => {
    const found = new Map<string, string>();
    for (const each of categories.data?.items ?? []) found.set(each.slug, each.label);
    for (const each of authors.data?.items ?? []) found.set(each.id, each.name);
    return found;
  }, [categories.data, authors.data]);

  function set<Name extends FormField>(field: Name, value: Form[Name]) {
    setForm((now) => {
      const next = { ...now, [field]: value };
      if (field === "title" && saved === null && !slugTyped && typeof value === "string") next.slug = slugFor(value);
      return next;
    });
  }

  /** The post as the server has it now, and the lists that show it read again. */
  function remember(post: Full) {
    queryClient.setQueryData(["get", ONE, { params: { path: { post_id: post.id } } }], post);
    void queryClient.invalidateQueries({ queryKey: ["get", LIST] });
    void queryClient.invalidateQueries({ queryKey: ["get", CATEGORIES] });
    void queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_LIST] });
  }

  /**
   * Saves what changed; the post as the server now has it, or throws why not.
   * `carried` are the fields a retry already knows are the person's, so a field
   * typed back to its saved value stays theirs to ask about (blog 0.1.3, as pages').
   */
  async function save(from: Form = form, onto: Full | null = saved, carried: readonly FormField[] = []): Promise<Full> {
    const found = problems(from, onto === null);
    setChecked(found);
    if (Object.keys(found).length > 0) throw new Error("Some fields need fixing first: they're marked.");
    setRefused(null);
    if (onto === null) {
      // An address that followed the title is left out, so the server numbers it when taken (CodeRabbit on #123).
      const sending = (Object.keys(from) as FormField[]).filter((field) => field !== "slug" || slugTyped);
      const { data } = await api.POST(LIST, { body: body(from, sending) as NewPost });
      if (!data) throw new Error("The site answered without the post.");
      remember(data);
      setSaved(data);
      setForm((now) => rebased(now, from, formOf(data)));
      guard.release();
      void navigate(`/admin/blog/${data.id}`, { replace: true, state: { created: true } });
      return data;
    }
    const sent = changed(from, formOf(onto));
    if (sent.length === 0) return onto;
    try {
      const { data } = await api.PATCH(ONE, {
        params: { path: { post_id: onto.id } },
        body: { version: onto.version, ...body(from, sent) },
      });
      if (!data) throw new Error("The site answered without the post.");
      remember(data);
      setSaved(data);
      setForm((now) => rebased(now, from, formOf(data)));
      setConflict(null);
      return data;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "blog.changed") {
        const theirs = error.extra.post as Full;
        // The form as it is now, typing since the save went included (CodeRabbit on #123).
        const latest = formNow.current;
        const fields = [...new Set([...carried, ...mineOf(latest, formOf(onto), from)])];
        const conflicting = conflictOf(error.detail, formOf(onto), latest, theirs, fields);
        if (conflicting.conflicts.length === 0) {
          // They changed only what you didn't: theirs, with yours on top, saved again.
          const next = merged(formOf(onto), latest, theirs, new Set(), fields);
          setSaved(theirs);
          setForm(next);
          // The fields read as `next` at once, before React draws it, so a retry
          // answered first never takes their change for yours (blog 0.1.3, as pages').
          formNow.current = next;
          return save(next, theirs, fields);
        }
        setConflict({ said: conflicting, theirs, mine: latest, fields });
      }
      throw error;
    }
  }

  /**
   * Takes in a post a Publish or an Unpublish answered with, `held` the one this
   * editor had: someone else's save since comes into the fields you haven't
   * changed, and where you both changed one, it asks which to keep.
   */
  function adopt(answer: Full, held: Full) {
    if (answer.version === held.version) {
      setSaved(answer);
      return;
    }
    const before = formOf(held);
    const latest = formNow.current;
    const fields = changed(latest, before);
    const conflicting = conflictOf("Someone saved this post since you opened it. Here is how it reads now.", before, latest, answer, fields);
    if (conflicting.conflicts.length > 0) {
      // The publish or unpublish happened: the panel says so while the fields wait on a
      // choice, and the fields' merge base stays the one this editor had (CodeRabbit on #123).
      setSaved({ ...held, status: answer.status, publish_at: answer.publish_at, published_at: answer.published_at });
      setConflict({ said: conflicting, theirs: answer, mine: latest, fields });
      return;
    }
    setForm((now) => merged(before, now, answer, new Set()));
    setSaved(answer);
  }

  async function act(what: () => Promise<unknown>, done?: string) {
    setBusy(true);
    try {
      await what();
      if (done) toast({ tone: "success", text: done });
    } catch (error) {
      setRefused(error);
      if (!(error instanceof ApiProblem && error.code === "blog.changed")) {
        toast({ tone: "danger", text: error instanceof Error ? failureWords(error) : "That didn't go through. Try again." });
      }
    } finally {
      setBusy(false);
    }
  }

  async function publish(schedule: boolean) {
    if (schedule && !at) throw new Error("Choose when it goes live.");
    const post = dirty || saved === null ? await save() : saved;
    const { data } = await api.POST("/api/blog/admin/posts/{post_id}/publish", {
      params: { path: { post_id: post.id } },
      body: schedule ? { at: new Date(at).toISOString() } : {},
    });
    if (!data) throw new Error("The site answered without the post.");
    remember(data);
    adopt(data, post);
    setScheduling(false);
  }

  async function unpublish() {
    if (!saved) return;
    const { data } = await api.POST("/api/blog/admin/posts/{post_id}/unpublish", { params: { path: { post_id: saved.id } } });
    if (!data) throw new Error("The site answered without the post.");
    remember(data);
    adopt(data, saved);
  }

  async function remove() {
    if (!saved) return;
    await api.DELETE(ONE, { params: { path: { post_id: saved.id } } });
    queryClient.removeQueries({ queryKey: ["get", ONE, { params: { path: { post_id: saved.id } } }] });
    await queryClient.invalidateQueries({ queryKey: ["get", LIST] });
    void queryClient.invalidateQueries({ queryKey: ["get", CATEGORIES] });
    void queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_LIST] });
    guard.release();
    toast({ tone: "success", text: `${saved.title} is deleted.` });
    void navigate("/admin/blog");
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
  const savedWords = live ? "The post is updated on the site." : "Saved.";
  const errorOf = (field: FormField, ...also: string[]) => checked[field] ?? fieldErrors(refused, field, ...also);
  const lead =
    saved === null
      ? "A new post. Nothing is on the site until you publish it."
      : status === "scheduled"
        ? `Scheduled for ${when(saved.publish_at)}. Saving changes what goes live then.`
        : live
          ? "Live. Saving changes the post on the site at once."
          : "Saved as a draft. Nothing changes on the site until you publish.";
  const authorChoices = authors.data?.items ?? [];
  const authorMissing = form.author_id !== "" && !authorChoices.some((each) => each.id === form.author_id);

  return (
    <AdminPage
      page={saved?.title ?? "New post"}
      crumb={saved?.title ?? "New post"}
      title={saved === null ? "New post" : "Edit post"}
      lead={lead}
      actions={
        <>
          {live && saved ? (
            <a className={buttonClass({})} href={pathOf(saved.slug)} target="_blank" rel="noreferrer">
              View on the site
            </a>
          ) : null}
          <Button ref={saveButton} variant="primary" disabled={busy || (!dirty && saved !== null)} onClick={() => void act(() => save(), savedWords)}>
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
          format={(field, value) => said(field as FormField, value, names)}
          onResolve={(choices) => {
            const keep = new Set(Object.entries(choices).filter(([, choice]) => choice === "theirs").map(([field]) => field));
            const next = merged(formOf(saved ?? conflict.theirs), conflict.mine, conflict.theirs, keep, conflict.fields);
            // Your fields stay yours for the save that follows, but those you gave them (blog 0.1.3, as pages').
            const carried = conflict.fields.filter((field) => !keep.has(field));
            setSaved(conflict.theirs);
            setForm(next);
            formNow.current = next;
            void act(async () => {
              await save(next, conflict.theirs, carried);
              setConflict(null);
            }, "Saved.");
          }}
          onCancel={() => {
            setConflict(null);
          }}
        />
      ) : null}
      <div className="mf-blog-editor">
        <div className="mf-blog-main">
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
            label="Post body"
            value={form.body}
            onChange={(text) => {
              set("body", text);
            }}
            preview={preview}
            previewTitle={form.title || "Untitled post"}
            previewNote="This is how the post looks on the site."
            hint="Markdown works here: ## for a heading, **bold**, *italic*, > for a quote and [words](address) for a link."
            maxLength={MAX_BODY}
            error={errorOf("body")}
            fields={{
              title: {
                value: form.title,
                set: (title) => {
                  set("title", title.slice(0, MAX_TITLE));
                },
              },
              summary: {
                value: form.summary,
                max: MAX_SUMMARY,
                set: (summary) => {
                  set("summary", summary);
                },
              },
              search: {
                set: (title, description) => {
                  set("search_title", title);
                  set("search_description", description);
                },
              },
            }}
          />
        </div>
        <div className="mf-blog-side">
          <Card title="Publish" level={2}>
            <div className="mf-blog-panel">
              <p className="mf-blog-state">
                <Pill tone={STATUS_TONE[status]}>{STATUS_WORDS[status]}</Pill>
                {saved?.status === "scheduled" ? <span>{when(saved.publish_at)}</span> : null}
                {live && saved?.published_at ? <span>since {when(saved.published_at)}</span> : null}
              </p>
              {mayPublish && !live ? (
                <fieldset className="mf-blog-when">
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
              <div className="mf-blog-actions">
                {mayPublish && !live ? (
                  <Button variant="primary" disabled={busy} onClick={() => void act(() => publish(scheduling), scheduling ? "The post is scheduled." : "The post is live.")}>
                    {scheduling ? "Schedule" : "Publish"}
                  </Button>
                ) : null}
                {live ? (
                  <Button variant="primary" disabled={busy || !dirty} onClick={() => void act(() => save(), savedWords)}>
                    Update
                  </Button>
                ) : null}
                {mayPublish && saved && status !== "draft" ? (
                  <Button disabled={busy} onClick={() => void act(unpublish, live ? "The post is a draft again." : "The schedule is cleared.")}>
                    {live ? "Unpublish" : "Back to a draft"}
                  </Button>
                ) : null}
              </div>
              {mayPublish && saved ? (
                <Button
                  size="small"
                  className="mf-blog-delete"
                  disabled={busy}
                  onClick={() => {
                    setDeleting(true);
                  }}
                >
                  Delete post
                </Button>
              ) : null}
            </div>
          </Card>
          <Card title="Details" level={2}>
            <div className="mf-blog-panel">
              <Field label="Category" error={errorOf("category")}>
                <Select
                  value={form.category}
                  onChange={(event) => {
                    set("category", event.target.value);
                  }}
                >
                  <option value="">No category</option>
                  {(categories.data?.items ?? []).map((each) => (
                    <option key={each.id} value={each.slug}>
                      {each.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Author" error={errorOf("author_id")}>
                <Select
                  value={form.author_id}
                  onChange={(event) => {
                    set("author_id", event.target.value);
                  }}
                >
                  <option value="">No one named</option>
                  {authorMissing && saved?.author ? <option value={saved.author.id}>{saved.author.name}</option> : null}
                  {authorChoices.map((each) => (
                    <option key={each.id} value={each.id}>
                      {each.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                label="Address"
                error={errorOf("slug")}
                hint={
                  live && saved && form.slug !== saved.slug
                    ? `${pathOf(saved.slug)} will send visitors here.`
                    : `The post is at ${pathOf(form.slug || "…")}. Lowercase letters, digits and hyphens.`
                }
              >
                <Input
                  value={form.slug}
                  maxLength={MAX_SLUG}
                  spellCheck={false}
                  autoCapitalize="none"
                  onChange={(event) => {
                    setSlugTyped(true);
                    set("slug", event.target.value);
                  }}
                />
              </Field>
              {saved && saved.moves.length > 0 ? (
                <p className="mf-field-hint">Also reached from {saved.moves.map(pathOf).join(", ")}.</p>
              ) : null}
              <Field label="Summary" hint="One line for its card on the blog and when it's shared." error={errorOf("summary")}>
                <TextArea
                  value={form.summary}
                  maxLength={MAX_SUMMARY}
                  rows={2}
                  onChange={(event) => {
                    set("summary", event.target.value);
                  }}
                />
              </Field>
              <div className="mf-blog-cover">
                <span className="mf-blog-cover-label">Cover image</span>
                {form.cover ? (
                  <Picture image={form.cover} sizes="320px" className="mf-blog-cover-picture" />
                ) : (
                  <p className="mf-field-hint">None: the post shows a plain card on the blog and when it's shared.</p>
                )}
                {fieldErrors(refused, "cover_id")?.map((each) => (
                  <p key={each} className="mf-field-error">
                    {each}
                  </p>
                ))}
                <div className="mf-blog-actions">
                  <Button
                    size="small"
                    onClick={() => {
                      setPicking(true);
                    }}
                  >
                    {form.cover ? "Change" : "Choose a cover"}
                  </Button>
                  {form.cover ? (
                    <Button
                      size="small"
                      onClick={() => {
                        set("cover", null);
                      }}
                    >
                      Remove
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          </Card>
          <Card title="Related posts" level={2} description="Live posts shown under this one, in this order.">
            <RelatedPicker
              self={saved?.id ?? null}
              value={form.related}
              onChange={(next) => {
                set("related", next);
              }}
            />
            {fieldErrors(refused, "related")?.map((each) => (
              <p key={each} className="mf-field-error">
                {each}
              </p>
            ))}
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
              fallbackTitle={site ? `${form.title || "Untitled post"} · ${site.name}` : form.title}
              fallbackDescription={form.summary.trim() || openingWords(form.body)}
              hint="Left empty, these use the title and summary."
              errors={{ title: errorOf("search_title"), description: errorOf("search_description") }}
            />
          </Card>
          <Card title="After publishing" level={2}>
            <div className="mf-blog-panel">
              <Switch
                label={LABELS.allow_comments}
                hint={comments ? "Guests' comments wait for approval." : "Kept for when the site has comments."}
                checked={form.allow_comments}
                onChange={(on) => {
                  set("allow_comments", on);
                }}
              />
              <Switch
                label={LABELS.post_to_community}
                hint={announced ? "Sent when it first went live." : community ? "In Community, with a link back, when it first goes live." : "Kept for when the site has Community."}
                disabled={announced}
                checked={form.post_to_community}
                onChange={(on) => {
                  set("post_to_community", on);
                }}
              />
              <Switch
                label={LABELS.email_subscribers}
                hint={announced ? "Sent when it first went live." : campaigns ? "As a newsletter, when it first goes live." : "Kept for when the site has a newsletter."}
                disabled={announced}
                checked={form.email_subscribers}
                onChange={(on) => {
                  set("email_subscribers", on);
                }}
              />
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
            setForm(saved ? formOf(saved) : start);
            setChecked({});
            setRefused(null);
          }}
        />
      ) : null}
      <UnsavedDialog guard={guard} what="This post" />
      {picking ? (
        <ImagePicker
          title="Choose a cover image"
          onPick={(image) => {
            set("cover", {
              id: image.id,
              url: image.url,
              srcset: image.srcset,
              width: image.width,
              height: image.height,
              alt: image.decorative ? "" : (image.alt ?? null),
              decorative: image.decorative,
            });
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
          <p className="mf-dialog-lead">
            {live ? `${pathOf(saved.slug)} stops working at once` : "It's gone for good"}
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
              Delete post
            </Button>
          </div>
        </Dialog>
      ) : null}
    </AdminPage>
  );
}
