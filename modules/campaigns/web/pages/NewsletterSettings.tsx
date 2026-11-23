// The Settings section "Newsletter" (`admin.settings.section`;
// `dev plans/contracts/campaigns.md` §2): whether sign-ups are open, the postal
// address every newsletter carries, the footer's note, and the send pace. The Site
// tab's one Save sends it.
import { useState } from "react";

import { Field, Input, LoadError, Switch, TextArea, useSettings } from "@/kernel";

import "../campaigns.css";

const text = (value: unknown): string => (typeof value === "string" ? value : "");

export default function NewsletterSettings() {
  const form = useSettings("campaigns");
  // The pace field's words while it's being typed in: null shows the setting.
  const [typed, setTyped] = useState<string | null>(null);
  if (form.read === "failed") {
    return <LoadError what="The newsletter's settings" error={form.problem} onRetry={form.retry} inline />;
  }
  if (form.read === "loading") return <p className="mf-newsletter-hint">Loading…</p>;
  const pace = typeof form.values.send_per_hour === "number" ? form.values.send_per_hour : 400;
  return (
    <div className="mf-newsletter-settings">
      <Switch
        label="Sign-ups open"
        hint="While it's off, the sign-up forms say sign-ups are closed."
        checked={form.values.signups_open !== false}
        onChange={(open) => {
          form.set("signups_open", open);
        }}
      />
      <Field
        label="Postal address"
        hint="US law puts a postal address in every newsletter; a P.O. box will do. Nothing sends until it's set."
        error={form.errors.postal_address}
      >
        <TextArea
          rows={3}
          maxLength={300}
          value={text(form.values.postal_address)}
          onChange={(event) => {
            form.set("postal_address", event.target.value);
          }}
        />
      </Field>
      <Field
        label="Footer note"
        hint="The first line under every newsletter. ${site_name} is the site's name."
        error={form.errors.footer_note}
      >
        <Input
          maxLength={300}
          value={text(form.values.footer_note)}
          onChange={(event) => {
            form.set("footer_note", event.target.value);
          }}
        />
      </Field>
      <Field
        label="Emails an hour"
        hint="How many newsletter copies go out in an hour, a sixtieth each minute. Lower it if your mail host has a sending limit."
        error={form.errors.send_per_hour}
      >
        <Input
          type="number"
          inputMode="numeric"
          min={1}
          max={10000}
          value={typed ?? String(pace)}
          onChange={(event) => {
            // The field keeps what's typed, empty included; only a whole number
            // becomes the setting, which the server checks for its range
            // (CodeRabbit on #134). Leaving the field shows the setting again.
            const words = event.target.value;
            setTyped(words);
            if (/^\d+$/.test(words)) form.set("send_per_hour", Number.parseInt(words, 10));
          }}
          onBlur={() => {
            setTyped(null);
          }}
        />
      </Field>
    </div>
  );
}
