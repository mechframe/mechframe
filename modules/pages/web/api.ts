// pages' typed client (decision 0042): its paths from modules/pages/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient, type LinkEntry } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type Full = components["schemas"]["Full"];
export type Listed = components["schemas"]["Listed"];
export type LivePage = components["schemas"]["LivePage"];
export type NewPage = components["schemas"]["NewPage"];
export type Change = components["schemas"]["PageChange"];
export type Status = Listed["status"];

/** Where the admin's list lives, for TanStack Query's keys and invalidation. */
export const LIST = "/api/pages/admin/pages";
export const ONE = "/api/pages/admin/pages/{page_id}";

/** The live pages in the header's menu or the footer's, as a link slot holds them (decision 0056). */
export async function menu(place: "header" | "footer"): Promise<LinkEntry[]> {
  const { data } = await api.GET("/api/pages/menu", { params: { query: { place } } });
  return (data ?? []).map((link) => ({ label: link.title, to: link.address }));
}

/** The HTML the site would draw for `body`, saved or not. */
export async function preview(body: string): Promise<string> {
  const { data } = await api.POST("/api/pages/admin/preview", { body: { body } });
  return data?.html ?? "";
}

/** How a page's state reads in the admin. */
export const STATUS_WORDS: Record<Status, string> = { draft: "Draft", scheduled: "Scheduled", published: "Live" };

/** The menus a page is in, in words. */
export function menuWords(page: Pick<Listed, "in_header" | "in_footer">): string {
  if (page.in_header && page.in_footer) return "Header and footer";
  if (page.in_header) return "Header";
  if (page.in_footer) return "Footer";
  return "Not in a menu";
}

/** The address of the privacy page "Needs you" asks for. */
export const PRIVACY = "/privacy";
