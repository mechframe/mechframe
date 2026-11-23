/**
 * The Markdown editor (decision 0055; VM Website `AdminPost.dc.html`, which
 * `AdminPages.dc.html` shares): Write and Preview tabs over one text, the
 * board's Bold, Italic, Heading, Quote and Link buttons, and `tools`, buttons
 * a module adds after them (`blog`'s writing help and images, `embeds`'
 * Embed), given the editor's own ways in.
 *
 * Preview asks `preview`, the module's own route, for the HTML the site would
 * draw (`kernel.markdown.render`), so it shows what the page will, words not
 * saved yet included; a failure says so and offers Try again. It asks once
 * per text, only while Preview is open.
 *
 * A button's change is typed in as the browser types, so Ctrl Z takes it
 * back; where the browser can't, the text is set and the selection put back.
 * Ctrl B and Ctrl I (⌘ on a Mac) are Bold and Italic in the text.
 *
 * After `tools` come the buttons the kernel and the modules on add to every
 * editor (`editor.tools`, decision 0060), each left out if it fails: first the
 * kernel's AI writing help (decision 0058), which may fill the module's
 * `fields` too.
 */
import {
  Suspense,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentType,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { Button } from "./Button";
import { ErrorBoundary } from "./ErrorBoundary";
import { Icon } from "./Icon";
import { LoadError } from "./LoadError";
import { Prose } from "./Prose";
import { Tabs } from "./Tabs";
import { applied, link, prefixLines, wrap, type Change, type Selection } from "./markdownEdits";
import { useTextParts } from "./textParts";
import { shows } from "./words";

/**
 * The module's own fields beside the editor, which the AI's writing help may
 * fill (decision 0058): its Titles, Summary and Search words buttons show only
 * for the fields given.
 */
export type WritingFields = {
  title?: { value: string; set: (title: string) => void };
  /** `max` is the field's own limit: blog's summary takes 300. */
  summary?: { value: string; max: number; set: (summary: string) => void };
  search?: { set: (title: string, description: string) => void };
};

/** The editor's ways in, for a module's `tools`. */
export type MarkdownTools = {
  /** `before` and `after` around the selection, or around `placeholder` when nothing is selected. */
  wrap: (before: string, after: string, placeholder: string) => void;
  /** `text` where the cursor is, in place of what's selected. */
  insert: (text: string) => void;
  /** What's selected now. */
  selected: () => string;
  /** The editor's label, "Post body": what its text is. */
  label: string;
  /** The whole text. */
  text: () => string;
  /** The whole text in place of what's there, typed in as `insert` is, so Ctrl Z takes it back. */
  replace: (text: string) => void;
  /** The module's fields beside the editor, for the AI's buttons. */
  fields?: WritingFields;
};

export type MarkdownEditorProps = {
  /** The text's name, for a screen reader: "Page body". */
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** The HTML the site would draw for a text: the module's preview route. */
  preview: (text: string) => Promise<string>;
  /** Above the words in Preview: the page's or the post's title. */
  previewTitle?: ReactNode;
  /** Under them: "This is how the page looks on the site." */
  previewNote?: ReactNode;
  /** Under the editor. */
  hint?: ReactNode;
  error?: string | readonly string[] | undefined;
  maxLength?: number;
  /** More buttons after the kit's, given the editor's ways in. */
  tools?: ComponentType<{ editor: MarkdownTools }>;
  /** The module's fields beside the editor that the AI's writing help may fill. */
  fields?: WritingFields;
};

type Shown = { text: string; html: string } | { text: string; error: unknown } | null;

export function MarkdownEditor({
  label,
  value,
  onChange,
  preview,
  previewTitle,
  previewNote,
  hint,
  error,
  maxLength,
  tools: Tools,
  fields,
}: MarkdownEditorProps) {
  const made = useId();
  const { tools: added } = useTextParts();
  const text = useRef<HTMLTextAreaElement>(null);
  const [tab, setTab] = useState("write");
  const pending = useRef<readonly [number, number] | null>(null);

  const said = typeof error === "string" ? error : error?.join(" ");
  const hintId = shows(hint) ? `${made}-hint` : undefined;
  const errorId = said ? `${made}-error` : undefined;

  const make = useCallback(
    (change: (at: Selection) => Change) => {
      const area = text.current;
      if (!area) return;
      const at = { value: area.value, start: area.selectionStart, end: area.selectionEnd };
      const next = change(at);
      area.focus();
      const want = applied(at.value, next);
      // A change the text's limit refuses, as typing would be (CodeRabbit on #118); a shorter one goes.
      if (maxLength !== undefined && want.length > maxLength && want.length > at.value.length) return;
      area.setSelectionRange(next.from, next.to);
      if (typeIn(next.insert) && area.value === want) {
        area.setSelectionRange(next.select[0], next.select[1]);
      } else {
        pending.current = next.select;
        onChange(want);
      }
    },
    [onChange, maxLength],
  );

  // A change the browser couldn't type: its selection, once the text is drawn.
  useLayoutEffect(() => {
    const area = text.current;
    const select = pending.current;
    if (!area || !select || area.value !== value) return;
    pending.current = null;
    area.focus();
    area.setSelectionRange(select[0], select[1]);
  }, [value]);

  const ways: MarkdownTools = {
    wrap: (before, after, placeholder) => {
      make((at) => wrap(at, before, after, placeholder));
    },
    insert: (words) => {
      make((at) => ({ from: at.start, to: at.end, insert: words, select: [at.start + words.length, at.start + words.length] }));
    },
    selected: () => {
      const area = text.current;
      return area ? area.value.slice(area.selectionStart, area.selectionEnd) : "";
    },
    label,
    text: () => text.current?.value ?? value,
    replace: (words) => {
      make((at) => ({ from: 0, to: at.value.length, insert: words, select: [words.length, words.length] }));
    },
    ...(fields ? { fields } : {}),
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey) return;
    const key = event.key.toLowerCase();
    if (key !== "b" && key !== "i") return;
    event.preventDefault();
    // Italic is one star: an underscore makes no emphasis inside a word (CodeRabbit on #118).
    ways.wrap(key === "b" ? "**" : "*", key === "b" ? "**" : "*", key === "b" ? "bold words" : "italic words");
  };

  const write = (
    <>
      <div className="mf-editor-tools" role="group" aria-label="Formatting">
        <Button
          size="small"
          aria-label="Bold"
          title="Bold (Ctrl B)"
          onClick={() => {
            ways.wrap("**", "**", "bold words");
          }}
        >
          <b aria-hidden="true">B</b>
        </Button>
        <Button
          size="small"
          aria-label="Italic"
          title="Italic (Ctrl I)"
          onClick={() => {
            ways.wrap("*", "*", "italic words");
          }}
        >
          <i aria-hidden="true">I</i>
        </Button>
        <Button
          size="small"
          aria-label="Heading"
          onClick={() => {
            make((at) => prefixLines(at, "## "));
          }}
        >
          <span aria-hidden="true">H</span>
        </Button>
        <Button
          size="small"
          aria-label="Quote"
          onClick={() => {
            make((at) => prefixLines(at, "> "));
          }}
        >
          <span aria-hidden="true">“ ”</span>
        </Button>
        <Button
          size="small"
          aria-label="Link"
          onClick={() => {
            make((at) => link(at, "link words"));
          }}
        >
          <Icon name="link" />
        </Button>
        {Tools ? <Tools editor={ways} /> : null}
        {added.map(({ key, Part }) => (
          <ErrorBoundary key={key} where={`The editor's button ${key}`} fallback={() => null}>
            <Suspense fallback={null}>
              <Part editor={ways} />
            </Suspense>
          </ErrorBoundary>
        ))}
      </div>
      <textarea
        ref={text}
        className="mf-editor-text"
        aria-label={label}
        aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
        aria-invalid={said ? true : undefined}
        value={value}
        maxLength={maxLength}
        spellCheck
        onChange={(event) => {
          onChange(event.target.value);
        }}
        onKeyDown={onKeyDown}
      />
    </>
  );

  return (
    <div className={said ? "mf-editor mf-editor--invalid" : "mf-editor"}>
      <div className="mf-editor-box">
        <Tabs
          label="Editor"
          selected={tab}
          onSelect={setTab}
          tabs={[
            { id: "write", label: "Write", panel: write },
            {
              id: "preview",
              label: "Preview",
              panel: (
                <Preview
                  open={tab === "preview"}
                  text={value}
                  preview={preview}
                  title={previewTitle}
                  note={previewNote}
                />
              ),
            },
          ]}
        />
      </div>
      {hintId ? (
        <p id={hintId} className="mf-field-hint">
          {hint}
        </p>
      ) : null}
      {errorId ? (
        <p id={errorId} className="mf-field-error">
          {said}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Types `insert` over the selection as the browser types, so its undo keeps
 * it: `execCommand` is deprecated but still the only way a browser does that
 * for a script's change (Chrome, Edge, Firefox and Safari all keep it). False
 * where it can't, and the editor sets the text itself.
 */
function typeIn(insert: string): boolean {
  try {
    // eslint-disable-next-line @typescript-eslint/no-deprecated -- the only call that keeps the browser's undo (above)
    return typeof document.execCommand === "function" && document.execCommand(insert ? "insertText" : "delete", false, insert);
  } catch {
    return false;
  }
}

function Preview({
  open,
  text,
  preview,
  title,
  note,
}: {
  open: boolean;
  text: string;
  preview: (text: string) => Promise<string>;
  title: ReactNode;
  note: ReactNode;
}) {
  const [shown, setShown] = useState<Shown>(null);
  const current = shown !== null && shown.text === text ? shown : null;

  useEffect(() => {
    if (!open || current) return;
    let live = true;
    preview(text).then(
      (html) => {
        if (live) setShown({ text, html });
      },
      (failure: unknown) => {
        if (live) setShown({ text, error: failure });
      },
    );
    return () => {
      live = false;
    };
    // `current` is what was shown for this text: Try again forgets it, so it's asked again.
  }, [open, text, preview, current]);

  return (
    <div className="mf-editor-preview">
      {shows(title) ? <p className="mf-editor-preview-title">{title}</p> : null}
      {current === null ? (
        <p className="mf-editor-preview-wait" role="status">
          Making the preview…
        </p>
      ) : "error" in current ? (
        <LoadError
          what="The preview"
          error={current.error}
          inline
          onRetry={() => {
            setShown(null);
          }}
        />
      ) : current.html ? (
        <Prose html={current.html} />
      ) : (
        <p className="mf-editor-preview-wait">Nothing written yet.</p>
      )}
      {shows(note) ? <p className="mf-editor-preview-note">{note}</p> : null}
    </div>
  );
}
