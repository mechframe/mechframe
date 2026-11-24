// Draw a cover (decision 0065; `dev plans/contracts/blog-covers.md` §2, and the
// AdminPost board at canvas version 104): the AI draws the post's cover from it
// as it stands, in one of four styles. The ask: Style with a line for the one
// chosen; for Custom, What to draw and In the site's colours; With the site's
// name; Draw. The drawn cover: shown as the server's own render of it, the PNG
// it will be kept as, drawn with the kernel's Inter; its Alt text; What to change with Change it; Draw again and
// Use this cover, which keeps it as a PNG in the media library. Focus starts on
// the title, and goes back to it when a draw finishes.
import { useEffect, useRef, useState, type RefObject } from "react";

import { Button, Dialog, Field, Input, Select, Switch, TextArea, sayAi } from "@/kernel";

import { api, type Cover } from "../api";
import type { components } from "../schema";

type Style = components["schemas"]["CoverAsk"]["style"];
type Colours = components["schemas"]["CoverColours"];
type Drawn = components["schemas"]["CoverDrawn"];
/** What a cover is asked for: Draw again and Change it ask again with what it was drawn with (Codex on #147). */
type Asked = { style: Style; description: string; inColours: boolean; wordmark: boolean };

/** The most What to draw and What to change hold. */
export const MAX_ASK = 600;
/** media's longest alt text. */
export const MAX_ALT = 250;

export const STYLES: readonly (readonly [Style, string, string])[] = [
  ["editorial", "Editorial", "The post's title, large, with one accent line and quiet shapes."],
  ["signal", "Signal", "Thin waveform or network lines, with no title."],
  ["minimal", "Minimal", "The post's title, small, with one accent detail."],
  ["custom", "Custom", "Drawn from what you describe."],
];

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;

/** A theme colour as `#rrggbb`, or null when the token isn't one. */
function hex(value: string): string | null {
  const found = value.trim();
  if (!HEX.test(found)) return null;
  const digits = found.slice(1).toLowerCase();
  // Three hex digits each stand for two: #ccd is #ccccdd.
  return digits.length === 6 ? `#${digits}` : `#${digits.replace(/./g, "$&$&")}`;
}

/**
 * The site's colours, from the theme's tokens where `from` is drawn: its
 * surface, its text and its accent. Null when one can't be read as `#rrggbb`,
 * and the server then uses the default theme's.
 */
export function themeColours(from: Element): Colours | null {
  const style = getComputedStyle(from);
  const ground = hex(style.getPropertyValue("--mf-color-surface"));
  const ink = hex(style.getPropertyValue("--mf-color-text"));
  const accent = hex(style.getPropertyValue("--mf-color-accent"));
  return ground && ink && accent ? { ground, ink, accent } : null;
}

export type CoverDialogProps = {
  /** The post's fields as they stand, read when Draw is pressed. */
  post: () => { title: string; summary: string; body: string };
  /** The Draw a cover button: where the theme's colours are read, and where focus goes back. */
  opener: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  /** The cover kept in the media library, for the Cover field. */
  onUse: (cover: Cover) => void;
};

