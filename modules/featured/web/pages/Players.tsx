// Players, /admin/featured (`dev plans/contracts/featured.md` §2; VM Website
// `AdminPlayers.dc.html`): a tab per player with how many it holds, the strip with
// what's playing now and what's next, the list in order with its dates and pills,
// and one save bar for every player changed: "Save and go live" puts each list on
// the site at once. A save someone else got to first asks theirs or mine. The tab
// is in the address (`?slot=`), as the Dashboard's links name it.
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useSearchParams } from "react-router";

import {
  AdminPage,
  ApiProblem,
  Button,
  Card,
  EmptyState,
  Icon,
  LoadError,
  SaveBar,
  SaveConflict,
  Tabs,
  UnsavedDialog,
  buttonClass,
  failureWords,
  useSession,
  useToast,
  useUnsavedGuard,
  type SettingsConflict,
} from "@/kernel";

import {
  LIVE,
  MAX_PLACEMENTS,
  SLOT,
  SLOTS,
  SLOT_MANAGE,
  YOUTUBE,
  api,
  apiQueryOptions,
  bodyOf,
  changesOf,
  intro,
  labelOf,
  rowOf,
  singular,
  statesOf,
  stripOf,
  titleOf,
  useApiQuery,
  type AdminRef,
  type AdminSlot,
  type FullSlot,
  type Row,
  type TypeLabel,
} from "../api";
import { DatesDialog } from "../components/DatesDialog";
import { PasteLinks, type PastedVideo } from "../components/PasteLinks";
import { Picker } from "../components/Picker";
import { PlacementRow } from "../components/PlacementRow";
import { SlotSettings } from "../components/SlotSettings";
import "../featured.css";

/** A list being changed: the version it was read at, and its rows. */
type Draft = { version: number; rows: Row[] };
type Conflict = { key: string; theirs: FullSlot; said: SettingsConflict };

let made = 0;
/** A key for a row that isn't saved yet. */
const newKey = () => `new-${String((made += 1))}`;

function problemOf(error: unknown): string {
  if (error instanceof ApiProblem) return Object.values(error.errors).flat().join(" ") || error.detail;
  return error instanceof Error ? failureWords(error) : "That didn't go through. Try again.";
}

/** The row a refusal's field points at: `items.3.link.title` is row 3. */
function rowRefused(error: unknown): number | null {
  if (!(error instanceof ApiProblem)) return null;
  for (const field of Object.keys(error.errors)) {
    const found = /^items\.(\d+)/.exec(field);
    if (found) return Number(found[1]);
  }
  return null;
}

type PanelProps = {
  slot: AdminSlot;
  full: FullSlot;
  rows: Row[];
  types: readonly TypeLabel[];
  mayMake: boolean;
  refused: { error: unknown; row: number | null } | null;
  conflict: Conflict | null;
  saving: boolean;
  onRows: (rows: Row[]) => void;
  onSettings: () => void;
  onResolve: (choice: "theirs" | "mine") => void;
  onCancelConflict: () => void;
};

