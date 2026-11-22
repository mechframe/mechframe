// contact's public surface (SPEC.md section 7; decision 0057): what a site or a
// module listing contact in `requires.modules` may import, as
// `@/modules/contact/public`. A site builds its own Contact page around the form.
export { ContactForm } from "./ContactForm";
export type { ContactFormProps } from "./ContactForm";
