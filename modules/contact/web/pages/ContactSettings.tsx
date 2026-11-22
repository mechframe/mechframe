// The Settings section "Contact form" (`admin.settings.section`;
// `dev plans/contracts/contact.md` §2): the Contact page's intro line, then the
// topics a message can be about, in the form's order, each with First (its new
// messages at the top of the Inbox). The Site tab's one Save sends it.
import { Button, Field, Input, Switch, useSettings } from "@/kernel";

import "../contact.css";

type Topic = { key: string; label: string; first: boolean };

const MAX_TOPICS = 12;

function topicsOf(value: unknown): Topic[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (each): each is Topic =>
      typeof each === "object" && each !== null && typeof (each as Topic).key === "string" && typeof (each as Topic).label === "string",
  );
}

/** A key for a new topic: its own, never one another topic has. */
function freshKey(topics: readonly Topic[]): string {
  const taken = new Set(topics.map((topic) => topic.key));
  let number = topics.length + 1;
  while (taken.has(`topic-${String(number)}`)) number += 1;
  return `topic-${String(number)}`;
}

export default function ContactSettings() {
  const form = useSettings("contact");
  const intro = typeof form.values.intro === "string" ? form.values.intro : "";
  const topics = topicsOf(form.values.topics);
  const put = (next: Topic[]) => {
    form.set("topics", next);
  };
  const change = (index: number, patch: Partial<Topic>) => {
    put(topics.map((topic, at) => (at === index ? { ...topic, ...patch } : topic)));
  };
  const swap = (index: number, by: -1 | 1) => {
    const next = [...topics];
    const other = index + by;
    const here = next[index];
    const there = next[other];
    if (!here || !there) return;
    next[index] = there;
    next[other] = here;
    put(next);
  };
  return (
    <div className="mf-contact-settings">
      <Field label="Intro" hint="The line under the Contact page's heading." error={form.errors.intro}>
        <Input value={intro} maxLength={300} onChange={(event) => { form.set("intro", event.target.value); }} />
      </Field>
      <fieldset className="mf-contact-topics">
        <legend>What a message can be about</legend>
        <p className="mf-contact-hint">In the form's order. A first topic&rsquo;s new messages come first in the Inbox.</p>
        {form.errors.topics ? <p className="mf-field-error">{form.errors.topics}</p> : null}
        <ol>
          {topics.map((topic, index) => (
            <li key={topic.key} className="mf-contact-topic">
              <Field label={`Topic ${String(index + 1)}`}>
                <Input value={topic.label} maxLength={80} onChange={(event) => { change(index, { label: event.target.value }); }} />
              </Field>
              <Switch label="First" checked={topic.first} onChange={(first) => { change(index, { first }); }} />
              <div className="mf-contact-topic-moves">
                <Button size="small" disabled={index === 0} onClick={() => { swap(index, -1); }} aria-label={`Move ${topic.label || "this topic"} up`}>
                  Up
                </Button>
                <Button
                  size="small"
                  disabled={index === topics.length - 1}
                  onClick={() => { swap(index, 1); }}
                  aria-label={`Move ${topic.label || "this topic"} down`}
                >
                  Down
                </Button>
                <Button
                  size="small"
                  disabled={topics.length === 1}
                  onClick={() => { put(topics.filter((_, at) => at !== index)); }}
                  aria-label={`Remove ${topic.label || "this topic"}`}
                >
                  Remove
                </Button>
              </div>
            </li>
          ))}
        </ol>
        <Button
          size="small"
          icon="plus"
          disabled={topics.length >= MAX_TOPICS}
          onClick={() => { put([...topics, { key: freshKey(topics), label: "", first: false }]); }}
        >
          Add a topic
        </Button>
      </fieldset>
    </div>
  );
}
