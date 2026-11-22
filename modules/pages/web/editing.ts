// The editor's form and what a save sends (`dev plans/contracts/pages.md` §2):
// the page as its fields hold it, the changes from what's saved, and the
// three-way merge a save someone else got to first asks for.
import type { FieldConflict, SettingsConflict } from "@/kernel";

import type { Change, Full } from "./api";

export type Menu = "none" | "header" | "footer" | "both";

export type Form = {
  title: string;
  address: string;
  body: string;
  search_title: string;
  search_description: string;
  menu: Menu;
  menu_order: number;
};

export type FormField = keyof Form;

export const LABELS: Record<FormField, string> = {
  title: "Title",
  address: "Address",
  body: "Page body",
  search_title: "Title in search results",
  search_description: "Description",
  menu: "Menu",
  menu_order: "Place in the menu",
};

export const MENUS: readonly { value: Menu; label: string }[] = [
  { value: "none", label: "Not in a menu" },
  { value: "header", label: "Header" },
  { value: "footer", label: "Footer" },
  { value: "both", label: "Header and footer" },
];

/** An address is one segment: lowercase letters and digits, single hyphens between (the server's rule). */
export const ADDRESS = /^\/[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const MAX_ADDRESS = 60;
export const MAX_TITLE = 120;
export const MAX_BODY = 100_000;

export const BLANK: Form = {
  title: "",
  address: "",
  body: "",
  search_title: "",
  search_description: "",
  menu: "none",
  menu_order: 0,
};

/** The privacy page "Needs you" asks for: its address and a few headings to fill. */
export const PRIVACY_START: Form = {
  ...BLANK,
  title: "Privacy",
  address: "/privacy",
  menu: "footer",
  body: [
    "What this site collects about you, why, and what you can do about it.",
    "## What we collect",
    "## How we use it",
    "## Who we share it with",
    "## How long we keep it",
    "## Your choices",
    "## How to reach us",
  ].join("\n\n"),
};

function menuOf(page: Pick<Full, "in_header" | "in_footer">): Menu {
  if (page.in_header && page.in_footer) return "both";
  if (page.in_header) return "header";
  return page.in_footer ? "footer" : "none";
}

export function formOf(page: Full): Form {
  return {
    title: page.title,
    address: page.address,
    body: page.body,
    search_title: page.search_title ?? "",
    search_description: page.search_description ?? "",
    menu: menuOf(page),
    menu_order: page.menu_order,
  };
}

/** The fields the person changed from `base`. */
export function changed(form: Form, base: Form): FormField[] {
  return (Object.keys(form) as FormField[]).filter((field) => form[field] !== base[field]);
}

/** What a save sends for `fields` of `form`: the menu as its two switches, an empty search word as none. */
export function body(form: Form, fields: readonly FormField[]): Omit<Change, "version"> {
  const sent: Record<string, unknown> = {};
  for (const field of fields) {
    if (field === "menu") {
      sent.in_header = form.menu === "header" || form.menu === "both";
      sent.in_footer = form.menu === "footer" || form.menu === "both";
    } else if (field === "search_title" || field === "search_description") {
      sent[field] = form[field].trim() || null;
    } else if (field === "title") {
      sent.title = form.title.trim();
    } else {
      sent[field] = form[field];
    }
  }
  return sent;
}

/** An address made from a title, for a new page whose address nobody has typed: "Press kit" is /press-kit. */
export function addressFor(title: string): string {
  const words = title
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, MAX_ADDRESS - 1)
    .replace(/-+$/, "");
  return words ? `/${words}` : "";
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

/** What the person's own client checks before a save: a title, and an address to the server's rule. */
export function problems(form: Form): Partial<Record<FormField, string>> {
  const found: Partial<Record<FormField, string>> = {};
  if (!form.title.trim()) found.title = "A page needs a title.";
  if (!ADDRESS.test(form.address) || form.address.length > MAX_ADDRESS) {
    found.address = "An address is a slash, then lowercase letters, digits and single hyphens, such as /press-kit.";
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
    .filter((field) => now[field] !== base[field] && now[field] !== mine[field])
    .map((field) => ({ field, yours: mine[field], theirs: now[field] }));
  return { detail, version: theirs.version, conflicts, at: theirs.updated_at };
}

/** The form to save again: theirs, with each field the person changed kept as theirs only where they chose so. */
export function merged(base: Form, mine: Form, theirs: Full, keepTheirs: ReadonlySet<string>): Form {
  const now = formOf(theirs);
  const next: Form = { ...now };
  for (const field of changed(mine, base)) {
    if (!keepTheirs.has(field)) (next as Record<FormField, unknown>)[field] = mine[field];
  }
  return next;
}
