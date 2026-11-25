// A player's settings, for whoever holds `featured.slot.manage` (`dev plans/contracts/featured.md`
// §8, 2 and 7): New player, or a player's own, with its name, the key the site's
// code reads, what it takes (the types the modules on give, and YouTube links), a
// video's kinds, and whether the Dashboard shows it; and Remove the player.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiProblem, Button, Dialog, Field, Input, Switch, failureWords, useToast } from "@/kernel";

import { KEY_PATTERN, MAX_KEY, MAX_KINDS, MAX_LABEL, SLOT, SLOTS, YOUTUBE, api, labelOf, type AdminSlot, type FullSlot, type Kind, type TypeLabel } from "../api";

export type SlotSettingsProps = {
  /** The player to change, or none for a new one. */
  slot: AdminSlot | null;
  types: readonly TypeLabel[];
  onDone: (key: string | null) => void;
  onClose: () => void;
};

/** A key from words: "Music video" is `music-video`. */
export function keyOf(words: string): string {
  return words
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, MAX_KEY)
    .replace(/-+$/g, "");
}

type KindRow = { key: string; label: string; typed: boolean };

function problemOf(error: unknown): string {
  if (error instanceof ApiProblem) return Object.values(error.errors).flat().join(" ") || error.detail;
  return error instanceof Error ? failureWords(error) : "That didn't go through. Try again.";
}

