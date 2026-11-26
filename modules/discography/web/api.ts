// discography's typed client (decision 0042): its paths from
// modules/discography/openapi.json, made into schema.ts by `npm run api:types`.
// No fetch() in components. The words and limits every page shares live here.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

type Schemas = components["schemas"];
export type ReleaseCard = Schemas["ReleaseCard"];
export type ReleaseCards = Schemas["ReleaseCards"];
export type LiveRelease = Schemas["LiveRelease"];
export type LiveTrack = Schemas["LiveTrack"];
export type TrackLine = Schemas["TrackLine"];
export type TrackCard = Schemas["TrackCard"];
export type TrackRelease = Schemas["TrackRelease"];
export type MusicMoved = Schemas["MusicMoved"];
export type MusicCover = Schemas["MusicCover"];
export type MusicCredit = Schemas["MusicCredit"];
export type MusicLink = Schemas["MusicLink"];
export type AdminRelease = Schemas["AdminRelease"];
export type FullRelease = Schemas["FullRelease"];
export type AdminTrack = Schemas["AdminTrack"];
export type FullTrack = Schemas["FullTrack"];
export type TrackAudio = Schemas["TrackAudio"];
export type AdminCredit = Schemas["AdminCredit"];
export type AdminPerson = Schemas["AdminPerson"];
export type AdminRole = Schemas["AdminRole"];
export type NewRelease = Schemas["NewRelease"];
export type ReleaseChange = Schemas["ReleaseChange"];
export type TrackChange = Schemas["TrackChange"];
export type PlaysWeek = Schemas["PlaysWeek"];
export type Kind = ReleaseCard["kind"];
export type Status = AdminRelease["status"];
export type Profile = AdminPerson["profile"];

/** Where the lists live, for TanStack Query's keys and invalidation. */
export const RELEASES = "/api/discography/admin/releases";
export const RELEASE = "/api/discography/admin/releases/{release_id}";
export const TRACKS = "/api/discography/admin/tracks";
export const TRACK = "/api/discography/admin/tracks/{track_id}";
export const PEOPLE = "/api/discography/admin/people";
export const ROLES = "/api/discography/admin/roles";
export const LINKS = "/api/discography/admin/links";
export const PUBLIC_RELEASES = "/api/discography/releases";
export const PLAYS = "/api/discography/admin/plays";
export const PUBLIC_TRACKS = "/api/discography/tracks";

/** Who may manage the library, and who may change the Music settings (the kernel's settings routes). */
export const MANAGE = "discography.release.manage";
export const SETTINGS = "kernel.settings.manage";

/** A master's largest size: the route's 64 MB holds it and the form's own bytes. */
export const MAX_MASTER_BYTES = 60 * 1024 * 1024;
/** What the site says of a file over it, before it's sent. */
export const TOO_LARGE = "The file is over 60 MB. Export it as FLAC: it keeps every bit at about half the size.";
/** The masters libsndfile reads (decision 0070): no M4A or ALAC. */
export const ACCEPT = ".wav,.wave,.aif,.aiff,.flac,.ogg,.oga,.mp3,audio/wav,audio/x-wav,audio/aiff,audio/flac,audio/ogg,audio/mpeg";

export const MAX_TITLE = 200;
export const MAX_SLUG = 80;
export const MAX_ARTIST = 200;
export const MAX_LINE = 300;
export const MAX_LYRICS = 20_000;
export const MAX_NAME = 120;
export const MAX_ROLE = 60;
export const MAX_URL = 500;
/** A slug: lowercase letters and digits, single hyphens between (the server's rule). */
export const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export const KIND_WORDS: Record<Kind, string> = { album: "Album", ep: "EP", single: "Single" };
export const STATUS_WORDS: Record<Status, string> = { draft: "Draft", scheduled: "Scheduled", published: "Live" };
export const STATUS_TONE = { draft: "neutral", scheduled: "info", published: "success" } as const;
export const PROFILE_WORDS: Record<Profile, string> = {
  unlinked: "Not linked",
  collective: "The collective",
  member: "A member's profile",
  not_member: "Not a member",
};

