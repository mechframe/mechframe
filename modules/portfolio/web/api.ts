// portfolio's typed client (decision 0042): its paths from modules/portfolio/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type AdminPiece = components["schemas"]["AdminPiece"];
export type AdminPieceList = components["schemas"]["AdminPieceList"];
export type Card = components["schemas"]["PieceCard"];
export type Cards = components["schemas"]["PieceCards"];
export type LivePiece = components["schemas"]["LivePiece"];
export type Discipline = components["schemas"]["Discipline"];
export type AdminDiscipline = components["schemas"]["AdminDiscipline"];
export type Picture = components["schemas"]["PiecePicture"];
export type Video = components["schemas"]["PieceVideo"];
export type Person = components["schemas"]["PortfolioPerson"];
export type NewPiece = components["schemas"]["NewPiece"];
export type Change = components["schemas"]["PieceChange"];
export type Status = AdminPiece["status"];

/** The two permissions (decision 0074): your own pieces, and every piece. */
export const ADD = "portfolio.piece.add";
export const MANAGE = "portfolio.piece.manage";

/** Where the reads live, for TanStack Query's keys and invalidation. */
export const LIST = "/api/portfolio/admin/pieces";
export const ONE = "/api/portfolio/admin/pieces/{piece_id}";
export const DISCIPLINES = "/api/portfolio/admin/disciplines";
export const ARTISTS = "/api/portfolio/admin/artists";
export const PUBLIC_LIST = "/api/portfolio/pieces";
export const PUBLIC_DISCIPLINES = "/api/portfolio/disciplines";

/** The Art page, and a piece's page on the site. */
export const ART = "/art";
export function pathOf(slug: string): string {
  return `${ART}/piece/${slug}`;
}

/** "Graphic design, by petro, 2026", leaving out what it hasn't got (the server's `line`). */
export function lineOf(card: { discipline: Discipline | null; artist: string | null; year: number | null }): string {
  const parts: string[] = [];
  if (card.discipline) parts.push(card.discipline.label);
  if (card.artist) parts.push(`by ${card.artist}`);
  if (card.year) parts.push(String(card.year));
  return parts.join(", ");
}

/** "By petro, 2026", the panel's byline, leaving out what it hasn't got. */
export function bylineOf(card: { artist: string | null; year: number | null }): string {
  const parts: string[] = [];
  if (card.artist) parts.push(`By ${card.artist}`);
  if (card.year) parts.push(String(card.year));
  return parts.join(", ");
}

/** The disciplines' labels as one line: "Paintings, graphic design, animation and video". */
export function joined(labels: readonly string[]): string {
  const [first, ...rest] = labels;
  if (first === undefined) return "";
  const words = [first, ...rest.map((each) => each.toLowerCase())];
  if (words.length === 1) return first;
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1] ?? ""}`;
}

/** How a piece's state reads in the admin; a live piece needs no pill. */
export const STATUS_WORDS: Record<Status, string> = { draft: "Draft", scheduled: "Scheduled", published: "Live" };
