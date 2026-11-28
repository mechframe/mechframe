// The album editor's and the track panel's forms, and what a save sends
// (`dev plans/contracts/discography.md` §2): each row as its fields hold it, the
// changes from what's saved, and the three-way merge a save someone else got to
// first asks for. blog's `editing.ts` is the pattern, with the two crossed-save
// gaps closed (#123): a field typed after a save went is the person's, even back
// to what's saved, and a conflict reads the form as it is when it lands.
import type { FieldConflict, SettingsConflict } from "@/kernel";

import { SLUG, clock, msOf, type FullRelease, type FullTrack, type Kind, type MusicCover, type ReleaseChange, type TrackChange } from "./api";

export type CreditRow = { role_id: string; name: string };

export type ReleaseForm = {
  title: string;
  kind: Kind;
  slug: string;
  /** As typed: "" for none. */
  year: string;
  artist_line: string;
  credit_line: string;
  summary: string;
  /** The album's Bandcamp player: its embed code as pasted, or the link it's kept as. */
  bandcamp_url: string;
  cover: MusicCover | null;
  back_cover: MusicCover | null;
  tracklist_to_come: boolean;
  credits: CreditRow[];
  /** One address a row, as typed. */
  links: string[];
  /** The tracks' ids, in the order they play. */
  track_ids: string[];
};

export type TrackForm = {
  title: string;
  slug: string;
  explicit: boolean;
  lyrics: string;
  soundcloud_url: string;
  /** Its own Bandcamp player: its embed code as pasted, or the link it's kept as. */
  bandcamp_url: string;
  /** A length typed for a track that plays from its link alone: "3:42". */
  length: string;
  credits: CreditRow[];
};

type Value = string | boolean | MusicCover | null | CreditRow[] | string[];

export const RELEASE_LABELS: Record<keyof ReleaseForm, string> = {
  title: "Title",
  kind: "Kind",
  slug: "Address",
  year: "Year",
  artist_line: "Artist line",
  credit_line: "Credit",
  summary: "Summary",
  bandcamp_url: "Bandcamp player",
  cover: "Front cover",
  back_cover: "Back cover",
  tracklist_to_come: "Tracklist to come",
  credits: "Credits",
  links: "Streaming links",
  track_ids: "The tracks' order",
};

export const TRACK_LABELS: Record<keyof TrackForm, string> = {
  title: "Title",
  slug: "Address",
  explicit: "Explicit",
  lyrics: "Lyrics",
  soundcloud_url: "SoundCloud link",
  bandcamp_url: "Bandcamp player",
  length: "Length",
  credits: "Credits",
};

const creditsOf = (credits: readonly { role_id: string; name: string }[]): CreditRow[] => credits.map(({ role_id, name }) => ({ role_id, name }));

function lengthOf(track: FullTrack): string {
  const typed = track.audio.plays_from === "soundcloud" || track.audio.plays_from === "bandcamp";
  const ms = typed && track.audio.state !== "ready" ? track.audio.duration_ms : null;
  return ms === null ? "" : clock(ms);
}

export function releaseFormOf(release: FullRelease): ReleaseForm {
  return {
    title: release.title,
    kind: release.kind,
    slug: release.slug,
    year: release.year === null ? "" : String(release.year),
    artist_line: release.artist_line,
    credit_line: release.credit_line,
    summary: release.summary,
    bandcamp_url: release.bandcamp_url ?? "",
    cover: release.cover ?? null,
    back_cover: release.back_cover ?? null,
    tracklist_to_come: release.tracklist_to_come,
    credits: creditsOf(release.credits),
    links: release.links.map((each) => each.url),
    track_ids: release.tracks.map((each) => each.id),
  };
}

export function trackFormOf(track: FullTrack): TrackForm {
  return {
    title: track.title,
    slug: track.slug,
    explicit: track.explicit,
    lyrics: track.lyrics ?? "",
    soundcloud_url: track.audio.soundcloud_url ?? "",
    bandcamp_url: track.audio.bandcamp_url ?? "",
    length: lengthOf(track),
    credits: creditsOf(track.credits),
  };
}

