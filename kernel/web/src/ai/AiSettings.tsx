/**
 * `/admin/settings/ai`, Settings → AI (decision 0058; built from the kit, in
 * the Site tab's cards, the owner's answer of 2026-11-23): the Anthropic key
 * the AI's writing help uses. A key saved here wins over the host's
 * ANTHROPIC_API_KEY; removing it brings the host's back. The key is
 * write-only: the page says only where the key in use comes from, and Check
 * asks Anthropic whether it works.
 */
import { useState } from "react";

import { api, useApiQuery } from "../api/client";
import { ApiProblem } from "../api/problem";
import { SettingsPage } from "../admin/SettingsPage";
import { useSettings } from "../settings/useSettings";
import { Attention } from "../ui/Attention";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Field, Input } from "../ui/Field";
import { LoadError } from "../ui/LoadError";
import { SectionHistory } from "../ui/SectionHistory";
import { useToast } from "../ui/Toast";
import "./ai.css";
import { sayAi } from "./words";

const LABELS: Readonly<Record<string, string>> = { api_key: "Anthropic API key" };

/** Where the key in use comes from, as the page says it. */
export function sourceWords(source: "settings" | "environment" | "none"): string {
  if (source === "settings") return "The AI's writing help uses the key saved here.";
  if (source === "environment") return "The AI's writing help uses the host's key, ANTHROPIC_API_KEY. A key saved here would be used instead.";
  return "No key is set, so the AI's writing help is off. Save one here, or set ANTHROPIC_API_KEY on the host.";
}

export default function AiSettings() {
  const toast = useToast();
  const form = useSettings("kernel.ai");
  const state = useApiQuery("get", "/api/kernel/admin/ai");
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
  const { source, model, unreadable } = state.data;

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
        <Field label="Model" hint="Set on the host, as ANTHROPIC_MODEL.">
          <Input value={model} readOnly />
        </Field>
        <SectionHistory version={form.version} labels={LABELS} load={() => form.history().then((got) => got.versions)} />
      </Card>
    </SettingsPage>
  );
}
