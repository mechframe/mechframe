/**
 * What the Markdown editor's buttons do to its text (decision 0055): each
 * answers one change, a range of the text to replace and what goes there,
 * and what to select after, so the editor can make it the way a browser
 * keeps undo for (`MarkdownEditor`).
 *
 * Bold and italic wrap the selection, or unwrap it when it's wrapped already;
 * a heading and a quote mark each line the selection touches, or unmark them
 * when every one is marked; a link wraps the words and selects its address
 * for the person to type over.
 */

/** The text and what's selected in it. */
export type Selection = { value: string; start: number; end: number };

/** Replace `from` to `to` with `insert`, then select `select`. */
export type Change = { from: number; to: number; insert: string; select: readonly [number, number] };

/** The text once `change` is made. */
export function applied(value: string, change: Change): string {
  return value.slice(0, change.from) + change.insert + value.slice(change.to);
}

/** `before` and `after` around the selection, or around `placeholder` when nothing is selected; off again when they're there. */
export function wrap({ value, start, end }: Selection, before: string, after: string, placeholder: string): Change {
  const words = value.slice(start, end);
  const outside =
    value.slice(start - before.length, start) === before && value.slice(end, end + after.length) === after;
  if (words && outside && start >= before.length) {
    const from = start - before.length;
    return { from, to: end + after.length, insert: words, select: [from, from + words.length] };
  }
  const inside = words.length >= before.length + after.length && words.startsWith(before) && words.endsWith(after);
  if (inside) {
    const bare = words.slice(before.length, words.length - after.length);
    return { from: start, to: end, insert: bare, select: [start, start + bare.length] };
  }
  const text = words || placeholder;
  const at = start + before.length;
  return { from: start, to: end, insert: before + text + after, select: [at, at + text.length] };
}

/** `prefix` at the start of each line the selection touches; off again when every one has it. */
export function prefixLines({ value, start, end }: Selection, prefix: string): Change {
  // At offset 0 the line starts there: lastIndexOf with -1 would search index 0 (Codex on #118).
  const from = start === 0 ? 0 : value.lastIndexOf("\n", start - 1) + 1;
  const stop = value.indexOf("\n", end > start && value[end - 1] === "\n" ? end - 1 : end);
  const to = stop === -1 ? value.length : stop;
  const lines = value.slice(from, to).split("\n");
  const marked = lines.every((line) => line.startsWith(prefix));
  const insert = lines.map((line) => (marked ? line.slice(prefix.length) : prefix + line)).join("\n");
  if (start === end && !marked) {
    // A caret stays where it was in its line's words.
    const caret = start + prefix.length;
    return { from, to, insert, select: [caret, caret] };
  }
  return { from, to, insert, select: [from, from + insert.length] };
}

/** A link around the selection (or `placeholder`), its address selected to type over. */
export function link({ value, start, end }: Selection, placeholder: string, address = "https://"): Change {
  const words = value.slice(start, end) || placeholder;
  const insert = `[${words}](${address})`;
  const at = start + words.length + 3;
  return { from: start, to: end, insert, select: [at, at + address.length] };
}