/** A length as a tracklist shows it: 3:42, or 1:02:05 past the hour. */
export function clock(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "--";
  const total = Math.round(ms / 1000);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return hours ? `${String(hours)}:${String(minutes).padStart(2, "0")}:${seconds}` : `${String(minutes)}:${seconds}`;
}

/** A typed length, "3:42" or "1:02:05", as milliseconds; null for anything else. */
export function msOf(words: string): number | null {
  const parts = words.trim().split(":");
  if (parts.length < 2 || parts.length > 3 || parts.some((part) => !/^\d+$/.test(part))) return null;
  const numbers = parts.map(Number);
  const [seconds = 0, minutes = 0, hours = 0] = [...numbers].reverse();
  if (seconds > 59 || (parts.length === 3 && minutes > 59)) return null;
  return ((hours * 60 + minutes) * 60 + seconds) * 1000;
}

/** A release's line under its title: "Album, 2024. 15 tracks". */
export function releaseLine(release: { kind: Kind; year: number | null; track_count: number; tracklist_to_come: boolean }): string {
  const kind = release.year ? `${KIND_WORDS[release.kind]}, ${String(release.year)}` : KIND_WORDS[release.kind];
  const count = release.track_count === 1 ? "1 track" : `${String(release.track_count)} tracks`;
  return `${kind}. ${release.tracklist_to_come ? `${count} for now` : count}`;
}

/** How a track's audio reads in a table: "Upload", "SoundCloud", "Making the stream file 64%". */
export function audioWords(audio: TrackAudio): string {
  if (audio.state === "processing") return audio.percent ? `Making the stream file ${String(audio.percent)}%` : "Making the stream file";
  if (audio.state === "failed") return audio.plays_from === "soundcloud" ? "SoundCloud (the upload failed)" : "The upload failed";
  if (audio.plays_from === "upload") return "Upload";
  if (audio.plays_from === "soundcloud") return audio.soundcloud_kind === "set" ? "SoundCloud playlist" : "SoundCloud";
  return "No audio yet";
}

/** A track's state as its Status column says it. */
export function trackState(audio: TrackAudio): { label: string; tone: "success" | "info" | "danger" } {
  if (audio.plays_from) return { label: "Live", tone: "success" };
  if (audio.state === "processing") return { label: "Processing", tone: "info" };
  return { label: "Can't play", tone: "danger" };
}

/** Why a file can't be sent, before it is: its size; null when it may go. */
export function fileProblem(file: File): string | null {
  return file.size > MAX_MASTER_BYTES ? `${file.name}: ${TOO_LARGE}` : null;
}

/** A master as a form sends it: the upload routes take multipart `file`. */
export function asForm(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}

/** A new track at the end of the release from `file`, refused here when it's too large to send. */
export async function uploadTrack(releaseId: string, file: File): Promise<FullTrack> {
  const problem = fileProblem(file);
  if (problem) throw new Error(problem);
  const { data } = await api.POST("/api/discography/admin/releases/{release_id}/tracks/upload", {
    params: { path: { release_id: releaseId } },
    body: { file: file as unknown as string },
    bodySerializer: () => asForm(file),
  });
  if (!data) throw new Error("The site answered without the track.");
  return data;
}

/** A new master for the track: the old stream plays until the new one is ready. */
export async function replaceAudio(trackId: string, file: File): Promise<FullTrack> {
  const problem = fileProblem(file);
  if (problem) throw new Error(problem);
  const { data } = await api.PUT("/api/discography/admin/tracks/{track_id}/audio", {
    params: { path: { track_id: trackId } },
    body: { file: file as unknown as string },
    bodySerializer: () => asForm(file),
  });
  if (!data) throw new Error("The site answered without the track.");
  return data;
}

/** A release's page on the site, or one of its tracks'. */
export function pathOf(release: string, track?: string): string {
  return track ? `/music/${release}/${track}` : `/music/${release}`;
}
