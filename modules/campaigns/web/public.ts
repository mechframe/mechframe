// campaigns' public surface (SPEC.md section 7; decision 0057): what a site or a
// module listing campaigns in `requires.modules` may import, as
// `@/modules/campaigns/public`. A site draws the sign-up in its own sections, and its
// other forms ask `useNewsletterOn()` before offering the news.
export { NewsletterSignup } from "./NewsletterSignup";
export type { NewsletterSignupProps } from "./NewsletterSignup";
export { useNewsletterOn, useSubscribe } from "./reads";
export type { NewSubscription } from "./api";
