/**
 * The kernel's part of `editor.tools` (decisions 0058 and 0060; from VybeSite's
 * editor AI buttons): Write with AI, in every MarkdownEditor, for anyone
 * holding `kernel.ai.write` while the site has a key. With none it draws
 * nothing; with a saved key that can't be read, it says so.
 *
 * Its dialog picks a writing style (or the house style) and one task:
 * - **Draft** from a topic, put in where the cursor is;
 * - **Rewrite** the selected words, or the whole text with nothing selected;
 * - **Titles**, **Summary** and **Search words**, only for the fields the
 *   module hands the editor (`fields`), each shown first and used on Use.
 *
 * A draft and a rewrite are typed in as the editor types, so Ctrl Z takes
 * them back; a rewrite whose words changed while the AI wrote is not put in.
 */
import { useEffect, useRef, useState } from "react";

import { api, useApiQuery } from "../api/client";
import { Button } from "../ui/Button";
import { Dialog } from "../ui/Dialog";
import { Field, Input, Select, TextArea } from "../ui/Field";
import type { MarkdownTools } from "../ui/MarkdownEditor";
import { useToast } from "../ui/Toast";
import "./ai.css";
import { HOUSE_STYLE, sayAi } from "./words";

type Task = "draft" | "rewrite" | "titles" | "summary" | "search";
type Style = { id: string; name: string; description: string };
type Length = "short" | "medium" | "long";

/** What the AI reads of a text for Titles, Summary and Search words (`kernel.ai.BODY_READ`): only that is sent. */
const READ = 12_000;
/** The longest text a task takes (`ai_routes.TEXT_MAX`): a longer one is rewritten a part at a time. */
const TEXT_MAX = 20_000;

const LENGTHS: readonly (readonly [Length, string])[] = [
  ["short", "Short, 400 to 600 words"],
  ["medium", "Medium, 800 to 1,200 words"],
  ["long", "Long, 1,500 to 2,000 words"],
];

/** The tasks the editor offers, those needing a field only with it. */
export function tasksFor(editor: MarkdownTools): readonly (readonly [Task, string])[] {
  const tasks: [Task, string][] = [
    ["draft", "Draft"],
    ["rewrite", "Rewrite"],
  ];
  if (editor.fields?.title) tasks.push(["titles", "Titles"]);
  if (editor.fields?.summary) tasks.push(["summary", "Summary"]);
  if (editor.fields?.search) tasks.push(["search", "Search words"]);
  return tasks;
}

type HelpProps = {
  editor: MarkdownTools;
  styles: readonly Style[];
  onClose: () => void;
  /** Closes the dialog, then makes `change` in the editor: while the modal is open the editor is inert, so nothing typed would reach its undo. */
  onFinish: (change: () => void) => void;
};

