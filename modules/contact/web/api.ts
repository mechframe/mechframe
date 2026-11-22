// contact's typed client (decision 0042): its paths from modules/contact/openapi.json,
// made into schema.ts by `npm run api:types`. No fetch() in components.
import { createApiClient } from "@/kernel";

import type { components, paths } from "./schema";

export const { api, useApiQuery, useApiMutation } = createApiClient<paths>();

export type InboxItem = components["schemas"]["InboxItem"];
export type InboxMessage = components["schemas"]["InboxMessage"];
export type InboxPage = components["schemas"]["InboxPage"];
export type ContactForm = components["schemas"]["ContactForm"];
export type NewMessage = components["schemas"]["NewContactMessage"];
export type Status = InboxItem["status"];
export type Tab = "all" | Status;

/** Where the Inbox's answers live, for TanStack Query's keys and invalidation. */
export const FORM = "/api/contact/form";
export const LIST = "/api/contact/admin/messages";
export const ONE = "/api/contact/admin/messages/{message_id}";
export const PERMISSION = "contact.message.manage";

export const TABS: readonly { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "new", label: "New" },
  { id: "replied", label: "Replied" },
  { id: "archived", label: "Archived" },
  { id: "spam", label: "Spam" },
];

export const STATUS_WORDS: Record<Status, string> = { new: "New", replied: "Replied", archived: "Archived", spam: "Spam" };

/** Why a message was set apart as spam, in words (kernel.bot's reasons and the filters'). */
const REASONS: Readonly<Record<string, string>> = {
  honeypot: "It filled in the form's hidden trap",
  too_fast: "It was sent faster than a person types",
  not_from_form: "It wasn't sent from the form",
  provider_error: "The bot check couldn't be made",
  term: "It holds a word the site's filters hold",
  domain: "It links to a site the filters block",
  links: "It holds more links than the filters allow",
};

export function reasonWords(reason: string | null): string | null {
  if (reason === null) return null;
  return REASONS[reason] ?? `Held by the bot check (${reason})`;
}

/** A spreadsheet cell: quoted, and a formula's first character made plain text. */
function cell(value: string): string {
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return `"${safe.replaceAll('"', '""')}"`;
}

const COLUMNS: readonly [string, (message: InboxMessage) => string][] = [
  ["Received", (m) => m.received_at],
  ["Name", (m) => m.name],
  ["Email", (m) => m.email],
  ["Topic", (m) => m.topic_label],
  ["Status", (m) => STATUS_WORDS[m.status]],
  ["Wants the newsletter", (m) => (m.wants_news ? "Yes" : "No")],
  ["Message", (m) => m.message],
];

/** The Export's CSV, made here from the export's typed answer (every API answer is JSON). */
export function toCsv(messages: readonly InboxMessage[]): string {
  const rows = [COLUMNS.map(([header]) => cell(header)).join(",")];
  for (const message of messages) rows.push(COLUMNS.map(([, read]) => cell(read(message))).join(","));
  return `${rows.join("\r\n")}\r\n`;
}
