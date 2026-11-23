// The email editor, /admin/campaigns/new and /admin/campaigns/:id
// (`dev plans/contracts/campaigns.md` §2): not drawn on the canvas, so built in the
// boards' language as blog's editor is. Subject, Preview text, Kind and the body in
// the kit's MarkdownEditor with Preview, then Send a test to me, Send now or Schedule
// with a date and time. A save someone else got to first asks which to keep, field
// by field (the kit's SaveConflict); leaving with changes asks first. Once it's sent,
// the email is read-only: "Sent to n people, <when>".
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useLayoutEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import {
  AdminPage,
  ApiProblem,
  Attention,
  Button,
  Card,
  Dialog,
  Field,
  Input,
  LoadError,
  MarkdownEditor,
  Pill,
  Prose,
  SaveConflict,
  Select,
  UnsavedDialog,
  failureWords,
  useToast,
  useUnsavedGuard,
  type Choices,
  type FieldConflict,
  type SettingsConflict,
} from "@/kernel";

import {
  KIND_WORDS,
  ONE,
  STATUS_TONE,
  STATUS_WORDS,
  api,
  dayAndTime,
  people,
  preview,
  useApiQuery,
  type CampaignEmail,
  type Kind,
} from "../api";
import "../campaigns.css";

type Form = { kind: Kind; subject: string; preview: string; body: string };
type FormField = keyof Form;

const FIELDS: readonly FormField[] = ["kind", "subject", "preview", "body"];
const LABELS: Record<FormField, string> = { kind: "Kind", subject: "Subject", preview: "Preview text", body: "Email body" };
const BLANK: Form = { kind: "newsletter", subject: "", preview: "", body: "" };
const LISTS = ["campaigns", "lists"] as const;

/** A save stopped before it went: the field says why, so no toast does too. */
class Untitled extends Error {}

const formOf = (email: CampaignEmail): Form => ({ kind: email.kind, subject: email.subject, preview: email.preview, body: email.body });
const changed = (form: Form, base: Form): FormField[] => FIELDS.filter((field) => form[field] !== base[field]);

function fieldErrors(error: unknown, field: FormField): string[] | undefined {
  return error instanceof ApiProblem ? error.errors[`body.${field}`] : undefined;
}

/** The email's words and footer as a subscriber reads them, for a sent email. */
function SentCopy({ email }: { email: CampaignEmail }) {
  const shown = useQuery({
    queryKey: ["campaigns", "copy", email.id, email.version],
    queryFn: () => preview(email.id, email.body),
  });
  if (shown.error) return <LoadError what="The email" error={shown.error} onRetry={() => void shown.refetch()} inline />;
  if (shown.data === undefined) return <p className="mf-newsletter-quiet">Loading…</p>;
  return <Prose html={shown.data} />;
}

function Sent({ email }: { email: CampaignEmail }) {
  const when = email.sent_at ?? email.started_at;
  const said =
    email.status === "sending"
      ? `Sending: ${people(email.sent_to)} so far.`
      : `Sent to ${people(email.sent_to)}${when ? `, ${dayAndTime(when)}` : ""}.`;
  return (
    <AdminPage page={email.subject} title={email.subject} crumb={email.subject} lead={said}>
      <Card className="mf-newsletter-sent-card">
        <p className="mf-newsletter-meta">
          <Pill tone={STATUS_TONE[email.status]}>{STATUS_WORDS[email.status]}</Pill> {KIND_WORDS[email.kind]}
          {email.preview ? <span className="mf-newsletter-quiet"> · {email.preview}</span> : null}
        </p>
        <SentCopy email={email} />
      </Card>
    </AdminPage>
  );
}

