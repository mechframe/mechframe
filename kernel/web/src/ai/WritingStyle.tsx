/**
 * `/admin/settings/writing/styles/:id`, one writing style (decision 0058; from
 * VybeSite's writing style pages), for `kernel.writing.manage`; `new` makes
 * one. A name, a short description, voice rules, phrases to avoid (one a
 * line) and up to three samples. With a key, the AI can draft the rules and
 * phrases from the samples, for the editor to change before Save. A save from
 * an older version is refused, and says so; leaving with changes asks first.
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { api, useApiQuery } from "../api/client";
import { ApiProblem } from "../api/problem";
import { SettingsPage } from "../admin/SettingsPage";
import { useSession } from "../session/session";
import { Button, LinkButton } from "../ui/Button";
import { Card } from "../ui/Card";
import { Dialog } from "../ui/Dialog";
import { Field, Input, TextArea } from "../ui/Field";
import { LoadError } from "../ui/LoadError";
import { useToast } from "../ui/Toast";
import { UnsavedDialog } from "../ui/UnsavedDialog";
import { useUnsavedGuard } from "../ui/unsaved";
import "./ai.css";
import { sayAi } from "./words";

const SAMPLES = 3;

type Shape = { name: string; description: string; voice_rules: string; avoid: string; samples: string[] };
const EMPTY: Shape = { name: "", description: "", voice_rules: "", avoid: "", samples: [] };

const STYLE_PROBLEMS: Readonly<Record<string, string>> = {
  "kernel.writing_style_changed": "Someone changed this style since you opened it. Reload the page to see their changes.",
  "kernel.writing_style_name_taken": "Another writing style has that name. Choose another.",
};

function sayStyle(error: unknown): string {
  if (error instanceof ApiProblem && STYLE_PROBLEMS[error.code]) return STYLE_PROBLEMS[error.code] ?? "";
  if (error instanceof ApiProblem && error.code === "kernel.invalid_request") {
    const first = Object.values(error.errors)[0];
    return first?.join(" ") ?? sayAi(error);
  }
  return sayAi(error);
}

function samplesOf(given: readonly string[]): string[] {
  return Array.from({ length: SAMPLES }, (_, at) => given[at] ?? "");
}

function Editor({ id, start, version }: { id: string | null; start: Shape; version: number }) {
  const toast = useToast();
  const navigate = useNavigate();
  const session = useSession();
  const ai = useApiQuery("get", "/api/kernel/ai", {}, { enabled: session.status === "signed-in" && session.can("kernel.ai.write") });
  const [shape, setShape] = useState<Shape>({ ...start, samples: samplesOf(start.samples) });
  const [saved, setSaved] = useState<Shape>({ ...start, samples: samplesOf(start.samples) });
  const [at, setAt] = useState(version);
  const [busy, setBusy] = useState<"" | "saving" | "drafting" | "deleting">("");
  const [problem, setProblem] = useState("");
  const [deleting, setDeleting] = useState(false);
  const dirty = JSON.stringify(shape) !== JSON.stringify(saved);
  // Where to go once what's saved has drawn: the leave guard asks while anything is unsaved.
  const [goTo, setGoTo] = useState<{ to: string; replace: boolean } | null>(null);
  useEffect(() => {
    if (goTo && !dirty) void navigate(goTo.to, { replace: goTo.replace });
  }, [goTo, dirty, navigate]);

  const put = (field: keyof Shape, value: string | string[]) => {
    setShape((now) => ({ ...now, [field]: value }));
  };

  const save = async (): Promise<string | null> => {
    setBusy("saving");
    setProblem("");
    const body = { ...shape, samples: shape.samples.filter((sample) => sample.trim()) };
    try {
      if (id === null) {
        const { data } = await api.POST("/api/kernel/admin/writing/styles", { body });
        if (data) {
          setSaved(shape);
          toast({ tone: "success", text: "Style saved." });
          setGoTo({ to: `/admin/settings/writing/styles/${data.id}`, replace: true });
        }
      } else {
        const { data } = await api.PATCH("/api/kernel/admin/writing/styles/{style_id}", {
          params: { path: { style_id: id } },
          body: { ...body, version: at },
        });
        if (data) {
          const now = { name: data.name, description: data.description, voice_rules: data.voice_rules, avoid: data.avoid, samples: samplesOf(data.samples) };
          setShape(now);
          setSaved(now);
          setAt(data.version);
          toast({ tone: "success", text: "Style saved." });
        }
      }
      return null;
    } catch (error) {
      const said = sayStyle(error);
      setProblem(said);
      return said;
    } finally {
      setBusy("");
    }
  };

  const guard = useUnsavedGuard(dirty, save);

  const draftRules = async () => {
    setBusy("drafting");
    setProblem("");
    try {
      const { data } = await api.POST("/api/kernel/ai/style-rules", { body: { samples: shape.samples.filter((sample) => sample.trim()) } });
      if (data) setShape((now) => ({ ...now, voice_rules: data.voice_rules, avoid: data.avoid }));
    } catch (error) {
      setProblem(sayAi(error));
    } finally {
      setBusy("");
    }
  };

  const remove = async () => {
    if (id === null) return;
    setBusy("deleting");
    try {
      await api.DELETE("/api/kernel/admin/writing/styles/{style_id}", { params: { path: { style_id: id } } });
      setSaved(shape);
      toast({ tone: "success", text: "Style deleted." });
      setGoTo({ to: "/admin/settings/writing", replace: false });
    } catch (error) {
      setDeleting(false);
      setProblem(sayAi(error));
    } finally {
      setBusy("");
    }
  };

  const hasSamples = shape.samples.some((sample) => sample.trim());

  return (
    <Card
      className="mf-settings-card mf-settings-card--form"
      title={id === null ? "New writing style" : saved.name}
      actions={
        <LinkButton size="small" to="/admin/settings/writing">
          All styles
        </LinkButton>
      }
    >
      <form
        className="mf-ai-form mf-ai-wide-form"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <Field label="Name">
          <Input
            value={shape.name}
            maxLength={80}
            onChange={(event) => {
              put("name", event.target.value);
            }}
          />
        </Field>
        <Field label="Description" hint="A line on when to use it, shown in the Style picker.">
          <Input
            value={shape.description}
            maxLength={200}
            onChange={(event) => {
              put("description", event.target.value);
            }}
          />
        </Field>
        {shape.samples.map((sample, index) => (
          <Field key={index} label={`Sample ${String(index + 1)}`} hint={index === 0 ? "Writing in the voice you want. The AI matches how it sounds, never its facts." : undefined}>
            <TextArea
              rows={4}
              maxLength={8000}
              value={sample}
              onChange={(event) => {
                put(
                  "samples",
                  shape.samples.map((each, at) => (at === index ? event.target.value : each)),
                );
              }}
            />
          </Field>
        ))}
        {ai.data?.ready ? (
          <div>
            <Button icon="sparkle" disabled={busy !== "" || !hasSamples} onClick={() => void draftRules()}>
              {busy === "drafting" ? "Drafting…" : "Draft the rules from the samples"}
            </Button>
          </div>
        ) : null}
        <Field label="Voice rules" hint="How it sounds: one rule a line.">
          <TextArea
            rows={6}
            maxLength={6000}
            value={shape.voice_rules}
            onChange={(event) => {
              put("voice_rules", event.target.value);
            }}
          />
        </Field>
        <Field label="Phrases to avoid" hint="One a line.">
          <TextArea
            rows={4}
            value={shape.avoid}
            onChange={(event) => {
              put("avoid", event.target.value);
            }}
          />
        </Field>
        <p className="mf-ai-problem" role="alert">
          {problem}
        </p>
        <div className="mf-dialog-actions">
          {id !== null ? (
            <Button
              disabled={busy !== ""}
              onClick={() => {
                setDeleting(true);
              }}
            >
              Delete
            </Button>
          ) : null}
          <Button type="submit" variant="primary" disabled={busy !== "" || !dirty || !shape.name.trim()}>
            {busy === "saving" ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
      {deleting ? (
        <Dialog
          title="Delete this style?"
          onClose={() => {
            setDeleting(false);
          }}
        >
          <p className="mf-dialog-lead">Writers can't pick it any more. What was written in it stays as it is.</p>
          <div className="mf-dialog-actions">
            <Button
              onClick={() => {
                setDeleting(false);
              }}
            >
              Cancel
            </Button>
            <Button variant="strong" disabled={busy === "deleting"} onClick={() => void remove()}>
              {busy === "deleting" ? "Deleting…" : "Delete"}
            </Button>
          </div>
        </Dialog>
      ) : null}
      <UnsavedDialog guard={guard} what="This style" />
    </Card>
  );
}

function Existing({ id }: { id: string }) {
  const found = useApiQuery("get", "/api/kernel/admin/writing/styles/{style_id}", { params: { path: { style_id: id } } });
  if (found.isError) return <LoadError what="this writing style" error={found.error} onRetry={() => void found.refetch()} />;
  if (!found.data) return <p className="mf-settings-quiet">Loading the style…</p>;
  const { data } = found;
  return (
    <Editor
      key={data.id}
      id={data.id}
      version={data.version}
      start={{ name: data.name, description: data.description, voice_rules: data.voice_rules, avoid: data.avoid, samples: data.samples }}
    />
  );
}

export default function WritingStyle() {
  const { id = "new" } = useParams();
  return <SettingsPage page="Writing style">{id === "new" ? <Editor id={null} version={0} start={EMPTY} /> : <Existing key={id} id={id} />}</SettingsPage>;
}
