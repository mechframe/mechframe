/**
 * `/admin/settings/ai`, Settings → AI (decision 0058; built from the kit, in
 * the Site tab's cards, the owner's answer of 2026-11-23): the Anthropic key
 * the AI's writing help uses. A key saved here wins over the host's
 * ANTHROPIC_API_KEY; removing it brings the host's back. The key is
 * write-only: the page says only where the key in use comes from, and Check
 * asks Anthropic whether it works.
 *
 * The Model row (decision 0064, `dev plans/contracts/ai-model.md`) is a
 * dropdown of Anthropic's newest Opus, Sonnet and Haiku, read from Anthropic
 * each time the page opens, in the words of VM Website's board. The host's
 * ANTHROPIC_MODEL is used until one is saved; Use the host's model clears it.
 */
import { useState } from "react";

import { api, useApiQuery } from "../api/client";
import { ApiProblem } from "../api/problem";
import { SettingsPage } from "../admin/SettingsPage";
import { useSettings } from "../settings/useSettings";
import { Attention } from "../ui/Attention";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Field, Input, Select } from "../ui/Field";
import { LoadError } from "../ui/LoadError";
import { SectionHistory } from "../ui/SectionHistory";
import { useToast } from "../ui/Toast";
import "./ai.css";
import { sayAi } from "./words";

const LABELS: Readonly<Record<string, string>> = { api_key: "Anthropic API key", model: "Model" };

/** The list waits for a key that works: none, or a saved one that can't be read. */
const NO_WORKING_KEY = new Set(["kernel.ai_off", "kernel.ai_key_unreadable"]);

/** Where the key in use comes from, as the page says it. */
export function sourceWords(source: "settings" | "environment" | "none"): string {
  if (source === "settings") return "The AI's writing help uses the key saved here.";
  if (source === "environment") return "The AI's writing help uses the host's key, ANTHROPIC_API_KEY. A key saved here would be used instead.";
  return "No key is set, so the AI's writing help is off. Save one here, or set ANTHROPIC_API_KEY on the host.";
}

/** Where the model in use comes from, as the page says it. */
export function modelSourceWords(source: "settings" | "environment"): string {
  if (source === "settings") return "The AI's writing help uses the model saved here.";
  return "The AI's writing help uses the host's model, ANTHROPIC_MODEL, until one is saved here.";
}

type ModelList = ReturnType<typeof useModels>;

function useModels() {
  // Read when the page opens and again when asked, never cached for long: the
  // list is Anthropic's, now (the owner, 2026-11-24).
  return useApiQuery("get", "/api/kernel/admin/ai/models", {}, { retry: false, staleTime: 0 });
}

