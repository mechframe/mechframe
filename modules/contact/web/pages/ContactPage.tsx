// The Contact page, /contact (`dev plans/contracts/contact.md` §2; VM Website's
// Contact board): its heading, Settings' intro line and the form. The words are
// the server copy's own, so a crawler reads what a person sees. A site with its
// own Contact page draws `ContactForm` there instead, and its route wins.
import { Seo, useSite } from "@/kernel";

import { useApiQuery } from "../api";
import { ContactForm } from "../ContactForm";
import "../contact.css";

export default function ContactPage() {
  const site = useSite();
  const form = useApiQuery("get", "/api/contact/form");
  const intro = form.data?.intro ?? "";
  return (
    <article className="mf-contact-page">
      <Seo title={site ? `Contact · ${site.name}` : "Contact"} description={intro} path="/contact" />
      <h1>Contact</h1>
      {intro ? <p className="mf-contact-intro">{intro}</p> : null}
      <ContactForm />
    </article>
  );
}