function SlotPanel({ slot, full, rows, types, mayMake, refused, conflict, saving, onRows: edit, onSettings, onResolve, onCancelConflict }: PanelProps) {
  // Nothing changes while a save is on its way, so its answer never drops an edit made meanwhile (Codex on #157).
  const onRows = (next: Row[]) => {
    if (!saving) edit(next);
  };
  const [picking, setPicking] = useState<string | null>(null);
  const [pasting, setPasting] = useState(false);
  const [dating, setDating] = useState<number | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const states = statesOf(rows);
  const strip = stripOf(full);
  const onTypes = types.filter((each) => slot.accepts.includes(each.type));
  const room = MAX_PLACEMENTS - rows.length;
  const taken = new Set(rows.flatMap((row) => (row.item ? [`${row.item.type}:${row.item.id}`] : [])));

  const move = (from: number, to: number) => {
    if (to < 0 || to >= rows.length || from === to) return;
    const next = [...rows];
    const [moved] = next.splice(from, 1);
    if (moved) next.splice(to, 0, moved);
    onRows(next);
  };
  const change = (at: number, patch: Partial<Row>) => {
    onRows(rows.map((row, index) => (index === at ? { ...row, ...patch } : row)));
  };
  const addRef = (type: string, ref: AdminRef) => {
    if (rows.length >= MAX_PLACEMENTS) return;
    onRows([...rows, { id: null, key: newKey(), item: { type, id: ref.id }, ref, removed: false, link: null, starts_at: null, ends_at: null }]);
  };
  const addVideos = (videos: PastedVideo[]) => {
    onRows([
      ...rows,
      ...videos.slice(0, room).map((video) => ({
        id: null,
        key: newKey(),
        item: null,
        ref: null,
        removed: false,
        link: { url: video.url, video_id: video.video_id, title: video.title, kind: video.kind },
        starts_at: null,
        ends_at: null,
      })),
    ]);
    setPasting(false);
  };
  const dated = dating === null ? undefined : rows[dating];

  return (
    <div className="mf-featured-panel">
      <div className="mf-featured-strip">
        <span className="mf-featured-dot" aria-hidden="true" />
        <span>
          <b>Now playing:</b> {strip.now}
        </span>
        <span className="mf-featured-next">{strip.next}</span>
      </div>
      {conflict ? (
        <SaveConflict
          conflict={conflict.said}
          labels={{ list: `The ${slot.label}'s list` }}
          saving={saving}
          onResolve={(choices) => {
            onResolve(choices.list === "theirs" ? "theirs" : "mine");
          }}
          onCancel={onCancelConflict}
        />
      ) : null}
      {refused ? (
        <p className="mf-featured-error" role="alert">
          {refused.row !== null && rows[refused.row] ? `${titleOf(rows[refused.row] as Row)}: ` : ""}
          {problemOf(refused.error)}
        </p>
      ) : null}
      <Card>
        <div className="mf-featured-head">
          <p className="mf-featured-intro">{intro(slot, types)}</p>
          <span className="mf-featured-adds">
            {onTypes.map((each) => (
              <Button
                key={each.type}
                icon="plus"
                disabled={saving || room <= 0}
                onClick={() => {
                  setPicking(each.type);
                }}
              >
                Add {singular(each.label)}
              </Button>
            ))}
            {slot.accepts.includes(YOUTUBE) ? (
              <Button
                icon="plus"
                disabled={saving || room <= 0}
                onClick={() => {
                  setPasting(true);
                }}
              >
                Paste links
              </Button>
            ) : null}
            {mayMake ? (
              <Button icon="settings" aria-label={`${slot.label} settings`} onClick={onSettings} />
            ) : null}
          </span>
        </div>
        {rows.length === 0 ? (
          <p className="mf-featured-empty">Nothing in the {slot.label} yet: it's empty on the site.</p>
        ) : (
          <ol className="mf-featured-list" aria-label={`The ${slot.label}, in order`}>
            {rows.map((row, at) => (
              <PlacementRow
                key={row.key}
                row={row}
                state={states[at] ?? "live"}
                index={at}
                count={rows.length}
                kinds={slot.kinds}
                typeLabel={row.item ? labelOf(types, row.item.type) : ""}
                onMove={(to) => {
                  move(dragging ?? at, dragging === null ? to : at);
                }}
                onRemove={() => {
                  onRows(rows.filter((_, index) => index !== at));
                }}
                onDates={() => {
                  setDating(at);
                }}
                onKind={(kind) => {
                  if (row.link) change(at, { link: { ...row.link, kind } });
                }}
                dragging={dragging}
                onDragging={setDragging}
                disabled={saving}
              />
            ))}
          </ol>
        )}
        {room <= 0 ? <p className="mf-featured-hint">A player holds {String(MAX_PLACEMENTS)} at most.</p> : null}
      </Card>
      {picking ? (
        <Picker
          slotKey={slot.key}
          types={onTypes}
          first={picking}
          taken={taken}
          onAdd={addRef}
          onClose={() => {
            setPicking(null);
          }}
        />
      ) : null}
      {pasting ? (
        <PasteLinks
          kinds={slot.kinds}
          room={room}
          onAdd={addVideos}
          onClose={() => {
            setPasting(false);
          }}
        />
      ) : null}
      {dated && dating !== null ? (
        <DatesDialog
          title={titleOf(dated)}
          starts={dated.starts_at}
          ends={dated.ends_at}
          onSave={(starts, ends) => {
            change(dating, { starts_at: starts, ends_at: ends });
            setDating(null);
          }}
          onClose={() => {
            setDating(null);
          }}
        />
      ) : null}
    </div>
  );
}

