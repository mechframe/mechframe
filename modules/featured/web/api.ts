// featured's typed client (decision 0042): its paths from modules/featured/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components. The words
// Players, its dialogs and the Dashboard's card share live here, with the state
// each row of an unsaved list is in, worked out as the server works it out.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation, apiQueryOptions } = createApiClient<paths>();

type Schemas = components["schemas"];
export type LiveSlot = Schemas["LiveSlot"];
export type LivePlacement = Schemas["LivePlacement"];
export type AdminSlot = Schemas["AdminSlot"];
export type AdminSlots = Schemas["AdminSlots"];
export type FullSlot = Schemas["FullSlot"];
export type AdminPlacement = Schemas["AdminPlacement"];
export type AdminRef = Schemas["AdminRef"];
export type RefChoices = Schemas["RefChoices"];
export type PastedLinks = Schemas["PastedLinks"];
export type FoundVideo = Schemas["FoundVideo"];
export type TypeLabel = Schemas["TypeLabel"];
export type Kind = Schemas["Kind"];
export type LinkShown = Schemas["LinkShown"];
export type State = AdminPlacement["state"];

/** Where the lists live, for TanStack Query's keys and invalidation. */
export const SLOTS = "/api/featured/admin/slots";
export const SLOT = "/api/featured/admin/slots/{key}";
export const LIVE = "/api/featured/slots/{key}";

/** Who may choose what plays, and who may make, change and remove players. */
export const PLACE = "featured.placement.manage";
export const SLOT_MANAGE = "featured.slot.manage";
/** What a slot takes for YouTube's links, beside the modules' types. */
export const YOUTUBE = "youtube";

export const MAX_PLACEMENTS = 100;
export const MAX_TITLE = 200;
export const MAX_LABEL = 60;
export const MAX_KEY = 40;
export const MAX_KINDS = 12;
export const MAX_PASTE = 20;
export const KEY_PATTERN = "^[a-z0-9]+(-[a-z0-9]+)*$";

/** "Nov 17", in the viewer's own zone. */
export function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** "Nov 17, 12:00 AM". */
export function dayTime(iso: string): string {
  const at = new Date(iso);
  return `${day(iso)}, ${at.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
}

/** A row's dates as the board says them: "Nov 10 to Nov 17", "Starts Nov 17, 12:00 AM", "No end date", "Until Nov 17" or "Always". */
export function datesWords(starts: string | null, ends: string | null, now: number = Date.now()): string {
  if (starts && ends) return `${day(starts)} to ${day(ends)}`;
  if (starts) return Date.parse(starts) > now ? `Starts ${dayTime(starts)}` : "No end date";
  if (ends) return `Until ${day(ends)}`;
  return "Always";
}

/** Each state's pill, in the board's words. */
export const PILLS: Record<State, { label: string; tone: "neutral" | "success" | "warning" | "danger" | "info" }> = {
  live: { label: "Live now", tone: "success" },
  next: { label: "Up next", tone: "info" },
  scheduled: { label: "Scheduled", tone: "neutral" },
  ended: { label: "Ended", tone: "neutral" },
  hidden: { label: "Not on the site", tone: "warning" },
  removed: { label: "This item was removed", tone: "danger" },
};

/** "Tracks" as one: "track"; "Stories" as "story". */
export function singular(label: string): string {
  const word = label.toLowerCase();
  if (word.endsWith("ies")) return `${word.slice(0, -3)}y`;
  if (word.endsWith("s") && !word.endsWith("ss")) return word.slice(0, -1);
  return word;
}

/** "a track", "an album". */
export function oneOf(label: string): string {
  const word = singular(label);
  return `${/^[aeiou]/.test(word) ? "an" : "a"} ${word}`;
}

/** "Tracks, albums and YouTube links". */
export function listed(words: readonly string[]): string {
  if (words.length <= 1) return words[0] ?? "";
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1] ?? ""}`;
}

/** A type's label, from the types the modules on give; the type itself while its module is off. */
export function labelOf(types: readonly TypeLabel[], type: string): string {
  return types.find((each) => each.type === type)?.label ?? type;
}

/** What a tab says the slot takes, as the board's three do. */
export function intro(slot: Pick<AdminSlot, "accepts" | "kinds">, types: readonly TypeLabel[]): string {
  const things = slot.accepts.filter((each) => each !== YOUTUBE).map((each) => labelOf(types, each));
  const links = slot.accepts.includes(YOUTUBE);
  const named = listed([...things.map((each, at) => (at === 0 ? each : each.toLowerCase())), ...(links ? ["YouTube links"] : [])]);
  const words = [`${named}, in order.`];
  if (things.length) words.push(`Give ${oneOf(things[0] ?? "item")} dates to schedule it.`);
  if (links) words.push("Paste one or several links at once; titles fill in from YouTube.");
  if (links && slot.kinds.length) words.push("Give each video one of this player's kinds.");
  return words.join(" ");
}

// --- a list being edited ----------------------------------------------------------------------

