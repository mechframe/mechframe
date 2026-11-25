// social's typed client (decision 0042): its paths from modules/social/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type Channel = components["schemas"]["SocialChannel"];
export type Share = components["schemas"]["SocialShare"];
export type ShareView = components["schemas"]["ShareView"];
export type TokenState = components["schemas"]["TokenState"];
export type Mode = Share["mode"];
export type State = Share["state"];

/** Where the answers live, for TanStack Query's keys and invalidation. */
export const STATE = "/api/social/admin/state";
export const SHARES = "/api/social/admin/shares";
export const SEND_PERMISSION = "social.post.send";

/** A share's state as the card names it. */
export const STATE_WORDS: Record<State, string> = {
  sending: "Not confirmed",
  unknown: "Not confirmed",
  queued: "Queued in Buffer",
  draft: "A draft in Buffer",
  sent: "Sent",
  failed: "Failed in Buffer",
  refused: "Not taken",
  removed: "Taken back",
};

export const STATE_TONE = {
  sending: "warning",
  unknown: "warning",
  queued: "info",
  draft: "neutral",
  sent: "success",
  failed: "danger",
  refused: "danger",
  removed: "neutral",
} as const;

export const MODE_WORDS: Record<Mode, string> = {
  queue: "Buffer's queue for each channel",
  now: "Now",
  at: "At a set time",
  draft: "A draft in Buffer, to schedule there",
};

/** A day and a time: "24 November 2026, 09:00". */
export function dayAndTime(at: string): string {
  return new Date(at).toLocaleString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** The text's length as the channel counts it: the link added at its end, unless the network shows it as a card or the text has it. */
export function lengthFor(channel: Channel, text: string, link: string): number {
  if (channel.service === "linkedin" || text.includes(link)) return text.length;
  return text.length + 2 + link.length;
}

/** Where the token in use comes from, as the Settings section says it. */
export function sourceWords(source: TokenState["source"]): string {
  if (source === "saved") return "Sharing uses the Buffer token saved here.";
  if (source === "host") return "Sharing uses the host's token, BUFFER_ACCESS_TOKEN. A token saved here would be used instead.";
  return "No Buffer token is set, so sharing is off. Save one here, or set BUFFER_ACCESS_TOKEN on the host.";
}
