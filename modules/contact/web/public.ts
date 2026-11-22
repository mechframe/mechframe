// contact's public surface (SPEC.md section 7; decision 0057): what a site or a
// module listing contact in `requires.modules` may import, as
// `@/modules/contact/public`. A site builds its own Contact page around the form,
// or draws its own form with the reads and the send (contact 0.1.1).
export { ContactForm } from "./ContactForm";
export type { ContactFormProps } from "./ContactForm";
export { fieldErrors, useContactForm, useSendMessage } from "./reads";
export type { FieldErrors, MessageField } from "./reads";
export type { ContactForm as ContactFormAnswer, NewMessage, Received, Topic } from "./api";
