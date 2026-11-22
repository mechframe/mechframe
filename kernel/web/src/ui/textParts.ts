/**
 * The parts other code adds to the kit's text (decision 0060): buttons after
 * `MarkdownEditor`'s own (the slot `editor.tools`), and the players a link
 * alone in its paragraph gives way to in `Prose` (`prose.embed`). The app's
 * mount fills it from the kernel's entries and the modules that are on; with
 * nothing given the kit draws only its own, so it still works alone.
 */
import { createContext, useContext, type ComponentType } from "react";

import type { MarkdownTools } from "./MarkdownEditor";

/** A button part, given the editor's ways in. `key` stays the same while it's shown. */
export type EditorToolPart = { key: string; Part: ComponentType<{ editor: MarkdownTools }> };

/** A player: `claims` says which links it takes; its part is given the link and its words. */
export type ProseEmbedPart = {
  key: string;
  claims: (href: string) => boolean;
  Part: ComponentType<{ href: string; words: string }>;
};

export type TextParts = { tools: readonly EditorToolPart[]; embeds: readonly ProseEmbedPart[] };

const NONE: TextParts = { tools: [], embeds: [] };

export const TextPartsContext = createContext<TextParts>(NONE);

export function useTextParts(): TextParts {
  return useContext(TextPartsContext);
}
