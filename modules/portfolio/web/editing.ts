// The editor's form and what a save sends (`dev plans/contracts/portfolio.md` §2):
// the piece as its fields hold it, the changes from what's saved, and the
// three-way merge a save someone else got to first asks for (blog's pattern,
// `modules/blog/web/editing.ts`).
import type { FieldConflict, SettingsConflict } from "@/kernel";

import type { AdminPiece, Change, NewPiece, Picture } from "./api";

export type Form = {
  title: string;
  slug: string;
  /** A discipline's slug; "" for none chosen yet. */
  discipline: string;
  /** The artist's id; "" for no one. */
  artist_id: string;
  /** As typed: "" for none. */
  year: string;
  about: string;
  picture: Picture | null;
  /** A YouTube video's address, as typed; "" for none. */
  video_url: string;
};

export type FormField = keyof Form;

export const LABELS: Record<FormField, string> = {
  title: "Title",
  slug: "Address",
  discipline: "Discipline",
  artist_id: "By",
  year: "Year",
  about: "About the piece",
  picture: "Picture",
  video_url: "Video",
};

/** A slug: lowercase letters and digits, single hyphens between (the server's rule). */
export const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const MAX_SLUG = 120;
export const MAX_TITLE = 200;
export const MAX_ABOUT = 2000;
export const MIN_YEAR = 1000;

export function blank(picture: Picture | null, artist: string): Form {
  return { title: "", slug: "", discipline: "", artist_id: artist, year: "", about: "", picture, video_url: "" };
}

export function formOf(piece: AdminPiece): Form {
  return {
    title: piece.title,
    slug: piece.slug,
    discipline: piece.discipline?.slug ?? "",
    artist_id: piece.artist?.id ?? "",
    year: piece.year === null ? "" : String(piece.year),
    about: piece.about,
    picture: piece.picture ?? null,
    video_url: piece.video?.url ?? "",
  };
}

function keyOf(field: FormField, value: Form[FormField]): string {
  if (field === "picture") return (value as Picture | null)?.id ?? "";
  return (value as string).trim();
}

export function same(field: FormField, a: Form[FormField], b: Form[FormField]): boolean {
  return keyOf(field, a) === keyOf(field, b);
}

/** The fields the person changed from `base`. */
export function changed(form: Form, base: Form): FormField[] {
  return (Object.keys(form) as FormField[]).filter((field) => !same(field, form[field], base[field]));
}

/** What a save sends for `fields` of `form`: an empty choice as none, the picture by its id. */
export function body(form: Form, fields: readonly FormField[]): Omit<Change, "version"> {
  const sent: Record<string, unknown> = {};
  for (const field of fields) {
    if (field === "picture") {
      if (form.picture) sent.image_id = form.picture.id;
    } else if (field === "artist_id") sent.artist_id = form.artist_id || null;
    else if (field === "year") sent.year = form.year.trim() ? Number(form.year.trim()) : null;
    else if (field === "video_url") sent.video_url = form.video_url.trim() || null;
    else if (field === "slug") {
      if (form.slug) sent.slug = form.slug; // empty, a new piece's comes from its title
    } else sent[field] = form[field].trim();
  }
  return sent;
}

/** What a new piece sends: every field it has, the artist only when someone may credit others. */
export function created(form: Form, { credits, slugTyped }: { credits: boolean; slugTyped: boolean }): NewPiece {
  const fields = (Object.keys(form) as FormField[]).filter(
    (field) => (field !== "slug" || slugTyped) && (field !== "artist_id" || credits) && (field !== "year" || form.year.trim() !== "") && (field !== "video_url" || form.video_url.trim() !== ""),
  );
  return body(form, fields) as NewPiece;
}

/** The slug a title spells, as the server makes it: "Don't stop" is dont-stop. */
export function slugFor(title: string): string {
  return title
    .replace(/['’]/g, "")
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, MAX_SLUG)
    .replace(/-+$/, "");
}

/** What the person's own client checks before a save. */
export function problems(form: Form, isNew: boolean, now: Date = new Date()): Partial<Record<FormField, string>> {
  const found: Partial<Record<FormField, string>> = {};
  if (!form.title.trim()) found.title = "A piece needs a title.";
  if (!form.discipline) found.discipline = "Choose its discipline.";
  if (!form.picture) found.picture = "A piece needs a picture.";
  const year = form.year.trim();
  const latest = now.getFullYear() + 1;
  if (year && !(/^\d{4}$/.test(year) && Number(year) >= MIN_YEAR && Number(year) <= latest)) {
    found.year = `A year from ${String(MIN_YEAR)} to ${String(latest)}, such as 2025.`;
  }
  const blankAllowed = isNew && form.slug === "";
  if (!blankAllowed && (!SLUG.test(form.slug) || form.slug.length > MAX_SLUG)) {
    found.slug = "An address is lowercase letters, digits and single hyphens, such as harbour-at-dusk.";
  }
  return found;
}

/**
 * A save someone else got to first, as the kit's SaveConflict reads it: each
 * field both changed since `base`, to different values. Fields only they
 * changed are theirs, and only you, yours, with nothing to ask.
 */
export function conflictOf(detail: string, base: Form, mine: Form, theirs: AdminPiece, fields: readonly FormField[] = changed(mine, base)): SettingsConflict {
  const now = formOf(theirs);
  const conflicts: FieldConflict[] = fields
    .filter((field) => !same(field, now[field], base[field]) && !same(field, now[field], mine[field]))
    .map((field) => ({ field, yours: mine[field], theirs: now[field] }));
  return { detail, version: theirs.version, conflicts, at: theirs.updated_at };
}

/** The form to save again: theirs, with each field the person changed kept as theirs only where they chose so. */
export function merged(base: Form, mine: Form, theirs: AdminPiece, keepTheirs: ReadonlySet<string>, fields: readonly FormField[] = changed(mine, base)): Form {
  const next: Form = { ...formOf(theirs) };
  for (const field of fields) {
    if (!keepTheirs.has(field)) (next as Record<FormField, unknown>)[field] = mine[field];
  }
  return next;
}

/** A value of a field as the conflict panel says it. */
export function said(field: FormField, value: unknown, names: ReadonlyMap<string, string>): string {
  if (field === "picture") return (value as Picture | null) ? ((value as Picture).alt ?? "An image") : "No picture";
  const text = typeof value === "string" ? value : "";
  if (field === "discipline" || field === "artist_id") return names.get(text) ?? (text || "None");
  return text || "None";
}
