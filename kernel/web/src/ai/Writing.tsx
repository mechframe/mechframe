/**
 * `/admin/settings/writing`, Settings → Writing (decision 0058; from VybeSite's
 * writing constitution and writing styles panels; built from the kit, the
 * owner's answer of 2026-11-23). Two cards:
 *
 * - **Writing rules** (the settings section `kernel.writing`, for
 *   `kernel.settings.manage`): what every AI task starts from. The default
 *   rules, each a switch, then rules of the site's own; or its own text in
 *   their place. Then the brief: what the site says about itself.
 * - **Writing styles** (for `kernel.writing.manage`): the voices a writer
 *   picks in the editor's Write with AI, each on a page of its own.
 */
import { useId } from "react";

import { useApiQuery } from "../api/client";
import { SettingsPage } from "../admin/SettingsPage";
import { useSession } from "../session/session";
import { useSettings, type SaveOutcome } from "../settings/useSettings";
import { Button, LinkButton } from "../ui/Button";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Field, Select, Switch, TextArea } from "../ui/Field";
import { LoadError } from "../ui/LoadError";
import { SaveConflict } from "../ui/SaveConflict";
import { SectionHistory } from "../ui/SectionHistory";
import { useToast } from "../ui/Toast";
import { UnsavedDialog } from "../ui/UnsavedDialog";
import { useUnsavedGuard } from "../ui/unsaved";
import "./ai.css";
import { sayAi } from "./words";

export const WRITING_LABELS = {
  mode: "Rules",
  rules_off: "Rules switched off",
  added_rules: "Rules of our own",
  own_text: "Our own text",
  about: "About the site",
  audience: "Who it's for",
  can_say: "What we can say",
  never_say: "What we never say",
  voice: "Voice",
} as const satisfies Readonly<Record<string, string>>;

/** The brief's boxes, in the order every task reads them. */
const BRIEF: readonly (readonly [string, string, string])[] = [
  ["about", WRITING_LABELS.about, "What the site is and does, in a few plain sentences."],
  ["audience", WRITING_LABELS.audience, "The readers it writes for."],
  ["can_say", WRITING_LABELS.can_say, "Facts the AI may use: what's true and checked."],
  ["never_say", WRITING_LABELS.never_say, "What the site holds back, and why."],
  ["voice", WRITING_LABELS.voice, "How it sounds: warm, plain, playful."],
];

const BOX_MAX = 4000;
const OWN_TEXT_MAX = 20000;

const text = (value: unknown): string => (typeof value === "string" ? value : "");
const ids = (value: unknown): string[] => (Array.isArray(value) ? value.map(String) : []);

function sayOutcome(outcome: SaveOutcome): string | null {
  if (outcome.status === "saved" || outcome.status === "unchanged") return null;
  if (outcome.status === "conflict") return "Someone else saved the writing rules since you opened them. Choose which values to keep.";
  return sayAi(outcome.problem);
}

