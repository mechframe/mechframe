// blog's typed client (decision 0042): its paths from modules/blog/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type Full = components["schemas"]["FullPost"];
export type Listed = components["schemas"]["ListedPost"];
export type LivePost = components["schemas"]["LivePost"];
export type Card = components["schemas"]["PostCard"];
export type Cover = components["schemas"]["PostCover"];
export type NewPost = components["schemas"]["NewPost"];
export type Change = components["schemas"]["PostChange"];
export type AdminCategory = components["schemas"]["BlogAdminCategory"];
export type Person = components["schemas"]["BlogPerson"];
export type Status = Listed["status"];

/** Where the admin's lists live, for TanStack Query's keys and invalidation. */
export const LIST = "/api/blog/admin/posts";
export const ONE = "/api/blog/admin/posts/{post_id}";
export const CATEGORIES = "/api/blog/admin/categories";
export const PUBLIC_LIST = "/api/blog/posts";

/** The HTML the site would draw for `body`, saved or not. */
export async function preview(body: string): Promise<string> {
  const { data } = await api.POST("/api/blog/admin/preview", { body: { body } });
  return data?.html ?? "";
}

/** How a post's state reads in the admin. */
export const STATUS_WORDS: Record<Status, string> = { draft: "Draft", scheduled: "Scheduled", published: "Live" };
export const STATUS_TONE = { draft: "neutral", scheduled: "info", published: "success" } as const;

/** A day as a reader sees it: "22 November 2026". */
export function day(at: string): string {
  return new Date(at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

/** A post's page on the site. */
export function pathOf(slug: string): string {
  return `/blog/${slug}`;
}
