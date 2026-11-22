// contact's public reads and its send, as hooks (`dev plans/contracts/contact.md`
// §2): the form's intro and topics, and sending a message. `ContactForm` works
// through these, and so does a site's own Contact page that draws its own form
// (`public.ts`, decision 0057).
import type { ApiProblem } from "@/kernel";

import { FORM, useApiMutation, useApiQuery, type NewMessage } from "./api";

/** The form's fields, by the names the server's errors use (`body.email` is `email`). */
export type MessageField = Exclude<keyof NewMessage, "bot">;

/** What the server said of each field it refused, by the form's own names. */
export type FieldErrors = Partial<Record<MessageField, string[]>>;

const FIELDS: readonly MessageField[] = ["name", "email", "topic", "message", "wants_news"];

/** The form's intro and its topics, in the order staff set them. */
export function useContactForm() {
  return useApiQuery("get", FORM);
}

/**
 * Sends a message: 202 `{received}` whether the server passed it or held it as
 * spam; a 422 ApiProblem with each refused field in `fieldErrors(problem)`; a 429
 * `kernel.rate_limited` after too many from one address. The body's `bot` is the
 * kernel's `useBotProof().proof()`.
 */
export function useSendMessage() {
  return useApiMutation("post", "/api/contact/messages");
}

/** A 422's field errors (`body.email`) by the form's names; a path that isn't a field is left out. */
export function fieldErrors(problem: ApiProblem): FieldErrors {
  const found: FieldErrors = {};
  for (const [path, said] of Object.entries(problem.errors)) {
    const name = path.replace(/^body\./, "");
    if ((FIELDS as readonly string[]).includes(name)) found[name as MessageField] = said;
  }
  return found;
}
