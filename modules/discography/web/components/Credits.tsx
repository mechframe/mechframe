// Credit rows, a role and a name each, added and removed in place: the album
// editor's for a release, the Tracks board's for a track (`dev plans/contracts/
// discography.md` §8, 5e). A row left without a name isn't saved. Each row
// keeps its key and a removal moves the focus (`rows.ts`).
import { Button, Field, Input, Select } from "@/kernel";

import { MAX_NAME } from "../api";
import type { CreditRow } from "../editing";
import { useFocusAfterRemoval, useRowKeys } from "../rows";

export function Credits({
  rows,
  roles,
  error,
  onChange,
}: {
  rows: readonly CreditRow[];
  roles: readonly { id: string; name: string }[];
  error?: string | undefined;
  onChange: (rows: CreditRow[]) => void;
}) {
  const { keys, added, removed } = useRowKeys(rows.length);
  const { rowsRef, removedAt } = useFocusAfterRemoval<HTMLDivElement>();
  const put = (index: number, row: CreditRow) => {
    onChange(rows.map((each, at) => (at === index ? row : each)));
  };
  return (
    <div ref={rowsRef} className="mf-music-stack">
      {rows.length ? (
        <ul className="mf-music-list">
          {rows.map((row, index) => (
            <li key={keys[index] ?? index} className="mf-music-credit mf-music-credit--role">
              <Field label="Role">
                <Select
                  data-row-first
                  value={row.role_id}
                  onChange={(event) => {
                    put(index, { ...row, role_id: event.target.value });
                  }}
                >
                  <option value="">Choose a role</option>
                  {roles.map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Name">
                <Input
                  value={row.name}
                  maxLength={MAX_NAME}
                  onChange={(event) => {
                    put(index, { ...row, name: event.target.value });
                  }}
                />
              </Field>
              <Button
                size="small"
                icon="close"
                aria-label={`Remove the credit ${row.name.trim() || String(index + 1)}`}
                onClick={() => {
                  removed(index);
                  removedAt(index);
                  onChange(rows.filter((_, at) => at !== index));
                }}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="mf-music-hint">No credits yet.</p>
      )}
      {error ? <p className="mf-music-error">{error}</p> : null}
      <div>
        <Button
          size="small"
          icon="plus"
          data-row-add
          onClick={() => {
            added();
            onChange([...rows, { role_id: roles[0]?.id ?? "", name: "" }]);
          }}
        >
          Add a credit
        </Button>
      </div>
    </div>
  );
}
