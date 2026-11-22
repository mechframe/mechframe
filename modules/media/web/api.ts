// media's typed client (decision 0042): its paths from modules/media/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type Image = components["schemas"]["Image"];
export type ImagePage = components["schemas"]["ImagePage"];

/** Where the library's list lives, for TanStack Query's keys and invalidation. */
export const LIBRARY = "/api/media/admin/images";

/** A file as the multipart body an upload or a replace sends. */
export function fileBody(file: File): FormData {
  const form = new FormData();
  form.append("file", file);
  return form;
}