export default function Players() {
  const session = useSession();
  const mayMake = session.status === "signed-in" && session.can(SLOT_MANAGE);
  const queryClient = useQueryClient();
  const toast = useToast();
  const listed = useApiQuery("get", SLOTS);
  const slots = listed.data?.items ?? [];
  const types = listed.data?.types ?? [];
  const fulls = useQueries({ queries: slots.map((slot) => apiQueryOptions("get", SLOT, { params: { path: { key: slot.key } } })) });
  const [params, setParams] = useSearchParams();
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [refused, setRefused] = useState<{ key: string; error: unknown; row: number | null } | null>(null);
  const [conflict, setConflict] = useState<Conflict | null>(null);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<AdminSlot | "new" | null>(null);
  const busy = useRef(false);

  const fullOf = (key: string): FullSlot | undefined => fulls[slots.findIndex((slot) => slot.key === key)]?.data;
  const savedRows = (key: string): Row[] => (fullOf(key)?.items ?? []).map(rowOf);
  const rowsOf = (key: string): Row[] => drafts[key]?.rows ?? savedRows(key);
  const changed = slots.flatMap((slot) => {
    const draft = drafts[slot.key];
    if (!draft) return [];
    const words = changesOf(savedRows(slot.key), draft.rows);
    return words.length ? [{ slot, draft, words }] : [];
  });
  const count = changed.reduce((sum, each) => sum + each.words.length, 0);
  const what = changed.map((each) => (changed.length > 1 ? `${each.slot.label}: ${each.words.join(", ")}` : each.words.join(", "))).join("; ");
  const selected = params.get("slot") ?? slots[0]?.key ?? "";

  const drop = (key: string) => {
    setDrafts((now) => Object.fromEntries(Object.entries(now).filter(([each]) => each !== key)));
  };
  const setRows = (key: string, rows: Row[]) => {
    setRefused(null);
    // A list back as it's saved is no draft: a later read of the slot shows through again (cubic on #157).
    if (changesOf(savedRows(key), rows).length === 0) {
      drop(key);
      return;
    }
    const version = drafts[key]?.version ?? fullOf(key)?.version ?? 1;
    setDrafts((now) => ({ ...now, [key]: { version, rows } }));
  };
  /** The tab in the address; none (the first) once its player is removed. */
  const select = (key: string | null) => {
    setParams(
      (now) => {
        const next = new URLSearchParams(now);
        if (key) next.set("slot", key);
        else next.delete("slot");
        return next;
      },
      { replace: true },
    );
  };

  /** Each changed list in turn; true once all are saved. */
  async function saveAll(only: { key: string; draft: Draft }[] = changed.map((each) => ({ key: each.slot.key, draft: each.draft }))): Promise<boolean> {
    if (busy.current) return false;
    busy.current = true;
    setSaving(true);
    setRefused(null);
    try {
      for (const { key, draft } of only) {
        try {
          const { data } = await api.PUT("/api/featured/admin/slots/{key}/placements", {
            params: { path: { key } },
            body: { version: draft.version, items: bodyOf(draft.rows) },
          });
          if (data) queryClient.setQueryData(["get", SLOT, { params: { path: { key } } }], data);
          // Only the draft this save sent: one that differs is kept, to be saved again.
          setDrafts((now) => (now[key] === draft ? Object.fromEntries(Object.entries(now).filter(([each]) => each !== key)) : now));
          if (conflict?.key === key) setConflict(null);
          void queryClient.invalidateQueries({ queryKey: ["get", SLOTS] });
          void queryClient.invalidateQueries({ queryKey: ["get", LIVE] });
        } catch (error) {
          select(key);
          const theirs = error instanceof ApiProblem && error.code === "featured.changed" ? (error.extra.slot as FullSlot | undefined) : undefined;
          if (theirs) {
            setConflict({
              key,
              theirs,
              said: {
                detail: error instanceof ApiProblem ? error.detail : "",
                version: theirs.version,
                conflicts: [{ field: "list", yours: draft.rows.map(titleOf), theirs: theirs.items.map((each) => titleOf(rowOf(each))) }],
                at: null,
              },
            });
          } else {
            setRefused({ key, error, row: rowRefused(error) });
          }
          return false;
        }
      }
      toast({ tone: "success", text: only.length === 1 ? "Saved. It's live on the site." : "Saved. They're live on the site." });
      return true;
    } finally {
      busy.current = false;
      setSaving(false);
    }
  }

  function resolve(choice: "theirs" | "mine") {
    if (!conflict) return;
    const { key, theirs } = conflict;
    queryClient.setQueryData(["get", SLOT, { params: { path: { key } } }], theirs);
    setConflict(null);
    if (choice === "theirs") {
      drop(key);
      return;
    }
    // Mine, at their version: a placement they removed is added again as new.
    const there = new Set(theirs.items.map((each) => each.id));
    const rows = rowsOf(key).map((row) => (row.id && !there.has(row.id) ? { ...row, id: null } : row));
    const draft = { version: theirs.version, rows };
    setDrafts((now) => ({ ...now, [key]: draft }));
    void saveAll([{ key, draft }]);
  }

  const guard = useUnsavedGuard(count > 0, async () => ((await saveAll()) ? null : ""));

  const lead = "Choose what plays in the homepage's players, in what order, and when.";
  const actions = (
    <>
      <a className={buttonClass({})} href="/" target="_blank" rel="noreferrer">
        Open homepage <Icon name="external" />
      </a>
      {mayMake ? (
        <Button
          icon="plus"
          onClick={() => {
            setSettings("new");
          }}
        >
          New player
        </Button>
      ) : null}
    </>
  );

  let body;
  if (listed.error) body = <LoadError what="The players" error={listed.error} onRetry={() => void listed.refetch()} />;
  else if (!listed.data) body = null;
  else if (slots.length === 0)
    body = (
      <EmptyState
        title="No players yet"
        action={
          mayMake ? (
            <Button
              variant="primary"
              icon="plus"
              onClick={() => {
                setSettings("new");
              }}
            >
              Make the first player
            </Button>
          ) : undefined
        }
      >
        {mayMake ? "A player is one of the homepage's lists, such as the Spotlight's tracks. Its key is what the site's code reads." : "An admin makes the homepage's players. Ask one to, and they'll show here."}
      </EmptyState>
    );
  else
    body = (
      <Tabs
        label="Players"
        selected={selected}
        onSelect={select}
        tabs={slots.map((slot, at) => {
          const full = fulls[at];
          const rows = rowsOf(slot.key);
          return {
            id: slot.key,
            label: (
              <>
                {slot.label} <span className="mf-featured-count">{full?.data ? rows.length : ""}</span>
              </>
            ),
            panel: full?.error ? (
              <LoadError what={`The ${slot.label}`} error={full.error} onRetry={() => void full.refetch()} />
            ) : full?.data ? (
              <SlotPanel
                slot={slot}
                full={full.data}
                rows={rows}
                types={types}
                mayMake={mayMake}
                refused={refused?.key === slot.key ? refused : null}
                conflict={conflict?.key === slot.key ? conflict : null}
                saving={saving}
                onRows={(next) => {
                  setRows(slot.key, next);
                }}
                onSettings={() => {
                  setSettings(slot);
                }}
                onResolve={resolve}
                onCancelConflict={() => {
                  setConflict(null);
                }}
              />
            ) : null,
          };
        })}
      />
    );

  return (
    <AdminPage page="Players" title="Players" lead={lead} actions={actions}>
      {body}
      <SaveBar
        changes={count}
        what={what}
        saving={saving}
        saveLabel="Save and go live"
        onSave={() => void saveAll()}
        onDiscard={() => {
          setDrafts({});
          setRefused(null);
          setConflict(null);
        }}
      />
      <UnsavedDialog guard={guard} what="These players" />
      {settings ? (
        <SlotSettings
          slot={settings === "new" ? null : settings}
          types={types}
          first={slots.length === 0}
          onDone={(key) => {
            // No key back is a player removed: its draft goes, and the address names none (cubic on #157).
            if (!key && settings !== "new") drop(settings.key);
            setSettings(null);
            select(key);
          }}
          onClose={() => {
            setSettings(null);
          }}
        />
      ) : null}
    </AdminPage>
  );
}

