// audio-player's typed client (decision 0042): its one path from
// modules/audio-player/openapi.json, made into schema.ts by `npm run api:types`.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type PlayerSettingsAnswer = components["schemas"]["PlayerSettings"];

export const SETTINGS = "/api/audio-player/settings";