export function SlotSettings({ slot, types, onDone, onClose }: SlotSettingsProps) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [label, setLabel] = useState(slot?.label ?? "");
  const [key, setKey] = useState(slot?.key ?? "");
  const [keyTyped, setKeyTyped] = useState(Boolean(slot));
  const [accepts, setAccepts] = useState<string[]>(slot?.accepts ?? []);
  const [kinds, setKinds] = useState<KindRow[]>((slot?.kinds ?? []).map((each) => ({ ...each, typed: true })));
  const [dashboard, setDashboard] = useState(slot?.on_dashboard ?? false);
  const [refused, setRefused] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);
  // Every type a module on gives, and those the player took whose module is off now.
  const choices = [...types.map((each) => each.type), ...accepts.filter((each) => each !== YOUTUBE && !types.some((type) => type.type === each))];
  const shownKey = keyTyped ? key : keyOf(label);
  const keyWrong = shownKey && !new RegExp(KEY_PATTERN).test(shownKey) ? "Lowercase letters and digits, with single hyphens between." : "";
  const ready = label.trim() && shownKey && !keyWrong && accepts.length > 0 && kinds.every((each) => each.label.trim() && each.key);

  const toggle = (type: string, on: boolean) => {
    setAccepts((now) => (on ? [...now.filter((each) => each !== type), type] : now.filter((each) => each !== type)));
  };

  async function save() {
    setBusy(true);
    setRefused(null);
    const madeKinds: Kind[] = kinds.map((each) => ({ key: each.typed ? each.key : keyOf(each.label), label: each.label.trim() }));
    try {
      let saved: FullSlot | undefined;
      if (slot) {
        const { data } = await api.PATCH("/api/featured/admin/slots/{key}", {
          params: { path: { key: slot.key } },
          body: { version: slot.version, label: label.trim(), accepts, kinds: madeKinds, on_dashboard: dashboard },
        });
        saved = data;
      } else {
        const { data } = await api.POST("/api/featured/admin/slots", {
          body: { key: shownKey, label: label.trim(), accepts, kinds: madeKinds, on_dashboard: dashboard },
        });
        saved = data;
      }
      if (saved) queryClient.setQueryData(["get", SLOT, { params: { path: { key: saved.key } } }], saved);
      await queryClient.invalidateQueries({ queryKey: ["get", SLOTS] });
      toast({ tone: "success", text: slot ? "The player is saved." : `The ${label.trim()} player is made.` });
      onDone(saved?.key ?? null);
    } catch (error) {
      setRefused(error);
      if (error instanceof ApiProblem && error.code === "featured.changed") void queryClient.invalidateQueries({ queryKey: ["get", SLOTS] });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!slot) return;
    setBusy(true);
    try {
      await api.DELETE("/api/featured/admin/slots/{key}", { params: { path: { key: slot.key } } });
      await queryClient.invalidateQueries({ queryKey: ["get", SLOTS] });
      toast({ tone: "success", text: `The ${slot.label} player is removed.` });
      onDone(null);
    } catch (error) {
      setRefused(error);
      setRemoving(false);
    } finally {
      setBusy(false);
    }
  }

  const close = busy ? () => undefined : onClose;
  if (removing && slot) {
    return (
      <Dialog title={`Remove the ${slot.label} player?`} onClose={close}>
        <div className="mf-featured-stack">
          <p>Everything in its list goes with it, and the site's code that reads “{slot.key}” finds nothing. This can't be undone.</p>
          <div className="mf-dialog-actions">
            <Button
              onClick={() => {
                setRemoving(false);
              }}
            >
              Keep it
            </Button>
            <Button variant="strong" disabled={busy} onClick={() => void remove()}>
              Remove the player
            </Button>
          </div>
        </div>
      </Dialog>
    );
  }
  return (
    <Dialog title={slot ? `${slot.label} settings` : "New player"} onClose={close} wide>
      <form
        className="mf-featured-stack"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) void save();
        }}
      >
        <div className="mf-featured-fields">
          <Field label="Name" hint="Its tab on Players: “Spotlight”.">
            <Input
              value={label}
              maxLength={MAX_LABEL}
              required
              onChange={(event) => {
                setLabel(event.target.value);
              }}
            />
          </Field>
          <Field label="Key" hint={slot ? "What the site's code reads. It can't change." : "What the site's code reads: “spotlight”."} error={keyWrong || undefined}>
            <Input
              value={shownKey}
              maxLength={MAX_KEY}
              disabled={Boolean(slot)}
              required
              onChange={(event) => {
                setKey(event.target.value);
                setKeyTyped(true);
              }}
            />
          </Field>
        </div>
        <fieldset className="mf-featured-takes">
          <legend>What it plays</legend>
          {choices.map((type) => (
            <label key={type} className="mf-featured-check">
              <input
                type="checkbox"
                checked={accepts.includes(type)}
                onChange={(event) => {
                  toggle(type, event.target.checked);
                }}
              />
              {labelOf(types, type)}
              {types.some((each) => each.type === type) ? null : <span className="mf-featured-hint"> (switched off)</span>}
            </label>
          ))}
          <label className="mf-featured-check">
            <input
              type="checkbox"
              checked={accepts.includes(YOUTUBE)}
              onChange={(event) => {
                toggle(YOUTUBE, event.target.checked);
              }}
            />
            YouTube links
          </label>
        </fieldset>
        {accepts.includes(YOUTUBE) ? (
          <fieldset className="mf-featured-takes">
            <legend>Kinds of video</legend>
            <p className="mf-featured-hint">A video's kind, such as Music video or Poetry: the site's Videos page can filter by it.</p>
            <ol className="mf-featured-kinds">
              {kinds.map((each, at) => (
                <li key={at} className="mf-featured-fields">
                  <Field label={`Kind ${String(at + 1)}`}>
                    <Input
                      value={each.label}
                      maxLength={MAX_LABEL}
                      onChange={(event) => {
                        const value = event.target.value;
                        setKinds((now) => now.map((row, index) => (index === at ? { ...row, label: value, key: row.typed ? row.key : keyOf(value) } : row)));
                      }}
                    />
                  </Field>
                  <Button
                    size="small"
                    icon="close"
                    aria-label={`Remove the kind ${each.label || String(at + 1)}`}
                    onClick={() => {
                      setKinds((now) => now.filter((_, index) => index !== at));
                    }}
                  />
                </li>
              ))}
            </ol>
            {kinds.length < MAX_KINDS ? (
              <div>
                <Button
                  size="small"
                  icon="plus"
                  onClick={() => {
                    setKinds((now) => [...now, { key: "", label: "", typed: false }]);
                  }}
                >
                  Add a kind
                </Button>
              </div>
            ) : null}
          </fieldset>
        ) : null}
        <Switch label="Show on the Dashboard" hint="Its card, and a warning two days before it goes empty." checked={dashboard} onChange={setDashboard} />
        {refused ? <p className="mf-featured-error">{problemOf(refused)}</p> : null}
        <div className="mf-dialog-actions">
          {slot ? (
            <Button
              type="button"
              className="mf-featured-remove"
              disabled={busy}
              onClick={() => {
                setRemoving(true);
              }}
            >
              Remove the player
            </Button>
          ) : null}
          <Button type="button" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !ready}>
            {slot ? "Save the player" : "Make the player"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
