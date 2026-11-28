// The Settings section "Art page" (`admin.settings.section`;
// `dev plans/contracts/portfolio.md` §2): the line under the Art page's title,
// where "Commission work like this" goes (empty hides it), and how many pieces
// a page holds. The Site tab's one Save sends it.
import { Field, Input, LoadError, useSettings } from "@/kernel";

import "../portfolio.css";

export default function ArtSettings() {
  const form = useSettings("portfolio");
  if (form.read === "failed") {
    return <LoadError what="The Art page's settings" error={form.problem} onRetry={form.retry} inline />;
  }
  if (form.read === "loading") return <p className="mf-portfolio-hint">Loading…</p>;
  const lead = typeof form.values.lead === "string" ? form.values.lead : "";
  const link = typeof form.values.commission_link === "string" ? form.values.commission_link : "";
  const perPage = typeof form.values.pieces_per_page === "number" ? form.values.pieces_per_page : 24;
  return (
    <div className="mf-portfolio-settings">
      <Field label="Lead" hint="The line under the Art page's title." error={form.errors.lead}>
        <Input
          value={lead}
          maxLength={300}
          onChange={(event) => {
            form.set("lead", event.target.value);
          }}
        />
      </Field>
      <Field label="Commission link" hint="Where Commission work like this goes: a page here, such as /contact, or an https address. Empty hides it." error={form.errors.commission_link}>
        <Input
          value={link}
          maxLength={500}
          onChange={(event) => {
            form.set("commission_link", event.target.value);
          }}
        />
      </Field>
      <Field label="Pieces a page" hint="From 6 to 60. Load more shows the next ones." error={form.errors.pieces_per_page}>
        <Input
          type="number"
          min={6}
          max={60}
          value={String(perPage)}
          onChange={(event) => {
            const value = Number(event.target.value);
            if (Number.isInteger(value)) form.set("pieces_per_page", value);
          }}
        />
      </Field>
    </div>
  );
}
