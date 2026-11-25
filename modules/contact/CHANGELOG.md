# Changelog: contact

## 0.1.2

- The Settings section ("Contact form" on Settings › Site) is drawn to the Site tab's board (VM Website Dev 17's T1 and T2; decision 0040, amended).
- The "Add a topic" button is as wide as its words. It used to stretch across the card.
- Each topic's "First" switch is labelled like a field's label: the theme's meta size, muted, at weight 400. It has no rule above it, as a row of switches has.
- A topic's name, its "First" switch and its Up, Down and Remove buttons share one line while they fit.
- The section's parts (the intro and the topics) are 18px apart; the topics are 12px apart.

## 0.1.1

- Its reads and its send in `public.ts`, for a site that draws its own form: `useContactForm`, `useSendMessage`, `fieldErrors` and the types `ContactFormAnswer`, `NewMessage`, `Received`, `Topic`, `FieldErrors` and `MessageField` (MODULE.md, "Extension points"). `ContactForm` works through the same hooks.
- "Message sent" takes focus once it's drawn, not in a frame asked for on success, which a loaded machine could run first.

## 0.1.0

- First version: the contact form at `/contact` and `ContactForm` for a site's own page, held messages set apart as spam, a notice to the Inbox's readers (decision 0059), a newsletter sign-up for `campaigns`, the Inbox with its tabs, actions and export, the Settings section, the daily prune, the server copy, and the bot check, privacy, seed and dashboard hooks (`dev plans/contracts/contact.md`, approved 2026-11-22).
