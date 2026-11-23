// The newsletter's sign-up for a site's own sections (`dev plans/contracts/campaigns.md`
// §2): Music's "New music in your inbox", Blog's and Videos'. It draws the kit's
// bot trap and one field, Email, then "Check your inbox": a confirmation is on its
// way, and nothing more is sent until it's clicked. The answer is the same
// whatever the address's state. While sign-ups are closed, it says so.
import { useEffect, useId, useRef, useState, type SubmitEvent } from "react";

import { ApiProblem, BotFields, Button, Field, Input, useBotProof } from "@/kernel";

import { useNewsletterOn, useSubscribe } from "./reads";
import "./campaigns.css";

export type NewsletterSignupProps = {
  /** Its heading: "New music in your inbox". */
  heading?: string;
  /** The line under the heading. */
  words?: string;
  /** Where the sign-ups come from, as the Subscribers tab shows it: a short name such as `music`. */
  source?: string;
  /** The button's words: "Sign up". */
  button?: string;
};

export function NewsletterSignup({
  heading = "Get the news",
  words = "New releases and news, by email. Unsubscribe whenever you like.",
  source = "form",
  button = "Sign up",
}: NewsletterSignupProps) {
  const open = useNewsletterOn();
  const subscribe = useSubscribe();
  const bot = useBotProof();
  const [address, setAddress] = useState("");
  const [error, setError] = useState<string[] | undefined>();
  const [failed, setFailed] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const done = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLInputElement>(null);
  const headingId = useId();
  useEffect(() => {
    if (sent) done.current?.focus();
  }, [sent]);

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFailed(null);
    if (!address.trim()) {
      setError(["Enter your email address."]);
      field.current?.focus();
      return;
    }
    setError(undefined);
    subscribe.mutate(
      { body: { email: address.trim(), source, bot: bot.proof() } },
      {
        onSuccess: () => {
          setSent(true);
        },
        onError: (problem) => {
          if (problem instanceof ApiProblem && problem.status === 422) {
            setError(problem.errors["body.email"] ?? [problem.detail]);
            field.current?.focus();
          } else if (problem instanceof ApiProblem && problem.code === "campaigns.closed") {
            setFailed("Sign-ups are closed just now.");
          } else if (problem instanceof ApiProblem && problem.status === 429) {
            setFailed("Too many sign-ups in a short time. Please try again in an hour.");
          } else {
            setFailed("That didn't go through. Try again in a moment.");
          }
        },
      },
    );
  };

  if (open === undefined) return null;
  return (
    <section className="mf-newsletter" aria-labelledby={headingId}>
      <h2 id={headingId}>{heading}</h2>
      {sent ? (
        <div className="mf-newsletter-sent" role="status" tabIndex={-1} ref={done}>
          <p className="mf-newsletter-sent-head">Check your inbox</p>
          <p>We&rsquo;ve sent a confirmation to {address.trim()}. Click its link and you&rsquo;re on the list.</p>
        </div>
      ) : open ? (
        <form className="mf-newsletter-form" aria-labelledby={headingId} noValidate onSubmit={submit}>
          <p className="mf-newsletter-words">{words}</p>
          <div className="mf-newsletter-row">
            <Field label="Email" error={error}>
              <Input
                ref={field}
                name="email"
                type="email"
                autoComplete="email"
                maxLength={254}
                required
                value={address}
                onChange={(event) => {
                  setAddress(event.target.value);
                }}
              />
            </Field>
            <Button type="submit" variant="primary" disabled={subscribe.isPending}>
              {subscribe.isPending ? "Signing up…" : button}
            </Button>
          </div>
          <BotFields {...bot.fields} />
          {failed ? (
            <p className="mf-newsletter-error" role="alert">
              {failed}
            </p>
          ) : null}
        </form>
      ) : (
        <p className="mf-newsletter-words">Sign-ups are closed just now.</p>
      )}
    </section>
  );
}
