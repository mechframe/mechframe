// The contact form (`dev plans/contracts/contact.md` §2; VM Website's Contact
// board): Name, Email, What it's about, Message, and "Send me news and releases
// too" while `campaigns` is on. It draws the kit's bot trap and sends its proof
// (hook 5), and thanks the sender the same whether the server passed the
// message or held it. A site builds its own Contact page around it as
// `@/modules/contact/public` (decision 0057).
import { useEffect, useId, useRef, useState, type SubmitEvent } from "react";

import { ApiProblem, BotFields, Button, Field, Input, LoadError, Select, TextArea, useBotProof, useModuleEnabled } from "@/kernel";

import { fieldErrors, useContactForm, useSendMessage } from "./reads";
import "./contact.css";

export type ContactFormProps = {
  /** Called once a message is sent, as the form shows its thanks. */
  onSent?: () => void;
};

type Values = { name: string; email: string; topic: string; message: string; wants_news: boolean };
type Errors = Partial<Record<keyof Values | "form", string[]>>;

const EMPTY: Values = { name: "", email: "", topic: "", message: "", wants_news: false };
const ORDER = ["name", "email", "topic", "message"] as const;

function checked(values: Values): Errors {
  const found: Errors = {};
  if (!values.name.trim()) found.name = ["Enter your name."];
  if (!values.email.trim()) found.email = ["Enter your email address, so we can reply."];
  if (!values.topic) found.topic = ["Choose what your message is about."];
  if (!values.message.trim()) found.message = ["Write your message."];
  return found;
}

export function ContactForm({ onSent }: ContactFormProps) {
  const form = useContactForm();
  const send = useSendMessage();
  const news = useModuleEnabled("campaigns");
  const bot = useBotProof();
  const [values, setValues] = useState<Values>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});
  const [sent, setSent] = useState(false);
  const thanks = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const ids = useId();
  // The thanks take focus once they're drawn: a frame asked for on success could run before
  // React drew them on a loaded machine, and focus nothing (contact's e2e under load).
  useEffect(() => {
    if (sent) thanks.current?.focus();
  }, [sent]);

  const set = <K extends keyof Values>(name: K, value: Values[K]) => {
    setValues((now) => ({ ...now, [name]: value }));
  };

  const focusFirst = (found: Errors) => {
    const first = ORDER.find((name) => found[name]);
    if (first) formRef.current?.querySelector<HTMLElement>(`[name="${first}"]`)?.focus();
  };

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const found = checked(values);
    setErrors(found);
    if (Object.keys(found).length) {
      focusFirst(found);
      return;
    }
    send.mutate(
      { body: { ...values, wants_news: news === true && values.wants_news, bot: bot.proof() } },
      {
        onSuccess: () => {
          setSent(true);
          onSent?.();
        },
        onError: (error) => {
          if (error instanceof ApiProblem && error.status === 422) {
            const said = fieldErrors(error);
            setErrors(ORDER.some((name) => said[name]) ? said : { form: [error.detail] });
            focusFirst(said);
          } else if (error instanceof ApiProblem && error.status === 429) {
            setErrors({ form: ["Too many messages in a short time. Please wait an hour and try again."] });
          } else {
            setErrors({ form: ["Your message didn't send. Try again in a moment."] });
          }
        },
      },
    );
  };

  if (sent) {
    return (
      <div className="mf-contact-sent" role="status" tabIndex={-1} ref={thanks}>
        <h2>Message sent</h2>
        <p>Thanks for writing. We&rsquo;ll reply by email.</p>
        <Button
          onClick={() => {
            setValues(EMPTY);
            setErrors({});
            setSent(false);
          }}
        >
          Send another
        </Button>
      </div>
    );
  }
  if (form.error) return <LoadError what="The contact form" error={form.error} onRetry={() => void form.refetch()} />;
  const topics = form.data?.topics ?? [];
  return (
    <form className="mf-contact-form" aria-label="Contact form" noValidate onSubmit={submit} ref={formRef}>
      <Field label="Name" error={errors.name}>
        <Input name="name" autoComplete="name" maxLength={200} required value={values.name} onChange={(e) => { set("name", e.target.value); }} />
      </Field>
      <Field label="Email" error={errors.email}>
        <Input name="email" type="email" autoComplete="email" maxLength={254} required value={values.email} onChange={(e) => { set("email", e.target.value); }} />
      </Field>
      <Field label="What it's about" error={errors.topic}>
        <Select name="topic" required value={values.topic} onChange={(e) => { set("topic", e.target.value); }}>
          <option value="">Choose one</option>
          {topics.map((topic) => (
            <option key={topic.key} value={topic.key}>
              {topic.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Message" error={errors.message}>
        <TextArea name="message" rows={6} maxLength={5000} required value={values.message} onChange={(e) => { set("message", e.target.value); }} />
      </Field>
      {news ? (
        <div className="mf-contact-news">
          <input
            id={`${ids}-news`}
            type="checkbox"
            checked={values.wants_news}
            onChange={(e) => { set("wants_news", e.target.checked); }}
          />
          <label htmlFor={`${ids}-news`}>Send me news and releases too</label>
        </div>
      ) : null}
      <BotFields {...bot.fields} />
      {errors.form ? (
        <p className="mf-contact-error" role="alert">
          {errors.form.join(" ")}
        </p>
      ) : null}
      <div>
        <Button type="submit" variant="primary" disabled={send.isPending}>
          {send.isPending ? "Sending…" : "Send message"}
        </Button>
      </div>
    </form>
  );
}