function ModelRow({ list, model, source, version, onSaved }: { list: ModelList; model: string; source: "settings" | "environment"; version: number; onSaved: () => void }) {
  const toast = useToast();
  const [picked, setPicked] = useState<string | null>(null);
  // The section's version when the pick began: a save from it merges with
  // any save since, so another admin's model is a conflict, never overwritten
  // (Codex on #144, as useSettings keeps a draft's version).
  const [pickedAt, setPickedAt] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const inUse = list.data?.in_use;
  const choices = list.data
    ? list.data.models.some((each) => each.id === list.data.in_use.id)
      ? list.data.models
      : [{ id: list.data.in_use.id, name: list.data.in_use.name ?? list.data.in_use.id }, ...list.data.models]
    : [{ id: model, name: model }];
  const chosen = picked ?? inUse?.id ?? model;
  const noKey = list.error instanceof ApiProblem && NO_WORKING_KEY.has(list.error.code);
  const failed = list.isError && !noKey;

  const pick = async (next: string | null, done: string) => {
    setSaving(true);
    try {
      await api.PUT("/api/kernel/admin/ai/model", { body: { version: next === null ? version : (pickedAt ?? version), model: next } });
      setPicked(null);
      setPickedAt(null);
      onSaved();
      toast({ tone: "success", text: done });
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "kernel.settings_conflict") {
        toast({ tone: "danger", text: "Someone else changed the model meanwhile. Reload the page to see it." });
      } else {
        const why = error instanceof ApiProblem ? error.errors.model?.join(" ") : undefined;
        toast({ tone: "danger", text: why ?? sayAi(error) });
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mf-ai-form">
      {inUse && !inUse.listed ? (
        <Attention tone="warning" what={`Anthropic doesn't list ${inUse.id} for this key, so the AI's writing help may fail.`} why="Choose another, or use the host's model." />
      ) : null}
      <Field label="Model" hint="Anthropic's newest model of each kind, listed when this page opens.">
        <Select
          value={chosen}
          disabled={!list.data || saving}
          onChange={(event) => {
            setPicked(event.target.value);
            setPickedAt((at) => at ?? version);
          }}
        >
          {choices.map((each) => (
            <option key={each.id} value={each.id}>
              {each.name}
            </option>
          ))}
        </Select>
      </Field>
      <p className="mf-ai-note">{modelSourceWords(source)}</p>
      {noKey ? <p className="mf-ai-note">Anthropic's model list loads once a key works.</p> : null}
      {failed ? (
        <div className="mf-ai-model-failed">
          <p className="mf-ai-note">Couldn't load Anthropic's model list, so the model in use is the only one shown.</p>
          <Button size="small" disabled={list.isFetching} onClick={() => void list.refetch()}>
            Try again
          </Button>
        </div>
      ) : null}
      <div className="mf-dialog-actions">
        {source === "settings" ? (
          <Button disabled={saving} onClick={() => void pick(null, "Using the host's model.")}>
            Use the host's model
          </Button>
        ) : null}
        <Button variant="primary" disabled={saving || !list.data || chosen === (inUse?.id ?? model)} onClick={() => void pick(chosen, "Saved the model.")}>
          {saving ? "Saving…" : "Save the model"}
        </Button>
      </div>
    </div>
  );
}

export default function AiSettings() {
  const toast = useToast();
  const form = useSettings("kernel.ai");
  const state = useApiQuery("get", "/api/kernel/admin/ai");
  const models = useModels();
  const [typed, setTyped] = useState("");
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [refused, setRefused] = useState("");
  const kept = (form.saved.api_key as { kept?: boolean } | undefined)?.kept === true;

  // The key goes alone, at the version the page read: a typed secret is the
  // only change this form makes, so it's sent as typed, not through a draft.
  const keep = async (key: string, done: string) => {
    setSaving(true);
    setRefused("");
    try {
      await api.PUT("/api/kernel/admin/settings/{id}", {
        params: { path: { id: "kernel.ai" } },
        body: { version: form.version ?? 0, changes: { api_key: key } },
      });
      setTyped("");
      form.retry();
      void state.refetch();
      void models.refetch();
      toast({ tone: "success", text: done });
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "kernel.invalid_request") {
        const why = error.errors.api_key?.join(" ");
        setRefused(why ?? sayAi(error));
      } else if (error instanceof ApiProblem && error.code === "kernel.settings_conflict") {
        toast({ tone: "danger", text: "Someone else changed the key meanwhile. Reload the page to see it." });
      } else {
        toast({ tone: "danger", text: sayAi(error) });
      }
    } finally {
      setSaving(false);
    }
  };

  const check = async () => {
    setChecking(true);
    try {
      const { data } = await api.POST("/api/kernel/admin/ai/check");
      if (data) toast({ tone: "success", text: data.source === "settings" ? "The saved key works." : "The host's key works." });
      // A key that works lists the models, if it didn't before.
      if (models.isError) void models.refetch();
    } catch (error) {
      toast({ tone: "danger", text: sayAi(error) });
    } finally {
      setChecking(false);
    }
  };

  if (form.read === "failed" || state.isError) {
    return (
      <SettingsPage page="AI">
        <LoadError what="the AI's settings" error={form.problem ?? state.error} onRetry={() => {
          form.retry();
          void state.refetch();
        }} />
      </SettingsPage>
    );
  }
  if (form.read === "loading" || !state.data) {
    return (
      <SettingsPage page="AI">
        <p className="mf-settings-quiet">Loading the settings…</p>
      </SettingsPage>
    );
  }
  const { source, model, model_source: modelSource, unreadable } = state.data;

  return (
    <SettingsPage page="AI">
      <Card className="mf-settings-card" title="Anthropic key" description="The AI's writing help in the editor, for staff who may use it.">
        {unreadable ? (
          <Attention tone="danger" what="The saved key can't be read" why="This happens when the server's ENCRYPTION_KEYS change. Save the key again." />
        ) : null}
        <p className="mf-ai-note" role="status">
          {sourceWords(source)}
        </p>
        <form
          className="mf-ai-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (typed.trim()) void keep(typed.trim(), "Key saved.");
          }}
        >
          <Field
            label={kept ? "Replace the saved key" : "Save a key"}
            hint="From the Anthropic console. It's kept sealed and never shown again."
            error={refused || undefined}
          >
            <Input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={typed}
              maxLength={400}
              onChange={(event) => {
                setTyped(event.target.value);
              }}
            />
          </Field>
          <div className="mf-dialog-actions">
            {kept ? (
              <Button disabled={saving} onClick={() => void keep("", "The saved key is removed.")}>
                Remove the saved key
              </Button>
            ) : null}
            <Button disabled={checking || source === "none" || unreadable} onClick={() => void check()}>
              {checking ? "Checking…" : "Check the key"}
            </Button>
            <Button type="submit" variant="primary" disabled={saving || !typed.trim()}>
              {saving ? "Saving…" : "Save the key"}
            </Button>
          </div>
        </form>
        <ModelRow
          list={models}
          model={model}
          source={modelSource}
          version={form.version ?? 0}
          onSaved={() => {
            form.retry();
            void state.refetch();
            void models.refetch();
          }}
        />
        <SectionHistory version={form.version} labels={LABELS} load={() => form.history().then((got) => got.versions)} />
      </Card>
    </SettingsPage>
  );
}
