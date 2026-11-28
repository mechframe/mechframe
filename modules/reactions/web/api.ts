// reactions' typed client (decision 0042): its paths from modules/reactions/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery } = createApiClient<paths>();

export type Reactions = components["schemas"]["Reactions"];
export type Counted = components["schemas"]["Counted"];

/** Where the counts live, for TanStack Query's keys. */
export const READ = "/api/reactions";
export const PRESS = "/api/reactions/{type}/{id}/{key}";

/** The read of one thing's row, as its query key holds it. */
export function readOf(type: string, id: string) {
  return { params: { query: { type, id: [id] } } };
}
