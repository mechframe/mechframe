// Everyone credited, /admin/music/credits (`dev plans/contracts/discography.md` §2;
// the canvas's AdminCredits board): a note for a name not linked to a profile yet,
// the table of names with their profile state and what each is credited for, Edit
// for a name and its profile state, and the Roles card with its list edited in
// place. Credits themselves are added on a release, in the album editor, and on a
// track, on the Tracks board. Linking a name to a member's profile waits for
// roster (step 3).
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  AdminPage,
  ApiProblem,
  Attention,
  Button,
  Card,
  Dialog,
  Field,
  Input,
  LoadError,
  Select,
  Table,
  failureWords,
  useToast,
  type Column,
} from "@/kernel";

import { MAX_NAME, MAX_ROLE, PEOPLE, PROFILE_WORDS, RELEASES, ROLES, TRACKS, api, useApiQuery, type AdminPerson, type AdminRole, type Profile } from "../api";
import "../music.css";

/** The states staff may set; `member` is roster's to set when it links a profile. */
const SETTABLE: readonly Exclude<Profile, "member">[] = ["unlinked", "collective", "not_member"];

function problemOf(error: unknown): string {
  if (error instanceof ApiProblem) return Object.values(error.errors).flat().join(" ") || error.detail;
  return error instanceof Error ? failureWords(error) : "That didn't go through. Try again.";
}

