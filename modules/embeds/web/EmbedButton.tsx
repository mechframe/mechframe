/**
 * embeds' part of editor.tools (decision 0060; from VybeSite's
 * `EmbedPicker.tsx`): the editor's Embed button. Its dialog takes a link from
 * YouTube, SoundCloud, Spotify or Bandcamp (for Bandcamp, its embed code from
 * Share, then Embed) and the words under the player, says what it found as
 * the link is typed, and puts `[words](link)` in a paragraph of its own
 * through the editor's `insert`, so Ctrl Z takes it back.
 */
import { Button, Dialog, Field, Input, type MarkdownTools } from "@/kernel";
import { useState, type KeyboardEvent } from "react";

import "./embeds.css";
import { embedMarkdown, fromBandcampCode, recognise } from "./providers";

/** What the dialog says of what's in the link field. */
function said(link: string): string {
  const typed = link.trim();
  if (!typed) return "";
  const found = recognise(typed);
  if (found) return `${found.default}.`;
  if (/^https?:\/\/[^/]*bandcamp\.com\//i.test(typed)) {
    return "For Bandcamp, paste its embed code from Share, then Embed, instead of the link.";
  }
  return "We can't play that link. It will stay a plain link.";
}

function EmbedDialog({ editor, onClose }: { editor: MarkdownTools; onClose: () => void }) {
  const [link, setLink] = useState("");
  const [words, setWords] = useState(editor.selected());

  const onLink = (typed: string) => {
    const code = typed.trimStart().startsWith("<") ? fromBandcampCode(typed) : null;
    if (code) {
      setLink(code.href);
      if (!words.trim()) setWords(code.words);
      return;
    }
    setLink(typed);
  };

  // No form of its own: the editor may sit inside a page's, and forms don't nest.
  const insert = () => {
    if (!link.trim()) return;
    editor.insert(`\n\n${embedMarkdown(link, words)}\n\n`);
    onClose();
  };
  const onEnter = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    insert();
  };

  return (
    <Dialog title="Embed a player" onClose={onClose}>
      <div className="mf-embed-form">
        <Field label="Paste a link from YouTube, SoundCloud, Spotify or Bandcamp">
          <Input
            value={link}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => {
              onLink(event.target.value);
            }}
            onKeyDown={onEnter}
          />
        </Field>
        <p className="mf-embed-found" role="status">
          {said(link)}
        </p>
        <Field label="Words under the player (optional)">
          <Input
            value={words}
            onChange={(event) => {
              setWords(event.target.value);
            }}
            onKeyDown={onEnter}
          />
        </Field>
        <div className="mf-dialog-actions">
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={!link.trim()} onClick={insert}>
            Insert
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

export default function EmbedButton({ editor }: { editor: MarkdownTools }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        size="small"
        icon="play"
        onClick={() => {
          setOpen(true);
        }}
      >
        Embed
      </Button>
      {open ? (
        <EmbedDialog
          editor={editor}
          onClose={() => {
            setOpen(false);
          }}
        />
      ) : null}
    </>
  );
}
