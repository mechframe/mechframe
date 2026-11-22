// The editor's form and what a save sends (`dev plans/contracts/blog.md` §2):
// the post as its fields hold it, the changes from what's saved, and the
// three-way merge a save someone else got to first asks for (pages' pattern,
// `modules/pages/web/editing.ts`).
import type { FieldConflict, SettingsConflict } from "@/kernel";

import type { Change, Cover, Full } from "./api";

export type RelatedPick = Full["related"][number];

export type Form = {
  title: string;
  slug: string;
  summary: string;
  body: string;
  /** A category's slug; "" for none. */
  category: string;
  /** The author's id; "" for none. */
  author_id: string;
  cover: Cover | null;
  related: RelatedPick[];
  search_title: string;
  search_description: string;
  allow_comments: boolean;
  post_to_community: boolean;
  email_subscribers: boolean;
};

export type FormField = keyof Form;

export const LABELS: Record<FormField, string> = {
  title: "Title",
  slug: "Address",
  summary: "Summary",
  body: "Post body",
  category: "Category",
  author_id: "Author",
  cover: "Cover image",
  related: "Related posts",
  search_title: "Title in search results",
  search_description: "Description",
  allow_comments: "Allow comments",
  post_to_community: "Post it in Community",
  email_subscribers: "Email it to subscribers",
};

/** A slug: lowercase letters and digits, single hyphens between (the server's rule). */
export const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const MAX_SLUG = 80;
export const MAX_TITLE = 200;
export const MAX_SUMMARY = 300;
export const MAX_BODY = 100_000;
export const MAX_RELATED = 3;

export const BLANK: Form = {
  title: "",
  slug: "",
  summary: "",
  body: "",
  category: "",
  author_id: "",
  cover: null,
  related: [],
  search_title: "",
  search_description: "",
  allow_comments: true,
  post_to_community: false,
  email_subscribers: false,
};

export function formOf(post: Full): Form {
  return {
    title: post.title,
    slug: post.slug,
    summary: post.summary,
    body: post.body,
    category: post.category?.slug ?? "",
    author_id: post.author?.id ?? "",
    cover: post.cover ?? null,
    related: post.related,
    search_title: post.search_title ?? "",
    search_description: post.search_description ?? "",
    allow_comments: post.allow_comments,
    post_to_community: post.post_to_community,
    email_subscribers: post.email_subscribers,
  };
}

/** A field's value as it's compared: a cover by its image, related posts by their ids in order. */
function keyOf(field: FormField, value: Form[FormField]): string | boolean {
  if (field === "cover") return (value as Cover | null)?.id ?? "";
  if (field === "related") return (value as RelatedPick[]).map((each) => each.id).join(",");
  return value as string | boolean;
}

export function same(field: FormField, a: Form[FormField], b: Form[FormField]): boolean {
  return keyOf(field, a) === keyOf(field, b);
}

/** The fields the person changed from `base`. */
export function changed(form: Form, base: Form): FormField[] {
  return (Object.keys(form) as FormField[]).filter((field) => !same(field, form[field], base[field]));
}

/** What a save sends for `fields` of `form`: an empty choice as none, the cover and related posts by id. */
export function body(form: Form, fields: readonly FormField[]): Omit<Change, "version"> {
  const sent: Record<string, unknown> = {};
  for (const field of fields) {
    if (field === "cover") sent.cover_id = form.cover?.id ?? null;
    else if (field === "related") sent.related = form.related.map((each) => each.id);
    else if (field === "category" || field === "author_id") sent[field] = form[field] || null;
    else if (field === "search_title" || field === "search_description") sent[field] = form[field].trim() || null;
    else if (field === "title" || field === "summary") sent[field] = form[field].trim();
    else if (field === "slug") {
      if (form.slug) sent.slug = form.slug; // empty, a new post's comes from its title
    } else sent[field] = form[field];
  }
  return sent;
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

/** The body's opening words, roughly as the server makes them, for the description's placeholder. */
export function openingWords(markdown: string, limit = 160): string {
  const words = markdown
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[#>*_`~-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (words.length <= limit) return words;
  const cut = words.slice(0, limit - 1);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), 1)).trimEnd()}…`;
}

/** What the person's own client checks before a save: a title, and a slug to the server's rule. */
export function problems(form: Form, isNew: boolean): Partial<Record<FormField, string>> {
  const found: Partial<Record<FormField, string>> = {};
  if (!form.title.trim()) found.title = "A post needs a title.";
  const blankAllowed = isNew && form.slug === "";
  if (!blankAllowed && (!SLUG.test(form.slug) || form.slug.length > MAX_SLUG)) {
    found.slug = "An address is lowercase letters, digits and single hyphens, such as spring-tour.";
  }
  return found;
}

/**
 * A save someone else got to first, as the kit's SaveConflict reads it: each
 * field both changed since `base`, to different values. Fields only they
 * changed are theirs, and only you, yours, with nothing to ask.
 */
export function conflictOf(detail: string, base: Form, mine: Form, theirs: Full): SettingsConflict {
  const now = formOf(theirs);
  const conflicts: FieldConflict[] = changed(mine, base)
    .filter((field) => !same(field, now[field], base[field]) && !same(field, now[field], mine[field]))
    .map((field) => ({ field, yours: mine[field], theirs: now[field] }));
  return { detail, version: theirs.version, conflicts, at: theirs.updated_at };
}

/** The form to save again: theirs, with each field the person changed kept as theirs only where they chose so. */
export function merged(base: Form, mine: Form, theirs: Full, keepTheirs: ReadonlySet<string>): Form {
  const next: Form = { ...formOf(theirs) };
  for (const field of changed(mine, base)) {
    if (!keepTheirs.has(field)) (next as Record<FormField, unknown>)[field] = mine[field];
  }
  return next;
}

/**
 * The fields once a save of `sent` is answered with `answer`: what the person
 * typed after the save went stays as typed, and the rest read as the server
 * has them (pages, Codex on #121).
 */
export function rebased(now: Form, sent: Form, answer: Form): Form {
  const next: Form = { ...answer };
  for (const field of Object.keys(now) as FormField[]) {
    if (!same(field, now[field], sent[field])) (next as Record<FormField, unknown>)[field] = now[field];
  }
  return next;
}

/** A value of a field as the conflict dialog says it. */
export function said(field: FormField, value: unknown, names: ReadonlyMap<string, string>): string {
  if (field === "cover") return (value as Cover | null) ? ((value as Cover).alt ?? "An image") : "No cover";
  if (field === "related") {
    const picks = value as RelatedPick[];
    return picks.length ? picks.map((each) => each.title).join(", ") : "None";
  }
  if (typeof value === "boolean") return value ? "On" : "Off";
  const text = typeof value === "string" ? value : "";
  if (field === "body") return openingWords(text, 120);
  if (field === "category" || field === "author_id") return names.get(text) ?? (text || "None");
  return text;
}
