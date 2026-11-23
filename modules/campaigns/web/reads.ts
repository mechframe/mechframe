// campaigns' public reads and its sign-up, as hooks (`dev plans/contracts/campaigns.md`
// §2): whether sign-ups are open, and signing up. `NewsletterSignup` works through
// these, and so does a site's own form (`public.ts`, decision 0057).
import { useModuleEnabled } from "@/kernel";

import { SIGNUP, useApiMutation, useApiQuery } from "./api";

/**
 * Whether the newsletter takes sign-ups now: true while campaigns is on and
 * Settings' "Sign-ups open" is; false while either is off; undefined while
 * it's being read. A site's other forms, such as contact's news box, show
 * their sign-up only while it's true.
 */
export function useNewsletterOn(): boolean | undefined {
  const on = useModuleEnabled("campaigns");
  const state = useApiQuery("get", SIGNUP, {}, { enabled: on === true });
  if (on === false) return false;
  if (on === undefined || state.isPending) return undefined;
  return state.data?.open ?? false;
}

/**
 * Signs an address up: 202 `{received}` whatever its state; a 422 ApiProblem
 * with `body.email` for an address that isn't one; 409 `campaigns.closed`
 * while sign-ups are closed; 429 `kernel.rate_limited` after too many from
 * one address. The body's `bot` is the kernel's `useBotProof().proof()`.
 */
export function useSubscribe() {
  return useApiMutation("post", "/api/campaigns/subscribe");
}
