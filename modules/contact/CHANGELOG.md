# Changelog: contact

## 0.1.2

- The Settings section drawn to the Site tab's board (VM Website Dev 17's T1 and T2; decision 0040, amended): Add a topic is as wide as its words, a topic's First is worded as a field's label (the theme's meta size, muted, at 400) beside its switch with no row's rule, a topic's name, First and moves share a line while they fit, and the section's parts are 18px apart, the topics' 12.

## 0.1.1

- Its reads and its send in `public.ts`, for a site that draws its own form: `useContactForm`, `useSendMessage`, `fieldErrors` and the types `ContactFormAnswer`, `NewMessage`, `Received`, `Topic`, `FieldErrors` and `MessageField` (MODULE.md, "Extension points"). `ContactForm` works through the same hooks.
- "Message sent" takes focus once it's drawn, not in a frame asked for on success, which a loaded machine could run first.

## 0.1.0

- First version: the contact form at `/contact` and `ContactForm` for a site's own page, held messages set apart as spam, a notice to the Inbox's readers (decision 0059), a newsletter sign-up for `campaigns`, the Inbox with its tabs, actions and export, the Settings section, the daily prune, the server copy, and the bot check, privacy, seed and dashboard hooks (`dev plans/contracts/contact.md`, approved 2026-11-22).