function Editor({ first }: { first: CampaignEmail | null }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [saved, setSaved] = useState<CampaignEmail | null>(first);
  const base = saved ? formOf(saved) : BLANK;
  const [form, setForm] = useState<Form>(base);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<unknown>(null);
  const [untitled, setUntitled] = useState(false);
  const [conflict, setConflict] = useState<{ said: SettingsConflict; theirs: CampaignEmail; mine: Form } | null>(null);
  const [asking, setAsking] = useState<"send" | "delete" | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [at, setAt] = useState("");
  const atId = useId();
  const saveButton = useRef<HTMLButtonElement>(null);
  const formNow = useRef(form);
  useLayoutEffect(() => {
    formNow.current = form;
  });

  const edits = changed(form, base);
  const dirty = edits.length > 0;
  const scheduled = saved?.status === "scheduled";

  const set = <Name extends FormField>(field: Name, value: Form[Name]) => {
    setForm((now) => ({ ...now, [field]: value }));
  };

  const remember = (email: CampaignEmail) => {
    queryClient.setQueryData(["get", ONE, { params: { path: { email_id: email.id } } }], email);
    void queryClient.invalidateQueries({ queryKey: LISTS });
    setSaved(email);
  };

  /** Saves what changed: the email as the server now has it, or throws why not. */
  async function save(from: Form = form, onto: CampaignEmail | null = saved): Promise<CampaignEmail> {
    if (!from.subject.trim()) {
      setUntitled(true);
      throw new Untitled("An email needs a subject.");
    }
    setUntitled(false);
    setRefused(null);
    if (onto === null) {
      const { data } = await api.POST("/api/campaigns/admin/emails", { body: { ...from, subject: from.subject.trim() } });
      if (!data) throw new Error("The site answered without the email.");
      remember(data);
      setForm(formOf(data));
      guard.release();
      void navigate(`/admin/campaigns/${data.id}`, { replace: true });
      return data;
    }
    const sent = changed(from, formOf(onto));
    if (sent.length === 0) return onto;
    try {
      const { data } = await api.PATCH(ONE, {
        params: { path: { email_id: onto.id } },
        body: { version: onto.version, ...Object.fromEntries(sent.map((field) => [field, from[field]])) },
      });
      if (!data) throw new Error("The site answered without the email.");
      remember(data);
      setForm((now) => ({ ...formOf(data), ...Object.fromEntries(changed(now, from).map((field) => [field, now[field]])) }));
      setConflict(null);
      return data;
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "campaigns.changed") {
        const theirs = error.extra.email as CampaignEmail;
        const now = formOf(theirs);
        const before = formOf(onto);
        const latest = formNow.current;
        const mine = changed(latest, before);
        const conflicts: FieldConflict[] = mine
          .filter((field) => now[field] !== before[field] && now[field] !== latest[field])
          .map((field) => ({ field, yours: latest[field], theirs: now[field] }));
        const next: Form = { ...now, ...Object.fromEntries(mine.map((field) => [field, latest[field]])) };
        if (conflicts.length === 0) {
          setSaved(theirs);
          setForm(next);
          return save(next, theirs);
        }
        setConflict({ said: { detail: error.detail, version: theirs.version, conflicts, at: theirs.updated_at }, theirs, mine: latest });
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
      if (!(error instanceof Untitled) && !(error instanceof ApiProblem && error.code === "campaigns.changed")) {
        toast({ tone: "danger", text: error instanceof ApiProblem ? error.detail : error instanceof Error ? failureWords(error) : "That didn't go through." });
      }
    } finally {
      setBusy(false);
    }
  }

  const guard = useUnsavedGuard(dirty, async () => {
    try {
      await save();
      return null;
    } catch (error) {
      return error instanceof Error ? failureWords(error) : "";
    }
  });

  async function test() {
    const email = dirty || saved === null ? await save() : saved;
    const { data } = await api.POST("/api/campaigns/admin/emails/{email_id}/test", { params: { path: { email_id: email.id } } });
    if (!data) throw new Error("The test wasn't sent.");
    toast({ tone: "success", text: `A test is on its way to ${data.to}.` });
  }

  async function send(when: string | null) {
    const email = dirty || saved === null ? await save() : saved;
    const { data } = await api.POST("/api/campaigns/admin/emails/{email_id}/send", {
      params: { path: { email_id: email.id } },
      body: when === null ? {} : { at: new Date(when).toISOString() },
    });
    if (!data) throw new Error("The site answered without the email.");
    remember(data);
    setForm(formOf(data));
    setAsking(null);
    setScheduling(false);
  }

  async function cancel() {
    if (!saved) return;
    const { data } = await api.POST("/api/campaigns/admin/emails/{email_id}/cancel", { params: { path: { email_id: saved.id } } });
    if (!data) throw new Error("The site answered without the email.");
    remember(data);
  }

  async function remove() {
    if (!saved) return;
    await api.DELETE(ONE, { params: { path: { email_id: saved.id } } });
    await queryClient.invalidateQueries({ queryKey: LISTS });
    guard.release();
    toast({ tone: "success", text: `${saved.subject} is deleted.` });
    void navigate("/admin/campaigns");
  }

  if (saved && (saved.status === "sending" || saved.status === "sent")) return <Sent email={saved} />;
  const title = saved === null ? "New email" : saved.subject || "Untitled email";
  const reach = saved?.audience;
  return (
    <AdminPage
      page={title}
      title={title}
      crumb={saved === null ? "New email" : saved.subject}
      lead={
        saved?.status === "scheduled" && saved.send_at
          ? `Scheduled for ${dayAndTime(saved.send_at)}, to ${people(reach ?? 0)} as things stand.`
          : "A draft. Nothing is sent until you send it or schedule it."
      }
      actions={
        <Button ref={saveButton} variant={dirty ? "primary" : "secondary"} disabled={busy || (!dirty && saved !== null)} onClick={() => void act(() => save(), "Saved.")}>
          Save draft
        </Button>
      }
    >
      <div className="mf-newsletter-editor">
        {conflict ? (
          <SaveConflict
            conflict={conflict.said}
            labels={LABELS}
            saving={busy}
            returnTo={saveButton}
            onCancel={() => {
              setConflict(null);
            }}
            onResolve={(choices: Choices) => {
              const theirs = formOf(conflict.theirs);
              const next: Form = { ...form };
              for (const each of conflict.said.conflicts) {
                const field = each.field as FormField;
                if (choices[field] === "theirs") (next as Record<FormField, string>)[field] = theirs[field];
              }
              setSaved(conflict.theirs);
              setForm(next);
              void act(() => save(next, conflict.theirs), "Saved.");
            }}
          />
        ) : null}
        <Card className="mf-newsletter-fields">
          <Field label="Subject" error={untitled ? ["An email needs a subject."] : fieldErrors(refused, "subject")}>
            <Input value={form.subject} maxLength={150} required onChange={(event) => { set("subject", event.target.value); }} />
          </Field>
          <Field label="Preview text" hint="The line an inbox shows after the subject." error={fieldErrors(refused, "preview")}>
            <Input value={form.preview} maxLength={150} onChange={(event) => { set("preview", event.target.value); }} />
          </Field>
          <Field label="Kind">
            <Select value={form.kind} onChange={(event) => { set("kind", event.target.value === "release" ? "release" : "newsletter"); }}>
              <option value="newsletter">{KIND_WORDS.newsletter}</option>
              <option value="release">{KIND_WORDS.release}</option>
            </Select>
          </Field>
          <MarkdownEditor
            label="Email body"
            value={form.body}
            maxLength={100_000}
            onChange={(value) => { set("body", value); }}
            preview={(text) => (saved ? preview(saved.id, text) : Promise.resolve("<p>Save the draft to see how it reads in an inbox.</p>"))}
            previewTitle={form.subject || "Untitled email"}
            previewNote="This is how the email reads in an inbox, with the footer every subscriber gets."
            error={fieldErrors(refused, "body")}
          />
        </Card>
        {refused instanceof ApiProblem && refused.code === "campaigns.no_address" ? (
          <Attention tone="warning" what="The newsletter has no postal address" why={refused.detail} action={{ label: "Add it", to: "/admin/settings" }} />
        ) : null}
        <Card className="mf-newsletter-send">
          <h2>Send it</h2>
          {scheduled ? (
            <div className="mf-newsletter-actions">
              <Button disabled={busy} onClick={() => void act(cancel, "Back to a draft: it won't go out.")}>
                Cancel the schedule
              </Button>
            </div>
          ) : (
            <>
              <p className="mf-newsletter-quiet">
                {reach === undefined ? "Save the draft first." : `It goes to ${people(reach)}: everyone subscribed and not set aside.`}
              </p>
              <div className="mf-newsletter-actions">
                <Button disabled={busy} onClick={() => void act(test)}>
                  Send a test to me
                </Button>
                <Button variant="primary" disabled={busy} onClick={() => { setAsking("send"); }}>
                  Send now
                </Button>
                <Button disabled={busy} onClick={() => { setScheduling((now) => !now); }} aria-expanded={scheduling}>
                  Schedule
                </Button>
                {saved ? (
                  <Button disabled={busy} onClick={() => { setAsking("delete"); }}>
                    Delete
                  </Button>
                ) : null}
              </div>
              {scheduling ? (
                <div className="mf-newsletter-schedule">
                  <Field label="When it goes out" id={atId} hint="In your own time zone.">
                    <Input type="datetime-local" value={at} onChange={(event) => { setAt(event.target.value); }} />
                  </Field>
                  <Button
                    variant="primary"
                    disabled={busy || !at}
                    onClick={() => void act(() => send(at), "Scheduled.")}
                  >
                    Schedule it
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </Card>
      </div>
      {asking === "send" ? (
        <Dialog title="Send it now?" onClose={() => { setAsking(null); }}>
          <p>{reach === undefined ? "It goes to everyone subscribed." : `It goes to ${people(reach)} now. There's no unsending it.`}</p>
          <div className="mf-newsletter-actions">
            <Button variant="primary" disabled={busy} onClick={() => void act(() => send(null), "Sending now.")}>
              Send it
            </Button>
            <Button onClick={() => { setAsking(null); }}>Not yet</Button>
          </div>
        </Dialog>
      ) : null}
      {asking === "delete" ? (
        <Dialog title="Delete this draft?" onClose={() => { setAsking(null); }}>
          <p>It goes for good.</p>
          <div className="mf-newsletter-actions">
            <Button variant="primary" disabled={busy} onClick={() => void act(remove)}>
              Delete it
            </Button>
            <Button onClick={() => { setAsking(null); }}>Keep it</Button>
          </div>
        </Dialog>
      ) : null}
      <UnsavedDialog guard={guard} what="This email" />
    </AdminPage>
  );
}

export default function AdminEmail() {
  const { id } = useParams();
  const isNew = id === undefined || id === "new";
  const read = useApiQuery("get", ONE, { params: { path: { email_id: id ?? "" } } }, { enabled: !isNew });
  if (isNew) return <Editor key="new" first={null} />;
  if (read.error) {
    return (
      <AdminPage page="Email" title="Email">
        <LoadError what="This email" error={read.error} onRetry={() => void read.refetch()} />
      </AdminPage>
    );
  }
  if (!read.data) return null;
  return <Editor key={read.data.id} first={read.data} />;
}
