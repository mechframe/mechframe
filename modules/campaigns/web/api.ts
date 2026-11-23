// campaigns' typed client (decision 0042): its paths from modules/campaigns/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type CampaignEmail = components["schemas"]["CampaignEmail"];
export type CampaignEmailItem = components["schemas"]["CampaignEmailItem"];
export type EmailsPage = components["schemas"]["CampaignEmailsPage"];
export type Subscriber = components["schemas"]["NewsletterSubscriber"];
export type SetAsideAddress = components["schemas"]["SetAsideAddress"];
export type NewSubscription = components["schemas"]["NewSubscription"];
export type SubscriptionLink = components["schemas"]["SubscriptionLink"];
export type Kind = CampaignEmail["kind"];
export type EmailStatus = CampaignEmail["status"];
export type SubscriberStatus = Subscriber["status"];
export type Why = SetAsideAddress["why"];

/** Where the answers live, for TanStack Query's keys and invalidation. */
export const SIGNUP = "/api/campaigns/signup";
export const EMAILS = "/api/campaigns/admin/emails";
export const ONE = "/api/campaigns/admin/emails/{email_id}";
export const SUBSCRIBERS = "/api/campaigns/admin/subscribers";
export const SET_ASIDE = "/api/campaigns/admin/set-aside";
export const EMAIL_PERMISSION = "campaigns.email.manage";
export const SUBSCRIBER_PERMISSION = "campaigns.subscriber.manage";

export const KIND_WORDS: Record<Kind, string> = { newsletter: "Newsletter", release: "Release announcement" };
export const STATUS_WORDS: Record<EmailStatus, string> = { draft: "Draft", scheduled: "Scheduled", sending: "Sending", sent: "Sent" };
export const STATUS_TONE = { draft: "neutral", scheduled: "info", sending: "warning", sent: "success" } as const;
export const SUBSCRIBER_WORDS: Record<SubscriberStatus, string> = {
  pending: "Waiting to confirm",
  subscribed: "Subscribed",
  unsubscribed: "Unsubscribed",
};
export const SUBSCRIBER_TONE = { pending: "warning", subscribed: "success", unsubscribed: "neutral" } as const;

/** Where a person signed up, in words: the board's "The footer form", "The contact form". */
export function sourceWords(source: string): string {
  if (source === "form") return "A sign-up form";
  if (source === "contact") return "The contact form";
  if (source === "blog") return "The blog";
  return source.replaceAll("-", " ").replace(/^./, (first) => first.toUpperCase());
}

/** Why an address is set aside, in words: the board's "Bounced: the address doesn't exist". */
export function whyWords(why: Why, detail: string): string {
  if (why === "complained") return "Marked a newsletter as spam";
  if (why === "unsubscribed") return "Unsubscribed";
  const code = /\b5\.1\.(\d+)\b/.exec(detail)?.[1];
  if (code === "1" || code === "0" || code === "10") return "Bounced: the address doesn't exist";
  if (code === "2") return "Bounced: the domain doesn't exist";
  return "Bounced";
}

/** A day as an admin reads it: "22 November 2026". */
export function day(at: string): string {
  return new Date(at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}

/** A day and a time: "22 November 2026, 09:00". */
export function dayAndTime(at: string): string {
  return new Date(at).toLocaleString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "1 person", "3 people". */
export function people(count: number): string {
  return count === 1 ? "1 person" : `${count.toLocaleString()} people`;
}

/** The email's HTML a subscriber reads, for the editor's Preview: unsaved words included. */
export async function preview(id: string, body: string): Promise<string> {
  const { data } = await api.POST("/api/campaigns/admin/emails/{email_id}/preview", {
    params: { path: { email_id: id } },
    body: { body },
  });
  return data?.html ?? "";
}
