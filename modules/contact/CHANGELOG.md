# Changelog: contact

## 0.1.1

- Its reads and its send in `public.ts`, for a site that draws its own form: `useContactForm`, `useSendMessage`, `fieldErrors` and the types `ContactFormAnswer`, `NewMessage`, `Received`, `Topic`, `FieldErrors` and `MessageField` (MODULE.md, "Extension points"). `ContactForm` works through the same hooks.
- "Message sent" takes focus once it's drawn, not in a frame asked for on success, which a loaded machine could run first.

## 0.1.0

- First version: the contact form at `/contact` and `ContactForm` for a site's own page, held messages set apart as spam, a notice to the Inbox's readers (decision 0059), a newsletter sign-up for `campaigns`, the Inbox with its tabs, actions and export, the Settings section, the daily prune, the server copy, and the bot check, privacy, seed and dashboard hooks (`dev plans/contracts/contact.md`, approved 2026-11-22).