/**
 * A field's value as it's compared: a cover by its image, lists by their rows in
 * order, links without blanks. A length that reads as one is its time, so 03:42
 * is 3:42; lyrics are as typed, blank or not (CodeRabbit on #145).
 */
function keyOf(field: string, value: Value): string | boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    if (field === "length") {
      const ms = msOf(value);
      return ms === null ? value.trim() : `ms:${String(ms)}`;
    }
    if (field === "lyrics") return value.trim() ? value : "";
    return value.trim();
  }
  if (value === null) return "";
  if (Array.isArray(value)) {
    const rows = value as (string | CreditRow)[];
    return JSON.stringify(field === "links" ? rows.map((each) => (each as string).trim()).filter(Boolean) : rows.map((each) => (typeof each === "string" ? each : [each.role_id, each.name.trim()])));
  }
  return value.id;
}

export function same(field: string, a: Value, b: Value): boolean {
  return keyOf(field, a) === keyOf(field, b);
}

/** The fields the person changed from `base`. */
export function changed<Form extends { [K in keyof Form]: Value }>(form: Form, base: Form): (keyof Form & string)[] {
  return (Object.keys(form) as (keyof Form & string)[]).filter((field) => !same(field, form[field], base[field]));
}

/** The fields the person changed: those that differ from `base`, and any typed after `sent` went, even back to what's saved. */
export function mineOf<Form extends { [K in keyof Form]: Value }>(now: Form, base: Form, sent?: Form): (keyof Form & string)[] {
  const found = new Set(changed(now, base));
  if (sent) for (const field of changed(now, sent)) found.add(field);
  return [...found];
}

/** Each field both changed since `base`, to different values, as the kit's SaveConflict reads it. */
export function conflictOf<Form extends { [K in keyof Form]: Value }>(
  detail: string,
  base: Form,
  mine: Form,
  now: Form,
  theirs: { version: number; updated_at?: string },
  fields: readonly (keyof Form & string)[],
): SettingsConflict {
  const conflicts: FieldConflict[] = fields
    .filter((field) => !same(field, now[field], base[field]) && !same(field, now[field], mine[field]))
    .map((field) => ({ field, yours: mine[field], theirs: now[field] }));
  return { detail, version: theirs.version, conflicts, at: theirs.updated_at ?? null };
}

/** Theirs, with each field the person changed kept as theirs only where they chose so. */
export function merged<Form extends { [K in keyof Form]: Value }>(mine: Form, now: Form, keepTheirs: ReadonlySet<string>, fields: readonly (keyof Form & string)[]): Form {
  const next: Form = { ...now };
  for (const field of fields) if (!keepTheirs.has(field)) next[field] = mine[field];
  return next;
}

/** The fields once a save of `sent` is answered with `answer`: what was typed after it went stays as typed. */
export function rebased<Form extends { [K in keyof Form]: Value }>(now: Form, sent: Form, answer: Form): Form {
  const next: Form = { ...answer };
  for (const field of Object.keys(now) as (keyof Form & string)[]) {
    if (!same(field, now[field], sent[field])) next[field] = now[field];
  }
  return next;
}

/**
 * The order with `id` past the next track shown above (-1) or below (1) it: by
 * id, as the form's order may hold a track the server no longer shows
 * (CodeRabbit on #145). Unchanged at either end.
 */
export function movedTrack(order: readonly string[], shown: readonly string[], id: string, by: -1 | 1): string[] {
  const neighbour = shown[shown.indexOf(id) + by];
  const from = order.indexOf(id);
  const to = neighbour === undefined ? -1 : order.indexOf(neighbour);
  if (from < 0 || to < 0 || shown.indexOf(id) < 0) return [...order];
  const next = [...order];
  next[from] = neighbour as string;
  next[to] = id;
  return next;
}