function RulesCard() {
  const formId = useId();
  const toast = useToast();
  const form = useSettings("kernel.writing");
  const catalogue = useApiQuery("get", "/api/kernel/admin/writing/rules");
  const save = async (): Promise<string | null> => sayOutcome(await form.save());
  const guard = useUnsavedGuard(form.dirty, save);

  if (form.read === "failed" || catalogue.isError) {
    return (
      <Card className="mf-settings-card mf-settings-card--form" title="Writing rules">
        <LoadError
          what="the writing rules"
          error={form.problem ?? catalogue.error}
          onRetry={() => {
            form.retry();
            void catalogue.refetch();
          }}
        />
      </Card>
    );
  }
  if (form.read === "loading" || !catalogue.data) {
    return (
      <Card className="mf-settings-card mf-settings-card--form" title="Writing rules">
        <p className="mf-settings-quiet">Loading the writing rules…</p>
      </Card>
    );
  }

  const { values } = form;
  const own = values.mode === "own";
  const off = new Set(ids(values.rules_off));
  const { rules, default_text: defaults } = catalogue.data;

  const submit = () => {
    void save().then((problem) => {
      toast(problem ? { tone: "danger", text: problem } : { tone: "success", text: "Writing rules saved." });
    });
  };

  return (
    <Card
      className="mf-settings-card mf-settings-card--form"
      title="Writing rules"
      description="What every AI task starts from, whoever asks and in whichever style."
      actions={
        <Button type="submit" form={formId} variant="primary" disabled={!form.dirty || form.saving}>
          {form.saving ? "Saving…" : "Save"}
        </Button>
      }
    >
      {form.conflict ? (
        <SaveConflict
          conflict={form.conflict}
          labels={WRITING_LABELS}
          saving={form.saving}
          onResolve={(choices) => {
            void form.resolve(choices).then((outcome) => {
              const problem = sayOutcome(outcome);
              toast(problem ? { tone: "danger", text: problem } : { tone: "success", text: "Writing rules saved." });
            });
          }}
          onCancel={form.dropConflict}
        />
      ) : null}
      <form
        id={formId}
        className="mf-ai-rules"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <Field label={WRITING_LABELS.mode} error={form.errors.mode}>
          <Select
            value={own ? "own" : "defaults"}
            onChange={(event) => {
              form.set("mode", event.target.value);
            }}
          >
            <option value="defaults">The default rules, each switched on or off</option>
            <option value="own">Our own text in their place</option>
          </Select>
        </Field>
        {own ? (
          <Field
            label={WRITING_LABELS.own_text}
            hint="Every AI task follows this in place of the default rules."
            error={form.errors.own_text}
            aside={
              text(values.own_text).trim() ? null : (
                <Button
                  size="small"
                  onClick={() => {
                    form.set("own_text", defaults);
                  }}
                >
                  Start from the defaults
                </Button>
              )
            }
          >
            <TextArea
              rows={10}
              maxLength={OWN_TEXT_MAX}
              value={text(values.own_text)}
              onChange={(event) => {
                form.set("own_text", event.target.value);
              }}
            />
          </Field>
        ) : (
          <>
            <div className="mf-switch-rows">
              {rules.map((rule) => {
                const on = !off.has(rule.id);
                return (
                  <Switch
                    key={rule.id}
                    label={rule.label}
                    // A rule switched off says its risk in the warning colour (VM Website Dev 17's W2).
                    hint={!on && rule.warning ? <span className="mf-ai-warning">{rule.warning}</span> : rule.why}
                    checked={on}
                    onChange={(next) => {
                      const left = new Set(off);
                      if (next) left.delete(rule.id);
                      else left.add(rule.id);
                      form.set(
                        "rules_off",
                        rules.map((each) => each.id).filter((id) => left.has(id)),
                      );
                    }}
                  />
                );
              })}
            </div>
            <Field label={WRITING_LABELS.added_rules} hint="One a line, after the defaults." error={form.errors.added_rules}>
              <TextArea
                rows={4}
                maxLength={BOX_MAX}
                value={text(values.added_rules)}
                onChange={(event) => {
                  form.set("added_rules", event.target.value);
                }}
              />
            </Field>
          </>
        )}
        <div className="mf-ai-brief">
          <h3 className="mf-ai-subhead">The brief</h3>
          <p className="mf-ai-note">What the site says about itself. A box left empty is left out.</p>
        </div>
        {BRIEF.map(([name, label, hint]) => (
          <Field key={name} label={label} hint={hint} error={form.errors[name]}>
            <TextArea
              rows={3}
              maxLength={BOX_MAX}
              value={text(values[name])}
              onChange={(event) => {
                form.set(name, event.target.value);
              }}
            />
          </Field>
        ))}
      </form>
      <SectionHistory version={form.version} labels={WRITING_LABELS} load={() => form.history().then((got) => got.versions)} />
      <UnsavedDialog guard={guard} what="The writing rules" several />
    </Card>
  );
}

function StylesCard() {
  const styles = useApiQuery("get", "/api/kernel/admin/writing/styles");
  const add = (
    <LinkButton size="small" icon="plus" to="/admin/settings/writing/styles/new">
      New style
    </LinkButton>
  );
  let body;
  if (styles.isError) body = <LoadError what="the writing styles" error={styles.error} onRetry={() => void styles.refetch()} />;
  else if (!styles.data) body = <p className="mf-settings-quiet">Loading the writing styles…</p>;
  else if (styles.data.items.length === 0) {
    body = <EmptyState title="No writing styles yet">Without one, the AI writes in the house style: the writing rules' own voice.</EmptyState>;
  } else {
    body = (
      <ul className="mf-ai-styles">
        {styles.data.items.map((style) => (
          <li key={style.id}>
            <LinkButton variant="secondary" size="small" to={`/admin/settings/writing/styles/${style.id}`}>
              {style.name}
            </LinkButton>
            <span className="mf-ai-style-line">{style.description}</span>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <Card className="mf-settings-card mf-settings-card--form" title="Writing styles" description="Voices a writer can pick in Write with AI. A style shapes how the writing sounds, never what it says." actions={add}>
      {body}
    </Card>
  );
}

export default function Writing() {
  const session = useSession();
  const may = (permission: string) => session.status === "signed-in" && session.can(permission);
  return (
    <SettingsPage page="Writing">
      {may("kernel.settings.manage") ? <RulesCard /> : null}
      {may("kernel.writing.manage") ? <StylesCard /> : null}
    </SettingsPage>
  );
}
