/**
 * `/account/profile`, "Profile" (decision 0061; contract
 * dev plans/contracts/account-name.md; VM Website design/site/Account.dc.html's
 * first pill): the name the site shows for the person, to staff and on what
 * they publish. Changing it needs no recent sign-in: a name opens nothing.
 * The server cleans what's typed (spaces, the ends) and answers the session,
 * which takes its place in the cache, so the person card and "Signed in as"
 * change at once.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { api } from "../api/client";
import { setSessionUser, useSession } from "../session/session";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Dialog } from "../ui/Dialog";
import { Field, Input } from "../ui/Field";
import { AccountPage, Row, Rows, useAction } from "./AccountPage";

/** The column's length (decision 0061); the server counts after cleaning. */
export const NAME_MAX = 120;
const PEOPLE = ["get", "/api/auth/admin/users"] as const;

export default function Profile() {
  const session = useSession();
  if (session.status !== "signed-in") return null;
  return (
    <AccountPage page="Profile" title="Profile" lead="How this site names you.">
      <div className="mf-account-grid">
        <Name name={session.user.name ?? null} />
      </div>
    </AccountPage>
  );
}

function Name({ name }: { name: string | null }) {
  const queryClient = useQueryClient();
  const { busy, run } = useAction();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const close = () => {
    if (busy) return;
    setOpen(false);
    setError("");
  };

  const save = (event: SubmitEvent) => {
    event.preventDefault();
    setError("");
    void run(
      async () => {
        const { data } = await api.PUT("/api/auth/account/name", { body: { name: typed } });
        if (data) await setSessionUser(queryClient, data.user);
      },
      {
        done: "Saved your name.",
        reads: [PEOPLE],
        refused: { "kernel.invalid_request": "A name is up to 120 characters, on one line." },
      },
    ).then((result) => {
      if (result.ok) setOpen(false);
      else setError(result.error);
    });
  };

  return (
    <Card title="Name" description="Shown to staff, and on what you publish here.">
      <Rows label="Your name">
        <Row
          name={name ?? "No name yet"}
          actions={
            <Button
              onClick={() => {
                setTyped(name ?? "");
                setOpen(true);
              }}
            >
              {name ? "Change name" : "Add a name"}
            </Button>
          }
        />
      </Rows>
      {open ? (
        <Dialog title="Your name" onClose={close}>
          <form className="mf-dialog-form" noValidate onSubmit={save}>
            <Field label="Name" hint="Up to 120 characters. Leave it empty for none." error={error || undefined}>
              <Input
                autoComplete="name"
                maxLength={NAME_MAX * 2}
                value={typed}
                onChange={(event) => {
                  setTyped(event.target.value);
                }}
              />
            </Field>
            <div className="mf-dialog-actions">
              <Button onClick={close}>Cancel</Button>
              <Button type="submit" variant="primary" disabled={busy}>
                Save
              </Button>
            </div>
          </form>
        </Dialog>
      ) : null}
    </Card>
  );
}