function EditPerson({ person, onClose }: { person: AdminPerson; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(person.name);
  const [profile, setProfile] = useState<Profile>(person.profile);
  const [refused, setRefused] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    setRefused(null);
    try {
      const change: { version: number; name?: string; profile?: Exclude<Profile, "member"> } = { version: person.version };
      if (name.trim() !== person.name) change.name = name.trim();
      if (profile !== person.profile && profile !== "member") change.profile = profile;
      const { data } = await api.PATCH("/api/discography/admin/people/{person_id}", { params: { path: { person_id: person.id } }, body: change });
      if (data) queryClient.setQueryData(["get", PEOPLE], data);
      void queryClient.invalidateQueries({ queryKey: ["get", RELEASES] });
      void queryClient.invalidateQueries({ queryKey: ["get", TRACKS] });
      toast({ tone: "success", text: "Saved." });
      onClose();
    } catch (error) {
      setRefused(error);
      if (error instanceof ApiProblem && error.code === "discography.changed") void queryClient.invalidateQueries({ queryKey: ["get", PEOPLE] });
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={`Edit ${person.name}`} onClose={onClose}>
      <form
        className="mf-music-stack"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <Field label="Name" hint="Every credit to this name changes with it.">
          <Input
            value={name}
            maxLength={MAX_NAME}
            required
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </Field>
        <Field label="Profile" hint={person.profile === "member" ? "Linked to a member's profile." : "Linking a name to a member's profile comes with the collective's pages."}>
          <Select
            value={profile}
            disabled={person.profile === "member"}
            onChange={(event) => {
              setProfile(event.target.value as Profile);
            }}
          >
            {person.profile === "member" ? <option value="member">{PROFILE_WORDS.member}</option> : null}
            {SETTABLE.map((each) => (
              <option key={each} value={each}>
                {PROFILE_WORDS[each]}
              </option>
            ))}
          </Select>
        </Field>
        {refused ? <p className="mf-music-error">{problemOf(refused)}</p> : null}
        <div className="mf-dialog-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !name.trim() || (name.trim() === person.name && profile === person.profile)}>
            Save
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

type RoleRow = { id: string | null; name: string; credits: number };

function EditRoles({ roles, onClose }: { roles: readonly AdminRole[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [rows, setRows] = useState<RoleRow[]>(roles.map((each) => ({ id: each.id, name: each.name, credits: each.credits })));
  const [refused, setRefused] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  function put(index: number, row: RoleRow) {
    setRows((now) => now.map((each, at) => (at === index ? row : each)));
  }
  function move(index: number, by: -1 | 1) {
    setRows((now) => {
      const next = [...now];
      const [one] = next.splice(index, 1);
      if (one) next.splice(index + by, 0, one);
      return next;
    });
  }
  async function save() {
    setBusy(true);
    setRefused(null);
    try {
      const items = rows.filter((each) => each.name.trim()).map((each) => (each.id ? { id: each.id, name: each.name.trim() } : { name: each.name.trim() }));
      const { data } = await api.PUT(ROLES, { body: { items } });
      if (data) queryClient.setQueryData(["get", ROLES], data);
      void queryClient.invalidateQueries({ queryKey: ["get", PEOPLE] });
      toast({ tone: "success", text: "The roles are saved." });
      onClose();
    } catch (error) {
      setRefused(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title="Edit the roles" onClose={onClose}>
      <form
        className="mf-music-stack"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <ol className="mf-music-list">
          {rows.map((row, index) => (
            <li key={row.id ?? `new-${String(index)}`} className="mf-music-credit">
              <Field label={`Role ${String(index + 1)}`} hint={row.credits ? (row.credits === 1 ? "1 credit names it" : `${String(row.credits)} credits name it`) : undefined}>
                <Input
                  value={row.name}
                  maxLength={MAX_ROLE}
                  onChange={(event) => {
                    put(index, { ...row, name: event.target.value });
                  }}
                />
              </Field>
              <span className="mf-music-order">
                <Button size="small" icon="chevron-down" className="mf-music-up" aria-label={`Move ${row.name || "this role"} up`} disabled={index === 0} onClick={() => {
                    move(index, -1);
                  }} />
                <Button size="small" icon="chevron-down" aria-label={`Move ${row.name || "this role"} down`} disabled={index === rows.length - 1} onClick={() => {
                    move(index, 1);
                  }} />
              </span>
              <Button
                size="small"
                icon="close"
                aria-label={`Remove ${row.name || "this role"}`}
                disabled={row.credits > 0}
                onClick={() => {
                  setRows((now) => now.filter((_, at) => at !== index));
                }}
              />
            </li>
          ))}
        </ol>
        <p className="mf-music-hint">A role that credits name stays until they're changed.</p>
        <div>
          <Button
            size="small"
            icon="plus"
            onClick={() => {
              setRows((now) => [...now, { id: null, name: "", credits: 0 }]);
            }}
          >
            Add a role
          </Button>
        </div>
        {refused ? <p className="mf-music-error">{problemOf(refused)}</p> : null}
        <div className="mf-dialog-actions">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={busy || !rows.some((each) => each.name.trim())}>
            Save the roles
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export default function AdminCredits() {
  const people = useApiQuery("get", PEOPLE);
  const roles = useApiQuery("get", ROLES);
  const [editing, setEditing] = useState<AdminPerson | null>(null);
  const [roling, setRoling] = useState(false);
  const everyone = people.data?.items ?? [];
  const unlinked = everyone.find((each) => each.profile === "unlinked");

  const columns: readonly Column<AdminPerson>[] = [
    { key: "name", header: "Name", cell: (person) => person.name },
    { key: "profile", header: "Profile", cell: (person) => PROFILE_WORDS[person.profile] },
    { key: "for", header: "Credited for", cell: (person) => person.credited_for },
    {
      key: "edit",
      header: <span className="mf-visually-hidden">Actions</span>,
      align: "end",
      cell: (person) => (
        <Button
          size="small"
          aria-label={`Edit ${person.name}`}
          onClick={() => {
            setEditing(person);
          }}
        >
          Edit
        </Button>
      ),
    },
  ];

  return (
    <AdminPage page="Credits" title="Credits" lead="Everyone credited on a release or a track. Credits are added in a release's editor and on the Tracks board.">
      {unlinked && people.data ? (
        <Attention
          tone="info"
          what={people.data.unlinked === 1 ? `“${unlinked.name}” isn't linked to a profile` : `${String(people.data.unlinked)} names aren't linked to a profile`}
          why={`${unlinked.name} is credited for ${unlinked.credited_for}. Mark the collective's own name, and anyone who isn't a member, so the list shows who's left to link.`}
        />
      ) : null}
      <div className="mf-music-board mf-music-board--panel">
        <div className="mf-music-main">
          {people.error ? (
            <LoadError what="The credits" error={people.error} onRetry={() => void people.refetch()} />
          ) : people.data ? (
            <Table caption="People credited" captionHidden columns={columns} rows={everyone} rowKey={(person) => person.id} empty="No one is credited yet." />
          ) : null}
        </div>
        <div className="mf-music-side">
          <Card
            title="Roles"
            level={2}
            actions={
              roles.data ? (
                <Button
                  size="small"
                  onClick={() => {
                    setRoling(true);
                  }}
                >
                  Edit
                </Button>
              ) : null
            }
          >
            {roles.error ? (
              <LoadError what="The roles" error={roles.error} onRetry={() => void roles.refetch()} inline />
            ) : (
              <dl className="mf-music-roles">
                {(roles.data?.items ?? []).map((role) => (
                  <div key={role.id}>
                    <dt>{role.name}</dt>
                    <dd>{role.credits === 0 ? "None yet" : role.credits === 1 ? "1 credit" : `${String(role.credits)} credits`}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Card>
        </div>
      </div>
      {editing ? (
        <EditPerson
          key={editing.id}
          person={editing}
          onClose={() => {
            setEditing(null);
          }}
        />
      ) : null}
      {roling && roles.data ? (
        <EditRoles
          roles={roles.data.items}
          onClose={() => {
            setRoling(false);
          }}
        />
      ) : null}
    </AdminPage>
  );
}