/** What a release's save sends for `fields`: covers by id, a year as a number, credits without blank rows. */
export function releaseBody(form: ReleaseForm, fields: readonly (keyof ReleaseForm)[]): Omit<ReleaseChange, "version"> {
  const sent: Record<string, unknown> = {};
  for (const field of fields) {
    if (field === "cover") sent.cover_id = form.cover?.id ?? null;
    else if (field === "back_cover") sent.back_cover_id = form.back_cover?.id ?? null;
    else if (field === "year") sent.year = form.year.trim() ? Number(form.year) : null;
    else if (field === "credits") sent.credits = rowsOf(form.credits);
    else if (field === "links") sent.links = form.links.map((each) => each.trim()).filter(Boolean);
    else if (field === "bandcamp_url") sent.bandcamp_url = form.bandcamp_url.trim() || null;
    else if (field === "track_ids" || field === "kind" || field === "tracklist_to_come") sent[field] = form[field];
    else sent[field] = form[field].trim();
  }
  return sent;
}

/** What a track's save sends for `fields`: an empty link or lyrics as none, a typed length in milliseconds. */
export function trackBody(form: TrackForm, fields: readonly (keyof TrackForm)[]): Omit<TrackChange, "version"> {
  const sent: Record<string, unknown> = {};
  for (const field of fields) {
    if (field === "credits") sent.credits = rowsOf(form.credits);
    else if (field === "length") sent.duration_ms = form.length.trim() ? msOf(form.length) : null;
    else if (field === "soundcloud_url") sent.soundcloud_url = form.soundcloud_url.trim() || null;
    else if (field === "bandcamp_url") sent.bandcamp_url = form.bandcamp_url.trim() || null;
    else if (field === "lyrics") sent.lyrics = form.lyrics.trim() ? form.lyrics : null;
    else if (field === "explicit") sent.explicit = form.explicit;
    else sent[field] = form[field].trim();
  }
  return sent;
}

/** Credit rows with a name; a row left blank isn't sent. */
export function rowsOf(rows: readonly CreditRow[]): CreditRow[] {
  return rows.filter((each) => each.name.trim()).map((each) => ({ role_id: each.role_id, name: each.name.trim() }));
}

/** What the person's own client checks before a release's save. */
export function releaseProblems(form: ReleaseForm): Partial<Record<keyof ReleaseForm, string>> {
  const found: Partial<Record<keyof ReleaseForm, string>> = {};
  if (!form.title.trim()) found.title = "A release needs a title.";
  if (!SLUG.test(form.slug)) found.slug = "An address is lowercase letters, digits and single hyphens, such as unified-vibration.";
  const year = form.year.trim();
  if (year && (!/^\d{4}$/.test(year) || Number(year) < 1900 || Number(year) > 2100)) found.year = "A year from 1900 to 2100, such as 2024.";
  if (form.credits.some((each) => each.name.trim() && !each.role_id)) found.credits = "Choose each credit's role.";
  return found;
}

/** What the person's own client checks before a track's save. */
export function trackProblems(form: TrackForm): Partial<Record<keyof TrackForm, string>> {
  const found: Partial<Record<keyof TrackForm, string>> = {};
  if (!form.title.trim()) found.title = "A track needs a title.";
  if (!SLUG.test(form.slug)) found.slug = "An address is lowercase letters, digits and single hyphens, such as night-drive.";
  if (form.length.trim() && msOf(form.length) === null) found.length = "A length as minutes and seconds, such as 3:42.";
  if (form.credits.some((each) => each.name.trim() && !each.role_id)) found.credits = "Choose each credit's role.";
  return found;
}

/** A value as the conflict dialog says it. */
export function said(value: unknown, roles: ReadonlyMap<string, string>): string {
  if (value === null) return "None";
  if (typeof value === "boolean") return value ? "On" : "Off";
  if (typeof value === "string") return value.trim() || "Empty";
  if (Array.isArray(value)) {
    const rows = value as (string | CreditRow)[];
    if (rows.length === 0) return "None";
    return rows.map((each) => (typeof each === "string" ? each : `${roles.get(each.role_id) ?? "A role"}: ${each.name}`)).join(", ");
  }
  return (value as MusicCover).alt ?? "An image";
}