function HelpDialog({ editor, styles, onClose, onFinish }: HelpProps) {
  const toast = useToast();
  const tasks = tasksFor(editor);
  const [task, setTask] = useState<Task>("draft");
  const [style, setStyle] = useState("");
  const [topic, setTopic] = useState("");
  const [length, setLength] = useState<Length>("medium");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [titles, setTitles] = useState<readonly string[]>([]);
  const [summary, setSummary] = useState("");
  const [search, setSearch] = useState<{ title: string; description: string } | null>(null);
  // An answer that arrives after the dialog closed is dropped.
  const open = useRef(true);
  // Set on each setup, not only at first: StrictMode, as the development app runs, sets it up twice (Codex on #135).
  useEffect(() => {
    open.current = true;
    return () => {
      open.current = false;
    };
  }, []);

  const chosen = { what: editor.label, style_id: style || null };
  const selected = editor.selected();

  const choose = (next: Task) => {
    setTask(next);
    setProblem("");
  };

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setProblem("");
    try {
      await work();
    } catch (error) {
      if (open.current) setProblem(sayAi(error));
    } finally {
      if (open.current) setBusy(false);
    }
  };

  const draft = () =>
    run(async () => {
      const { data } = await api.POST("/api/kernel/ai/draft", { body: { ...chosen, topic, length } });
      if (!open.current || !data) return;
      onFinish(() => {
        if (editor.text().trim()) editor.insert(`\n\n${data.markdown}\n\n`);
        else editor.replace(data.markdown);
        toast({ tone: "success", text: "Drafted. Ctrl Z takes it back." });
      });
    });

  const rewrite = () =>
    run(async () => {
      const part = selected.trim() ? selected : "";
      const sent = part || editor.text();
      if (sent.length > TEXT_MAX) {
        setProblem("Select up to 20,000 characters to rewrite: the AI rewrites that much at once.");
        return;
      }
      const { data } = await api.POST("/api/kernel/ai/rewrite", { body: { ...chosen, markdown: sent } });
      if (!open.current || !data) return;
      const now = part ? editor.selected() : editor.text();
      if (now !== sent) {
        setProblem("The words changed while the AI was writing, so they weren't replaced. Try again.");
        return;
      }
      onFinish(() => {
        if (part) editor.insert(data.markdown);
        else editor.replace(data.markdown);
        toast({ tone: "success", text: "Rewritten. Ctrl Z takes it back." });
      });
    });

  const suggestTitles = () =>
    run(async () => {
      const { data } = await api.POST("/api/kernel/ai/titles", { body: { ...chosen, topic, body: editor.text().slice(0, READ) } });
      if (open.current && data) setTitles(data.titles);
    });

  const writeSummary = (most: number) =>
    run(async () => {
      const { data } = await api.POST("/api/kernel/ai/summary", { body: { ...chosen, body: editor.text().slice(0, READ), max: most } });
      if (open.current && data) setSummary(data.summary);
    });

  const searchWords = () =>
    run(async () => {
      const title = editor.fields?.title?.value ?? "";
      const { data } = await api.POST("/api/kernel/ai/search", { body: { ...chosen, title, body: editor.text().slice(0, READ) } });
      if (open.current && data) setSearch(data);
    });

  const written = editor.text().trim() !== "";
  const fields = editor.fields;

  return (
    <Dialog title="Write with AI" onClose={onClose}>
      <div className="mf-ai-form">
        <div className="mf-ai-tasks" role="group" aria-label="What to do">
          {tasks.map(([id, label]) => (
            <Button
              key={id}
              size="small"
              variant={task === id ? "primary" : "secondary"}
              aria-pressed={task === id}
              onClick={() => {
                choose(id);
              }}
            >
              {label}
            </Button>
          ))}
        </div>
        <Field label="Style" hint="How the writing sounds. The site's writing rules come first whichever you pick.">
          <Select
            value={style}
            onChange={(event) => {
              setStyle(event.target.value);
            }}
          >
            <option value="">{HOUSE_STYLE}</option>
            {styles.map((one) => (
              <option key={one.id} value={one.id}>
                {one.name}
              </option>
            ))}
          </Select>
        </Field>

        {task === "draft" ? (
          <>
            <Field label="What should it be about?">
              <TextArea
                rows={3}
                maxLength={300}
                value={topic}
                onChange={(event) => {
                  setTopic(event.target.value);
                }}
              />
            </Field>
            <Field label="Length">
              <Select
                value={length}
                onChange={(event) => {
                  setLength(event.target.value as Length);
                }}
              >
                {LENGTHS.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <p className="mf-ai-note">{written ? "The draft goes in where the cursor is." : "The draft fills the empty editor."}</p>
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              <Button variant="primary" disabled={busy || !topic.trim()} onClick={() => void draft()}>
                {busy ? "Writing…" : "Write the draft"}
              </Button>
            </div>
          </>
        ) : null}

        {task === "rewrite" ? (
          <>
            <p className="mf-ai-note">
              {selected.trim() ? "Rewrites the words you selected, saying what they said." : "Rewrites the whole text, saying what it said. Select some words to rewrite only those."}
            </p>
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              <Button variant="primary" disabled={busy || !written} onClick={() => void rewrite()}>
                {busy ? "Rewriting…" : "Rewrite it"}
              </Button>
            </div>
          </>
        ) : null}

        {task === "titles" && fields?.title ? (
          <>
            {written ? null : (
              <Field label="What is it about?" hint="Nothing's written yet, so the titles come from this.">
                <Input
                  value={topic}
                  maxLength={300}
                  onChange={(event) => {
                    setTopic(event.target.value);
                  }}
                />
              </Field>
            )}
            {titles.length > 0 ? (
              <ul className="mf-ai-choices" aria-label="Titles">
                {titles.map((title) => (
                  <li key={title}>
                    <Button
                      size="small"
                      onClick={() => {
                        fields.title?.set(title);
                        onClose();
                      }}
                    >
                      Use
                    </Button>
                    <span>{title}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              <Button variant="primary" disabled={busy || (!written && !topic.trim())} onClick={() => void suggestTitles()}>
                {busy ? "Thinking…" : titles.length > 0 ? "Suggest others" : "Suggest titles"}
              </Button>
            </div>
          </>
        ) : null}

        {task === "summary" && fields?.summary ? (
          <>
            {summary ? (
              <blockquote className="mf-ai-result" aria-label="Summary">
                {summary}
              </blockquote>
            ) : (
              <p className="mf-ai-note">One or two sentences saying what the reader will find, at most {fields.summary.max} characters.</p>
            )}
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              {summary ? (
                <Button
                  onClick={() => {
                    fields.summary?.set(summary);
                    onClose();
                  }}
                >
                  Use this summary
                </Button>
              ) : null}
              <Button variant="primary" disabled={busy || !written} onClick={() => void writeSummary(fields.summary?.max ?? 300)}>
                {busy ? "Writing…" : summary ? "Write another" : "Write a summary"}
              </Button>
            </div>
          </>
        ) : null}

        {task === "search" && fields?.search ? (
          <>
            {search ? (
              <dl className="mf-ai-result" aria-label="Search words">
                <dt>Title in search results</dt>
                <dd>{search.title}</dd>
                <dt>Description</dt>
                <dd>{search.description}</dd>
              </dl>
            ) : (
              <p className="mf-ai-note">The title a search result shows and the description under it.</p>
            )}
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              {search ? (
                <Button
                  onClick={() => {
                    fields.search?.set(search.title, search.description);
                    onClose();
                  }}
                >
                  Use these
                </Button>
              ) : null}
              <Button variant="primary" disabled={busy || !written} onClick={() => void searchWords()}>
                {busy ? "Writing…" : search ? "Write others" : "Write search words"}
              </Button>
            </div>
          </>
        ) : null}

        <p className="mf-ai-problem" role="alert">
          {problem}
        </p>
      </div>
    </Dialog>
  );
}

export default function WritingHelp({ editor }: { editor: MarkdownTools }) {
  const state = useApiQuery("get", "/api/kernel/ai");
  const [open, setOpen] = useState(false);
  // A change to make once the dialog has gone, so it's typed in where Ctrl Z reaches it: from a task
  // of its own, outside React's effects, where the editor's onChange lands at once and React never
  // writes the old value back over the browser's typing (which would wipe its undo).
  const pending = useRef<(() => void) | null>(null);
  useEffect(() => {
    if (open || !pending.current) return;
    const change = pending.current;
    pending.current = null;
    window.setTimeout(change, 0);
  }, [open]);
  if (!state.data) return null;
  if (state.data.unreadable) {
    return <span className="mf-ai-note">The AI can't read its saved key. An admin can save it again in Settings → AI.</span>;
  }
  if (!state.data.ready) return null;
  return (
    <>
      <Button
        size="small"
        icon="sparkle"
        onClick={() => {
          setOpen(true);
        }}
      >
        Write with AI
      </Button>
      {open ? (
        <HelpDialog
          editor={editor}
          styles={state.data.styles}
          onClose={() => {
            setOpen(false);
          }}
          onFinish={(change) => {
            pending.current = change;
            setOpen(false);
          }}
        />
      ) : null}
    </>
  );
}