export function CoverDialog({ post, opener, onClose, onUse }: CoverDialogProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const [style, setStyle] = useState<Style>("editorial");
  const [description, setDescription] = useState("");
  const [inColours, setInColours] = useState(true);
  const [wordmark, setWordmark] = useState(true);
  const [drawn, setDrawn] = useState<(Drawn & { asked: Asked }) | null>(null);
  const [alt, setAlt] = useState("");
  const [changes, setChanges] = useState("");
  const [busy, setBusy] = useState<"" | "draw" | "change" | "use">("");
  const [problem, setProblem] = useState("");
  // Each finished draw, so focus goes back to the title once it's drawn.
  const [draws, setDraws] = useState(0);
  // An answer that arrives after the dialog closed is dropped. Set on each setup: StrictMode sets it up twice.
  const open = useRef(true);
  useEffect(() => {
    open.current = true;
    return () => {
      open.current = false;
    };
  }, []);
  useEffect(() => {
    if (draws > 0) heading.current?.focus();
  }, [draws]);

  const custom = style === "custom";
  const hint = STYLES.find(([id]) => id === style)?.[2] ?? "";

  const run = async (kind: "draw" | "change" | "use", work: () => Promise<void>) => {
    setBusy(kind);
    setProblem("");
    try {
      await work();
    } catch (error) {
      if (open.current) setProblem(sayAi(error));
    } finally {
      if (open.current) setBusy("");
    }
  };

  const draw = (revise: boolean) => {
    // The ask's options as they stand, or, for a drawn cover, the ones it was drawn with.
    const asked: Asked = drawn ? drawn.asked : { style, description, inColours, wordmark };
    const keep = asked.style === "custom";
    return run(revise ? "change" : "draw", async () => {
      const colours = !keep || asked.inColours ? themeColours(opener.current ?? document.documentElement) : null;
      const { data } = await api.POST("/api/blog/admin/covers/draw", {
        body: {
          ...post(),
          style: asked.style,
          ...(keep ? { description: asked.description } : {}),
          ...(colours ? { colours } : {}),
          wordmark: asked.wordmark,
          ...(revise && drawn ? { current: drawn.svg, changes } : {}),
        },
      });
      if (!open.current || !data) return;
      setDrawn({ ...data, asked });
      setAlt(data.alt);
      setChanges("");
      setDraws((n) => n + 1);
    });
  };

  const use = () =>
    run("use", async () => {
      if (!drawn) return;
      const { data } = await api.POST("/api/blog/admin/covers", {
        body: { svg: drawn.svg, alt: alt.trim() },
      });
      if (!open.current || !data) return;
      onUse(data.cover);
    });

  const failure = problem ? (
    <p className="mf-field-error mf-blog-cover-problem" role="alert">
      {problem}
    </p>
  ) : null;

  return (
    <Dialog title="Draw a cover" heading={heading} returnTo={opener} onClose={onClose}>
      <div className="mf-blog-cover-form">
        {drawn ? (
          <>
            <img className="mf-blog-cover-drawn" src={drawn.preview} alt={alt.trim() || "The cover the AI drew"} width={1200} height={630} />
            <Field label="Alt text" hint="Says what the cover shows, for anyone who can't see it.">
              <Input
                value={alt}
                maxLength={MAX_ALT}
                onChange={(event) => {
                  setAlt(event.target.value);
                }}
              />
            </Field>
            <Field label="What to change" hint="Up to 600 characters.">
              <div className="mf-blog-cover-change">
                <TextArea
                  rows={2}
                  maxLength={MAX_ASK}
                  value={changes}
                  onChange={(event) => {
                    setChanges(event.target.value);
                  }}
                />
                <Button disabled={busy !== "" || !changes.trim()} onClick={() => void draw(true)}>
                  {busy === "change" ? "Changing…" : "Change it"}
                </Button>
              </div>
            </Field>
            {failure}
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              <Button disabled={busy !== ""} onClick={() => void draw(false)}>
                {busy === "draw" ? "Drawing…" : "Draw again"}
              </Button>
              <Button variant="primary" disabled={busy !== ""} onClick={() => void use()}>
                {busy === "use" ? "Keeping it…" : "Use this cover"}
              </Button>
            </div>
          </>
        ) : (
          <>
            <Field label="Style" hint={hint}>
              <Select
                value={style}
                disabled={busy !== ""}
                onChange={(event) => {
                  setStyle(event.target.value as Style);
                  setProblem("");
                }}
              >
                {STYLES.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            {custom ? (
              <Field label="What to draw" hint="Up to 600 characters.">
                <TextArea
                  rows={3}
                  maxLength={MAX_ASK}
                  value={description}
                  disabled={busy !== ""}
                  onChange={(event) => {
                    setDescription(event.target.value);
                  }}
                />
              </Field>
            ) : null}
            <div className="mf-blog-panel">
              {custom ? (
                <Switch
                  label="In the site's colours"
                  hint="The theme's background, text and accent colours."
                  checked={inColours}
                  disabled={busy !== ""}
                  onChange={setInColours}
                />
              ) : null}
              <Switch
                label="With the site's name"
                hint="In the top-left corner of the cover."
                checked={wordmark}
                disabled={busy !== ""}
                onChange={setWordmark}
              />
            </div>
            {failure}
            <div className="mf-dialog-actions">
              <Button onClick={onClose}>Cancel</Button>
              <Button variant="primary" disabled={busy !== "" || (custom && !description.trim())} onClick={() => void draw(false)}>
                {busy === "draw" ? "Drawing…" : "Draw"}
              </Button>
            </div>
          </>
        )}
      </div>
    </Dialog>
  );
}
