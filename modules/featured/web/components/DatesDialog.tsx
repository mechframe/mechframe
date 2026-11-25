// A row's dates (`dev plans/contracts/featured.md` §8, 7: what the board doesn't
// draw): when it starts and when it ends, each in the viewer's own time, either
// left blank. A start alone waits for its day; an end alone takes it off then;
// neither is always. Saving the list puts them live.
import { useState } from "react";

import { Button, Dialog, Field, Input } from "@/kernel";

export type DatesDialogProps = {
  title: string;
  starts: string | null;
  ends: string | null;
  onSave: (starts: string | null, ends: string | null) => void;
  onClose: () => void;
};

const pad = (n: number) => String(n).padStart(2, "0");

/** An ISO time as a `datetime-local` input's value, in the viewer's zone. */
export function localOf(iso: string | null): string {
  if (!iso) return "";
  const at = new Date(iso);
  return `${String(at.getFullYear())}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}T${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

/** A `datetime-local` value as an ISO time with its zone, or null when blank. */
export function isoOf(local: string): string | null {
  if (!local) return null;
  const at = new Date(local);
  return Number.isNaN(at.getTime()) ? null : at.toISOString();
}

/** Whether a `datetime-local` value is a time the viewer's clocks show: one the spring's change skips isn't. */
export function exists(local: string): boolean {
  const at = isoOf(local);
  return at !== null && localOf(at) === local;
}

export function DatesDialog({ title, starts, ends, onSave, onClose }: DatesDialogProps) {
  const [start, setStart] = useState(localOf(starts));
  const [end, setEnd] = useState(localOf(ends));
  // A date left as it was keeps its own time to the second: the input holds only minutes.
  const startAt = start === localOf(starts) ? starts : isoOf(start);
  const endAt = end === localOf(ends) ? ends : isoOf(end);
  // A time the clocks skip (02:30 on the spring's change) would be saved an hour on: say so instead (cubic on #157).
  const skipped = (local: string, at: string | null) => (local && at && !exists(local) ? "That time doesn't exist on that day: the clocks change then." : "");
  const startWrong = start === localOf(starts) ? "" : skipped(start, startAt);
  const endWrong = end === localOf(ends) ? "" : skipped(end, endAt);
  const order = startAt && endAt && Date.parse(endAt) <= Date.parse(startAt) ? "The end has to be after the start." : "";
  const wrong = startWrong || endWrong || order;
  return (
    <Dialog title={`Dates of ${title}`} onClose={onClose}>
      <form
        className="mf-featured-stack"
        onSubmit={(event) => {
          event.preventDefault();
          if (wrong) return;
          onSave(startAt, endAt);
        }}
      >
        <p className="mf-featured-hint">Leave a date blank for none: with neither, it plays always. Times are your own, {Intl.DateTimeFormat().resolvedOptions().timeZone}.</p>
        <Field label="Starts" hint="It goes live then." error={startWrong || undefined}>
          <Input
            type="datetime-local"
            value={start}
            onChange={(event) => {
              setStart(event.target.value);
            }}
          />
        </Field>
        <Field label="Ends" hint="It comes off then." error={endWrong || order || undefined}>
          <Input
            type="datetime-local"
            value={end}
            onChange={(event) => {
              setEnd(event.target.value);
            }}
          />
        </Field>
        <div className="mf-dialog-actions">
          <Button
            type="button"
            onClick={() => {
              setStart("");
              setEnd("");
            }}
          >
            Clear both
          </Button>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={Boolean(wrong)}>
            Set the dates
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