/** One row of the list on the screen: a saved placement as it is or changed, or a new one. */
export type Row = {
  /** The saved placement's id, or null for a new one. */
  id: string | null;
  /** A key the screen keeps for the row, saved or not. */
  key: string;
  item: { type: string; id: string } | null;
  ref: AdminRef | null;
  removed: boolean;
  link: { url: string; video_id: string; title: string; kind: string | null } | null;
  starts_at: string | null;
  ends_at: string | null;
};

export function rowOf(placement: AdminPlacement): Row {
  return {
    id: placement.id,
    key: placement.id,
    item: placement.item,
    ref: placement.ref,
    removed: placement.removed,
    link: placement.link ? { ...placement.link } : null,
    starts_at: placement.starts_at,
    ends_at: placement.ends_at,
  };
}

/** A row's title: its item's, its link's, or what's known of an item that's gone or off. */
export function titleOf(row: Row): string {
  if (row.ref) return row.ref.title;
  if (row.link) return row.link.title || "A video with no title";
  return row.removed ? "An item that was removed" : "An item from a part of the site that's off";
}

/** Each row's state now, as the server works it out: gone, over, not on the site, live, or to come (the soonest `next`). */
export function statesOf(rows: readonly Row[], now: number = Date.now()): State[] {
  const states: (State | "upcoming")[] = rows.map((row) => {
    if (row.item && !row.ref) return row.removed ? "removed" : "hidden";
    if (row.ends_at && Date.parse(row.ends_at) <= now) return "ended";
    if (row.ref && !row.ref.live) return "hidden";
    if (row.starts_at && Date.parse(row.starts_at) > now) return "upcoming";
    return "live";
  });
  let soonest = -1;
  states.forEach((state, at) => {
    if (state !== "upcoming") return;
    const starts = Date.parse(rows[at]?.starts_at ?? "");
    if (soonest < 0 || starts < Date.parse(rows[soonest]?.starts_at ?? "")) soonest = at;
  });
  return states.map((state, at) => (state === "upcoming" ? (at === soonest ? "next" : "scheduled") : state));
}

/** What a save sends for the rows: each kept placement's id, an item's type and id, or a link. */
export function bodyOf(rows: readonly Row[]) {
  return rows.map((row) => ({
    ...(row.id ? { id: row.id } : {}),
    ...(row.item ? { ref: { type: row.item.type, id: row.item.id } } : {}),
    ...(row.link ? { link: { url: row.link.url, title: row.link.title, kind: row.link.kind } } : {}),
    starts_at: row.starts_at,
    ends_at: row.ends_at,
  }));
}

/** What's changed from the saved list, each in a few words, what's added first as the board has it: "Hook It Up added", "Gather Around scheduled", "The order changed". */
export function changesOf(saved: readonly Row[], rows: readonly Row[]): string[] {
  const added: string[] = [];
  const changed: string[] = [];
  const before = new Map(saved.map((row) => [row.id, row]));
  for (const row of rows) {
    const was = row.id ? before.get(row.id) : undefined;
    if (!was) {
      added.push(`${titleOf(row)} added`);
      continue;
    }
    if (was.starts_at !== row.starts_at || was.ends_at !== row.ends_at) changed.push(row.starts_at || row.ends_at ? `${titleOf(row)} scheduled` : `${titleOf(row)}'s dates cleared`);
    if (was.link && row.link && was.link.title !== row.link.title) changed.push(`${titleOf(was)} renamed`);
    if (was.link && row.link && was.link.kind !== row.link.kind) changed.push(`${titleOf(row)}'s kind changed`);
  }
  const kept = new Set(rows.map((row) => row.id));
  const removed = saved.filter((row) => !kept.has(row.id)).map((row) => `${titleOf(row)} removed`);
  const order = (list: readonly Row[]) => list.filter((row) => row.id && kept.has(row.id) && before.has(row.id)).map((row) => row.id);
  const moved = order(saved).join() !== order(rows).join() ? ["The order changed"] : [];
  return [...added, ...changed, ...removed, ...moved];
}

/** The strip's two lines for a saved slot: "Catalyst (full album), until Nov 17" and "Up next: Gather Around on Nov 17". */
export function stripOf(slot: FullSlot): { now: string; next: string } {
  const live = slot.items.filter((each) => each.state === "live").map(rowOf);
  const next = slot.items.find((each) => each.state === "next");
  const first = live[0];
  let now = "Nothing live";
  if (first) {
    if (first.ends_at) now = `${titleOf(first)}, until ${day(first.ends_at)}`;
    else if (live.length === 1) now = titleOf(first);
    else now = `${titleOf(first)}, then ${titleOf(live[1] as Row)}${live.length > 2 ? `, and ${String(live.length - 2)} more` : ""}`;
  }
  return { now, next: next?.starts_at ? `Up next: ${titleOf(rowOf(next))} on ${day(next.starts_at)}` : "Nothing scheduled" };
}

/** The Dashboard card's line: "Live since Nov 10, with 2 more queued". */
export function liveLine(slot: AdminSlot): string {
  const more = slot.counts.live - 1 + slot.counts.scheduled;
  const queued = more > 0 ? `, with ${String(more)} more queued` : "";
  return slot.now?.starts_at ? `Live since ${day(slot.now.starts_at)}${queued}` : `Live now${queued}`;
}
