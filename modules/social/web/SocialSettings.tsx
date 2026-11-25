// The Settings section "Social" (`admin.settings.section`; `dev plans/contracts/social.md`
// §2): the Buffer token sharing uses. A token saved here wins over the host's
// BUFFER_ACCESS_TOKEN; removing it brings the host's back. It's write-only: the
// section says where the token in use comes from, and Check the token asks Buffer
// which channels it reaches. It's saved alone, as Settings › AI's key is, so the
// Site tab's Save never sends it.
import { useState } from "react";

import { ApiProblem, Attention, Button, Field, Input, LoadError, Pill, api as kernelApi, failureWords, useSettings, useToast } from "@/kernel";

import { STATE, api, dayAndTime, sourceWords, useApiQuery } from "./api";
import "./social.css";

export default function SocialSettings() {
  const toast = useToast();
  const form = useSettings("social");
  const state = useApiQuery("get", STATE);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState("");
  const kept = (form.saved.buffer_token as { kept?: boolean } | undefined)?.kept === true;

  const keep = async (token: string, done: string) => {
    setBusy(true);
    setRefused("");
    try {
      await kernelApi.PUT("/api/kernel/admin/settings/{id}", {
        params: { path: { id: "social" } },
        body: { version: form.version ?? 0, changes: { buffer_token: token } },
      });
      setTyped("");
      form.retry();
      void state.refetch();
      toast({ tone: "success", text: done });
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "kernel.invalid_request") {
        setRefused(error.errors.buffer_token?.join(" ") ?? failureWords(error));
      } else if (error instanceof ApiProblem && error.code === "kernel.settings_conflict") {
        toast({ tone: "danger", text: "Someone else changed the token meanwhile. Reload the page to see it." });
      } else {
        toast({ tone: "danger", text: failureWords(error) });
      }
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    setBusy(true);
    try {
      const { data } = await api.POST("/api/social/admin/channels");
      const count = data?.channels.length ?? 0;
      toast({ tone: "success", text: `The token works: Buffer lists ${count === 1 ? "1 channel" : `${count.toString()} channels`}.` });
      void state.refetch();
    } catch (error) {
      toast({ tone: "danger", text: failureWords(error) });
    } finally {
      setBusy(false);
    }
  };

  if (form.read === "failed" || state.isError) {
    return (
      <LoadError
        what="The sharing settings"
        error={form.problem ?? state.error}
        onRetry={() => {
          form.retry();
          void state.refetch();
        }}
        inline
      />
    );
  }
  if (form.read === "loading" || !state.data) return <p className="mf-social-quiet">Loading…</p>;
  const { source, unreadable, channels, listed_at: listedAt } = state.data;

  return (
    <div className="mf-social-settings">
      {unreadable ? (
        <Attention tone="danger" what="The saved Buffer token can't be read" why="This happens when the server's ENCRYPTION_KEYS change. Save the token again." />
      ) : null}
      <p className="mf-social-quiet" role="status">
        {sourceWords(source)}
      </p>
      <Field
        label={kept ? "Replace the saved token" : "Save a Buffer token"}
        hint="From Buffer's API settings, at publish.buffer.com. It's kept sealed and never shown again."
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
      <div className="mf-social-actions">
        {kept ? (
          <Button size="small" disabled={busy} onClick={() => void keep("", "The saved token is removed.")}>
            Remove the saved token
          </Button>
        ) : null}
        <Button size="small" disabled={busy || source === "none" || unreadable} onClick={() => void check()}>
          {busy ? "Checking…" : "Check the token"}
        </Button>
        <Button size="small" variant="primary" disabled={busy || !typed.trim()} onClick={() => void keep(typed.trim(), "Token saved. Check it to list its channels.")}>
          Save the token
        </Button>
      </div>
      {channels.length > 0 ? (
        <div className="mf-social-stack">
          <p className="mf-social-quiet">{listedAt ? `The channels Buffer listed on ${dayAndTime(listedAt)}:` : "The channels Buffer listed:"}</p>
          <ul className="mf-social-listed">
            {channels.map((channel) => (
              <li key={channel.id}>
                <span>
                  {channel.name} <span className="mf-social-quiet">({channel.network})</span>
                </span>
                {channel.usable ? <Pill tone="success">Can be shared to</Pill> : <span className="mf-social-quiet">{channel.problem}</span>}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
