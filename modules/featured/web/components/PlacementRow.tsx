// One row of a player's list (VM Website `AdminPlayers.dc.html`, `placement`): the
// drag grip, with Move up and Move down for the keyboard; the picture (an item's
// cover, or YouTube's mark for a video: nothing loads from YouTube here); the title
// and its line; a video's kind; the dates, which open the dates dialog; the pill;
// and Remove.
import type { DragEvent } from "react";

import { Button, Icon, Pill, Select } from "@/kernel";

import { PILLS, datesWords, titleOf, type Kind, type Row, type State } from "../api";

export type PlacementRowProps = {
  row: Row;
  state: State;
  index: number;
  count: number;
  kinds: readonly Kind[];
  /** The type's label, for an item whose module is off. */
  typeLabel: string;
  onMove: (to: number) => void;
  onRemove: () => void;
  onDates: () => void;
  onKind: (kind: string | null) => void;
  /** The row dragged now, shared by the list. */
  dragging: number | null;
  onDragging: (index: number | null) => void;
};

/** The words under a row's title. */
function lineOf(row: Row, typeLabel: string): string {
  if (row.ref) return row.ref.line;
  if (row.link) return `youtu.be/${row.link.video_id}`;
  if (row.removed) return "Its page is gone. Saving leaves it out.";
  return `${typeLabel} are switched off on the site. Saving keeps it.`;
}

export function PlacementRow({ row, state, index, count, kinds, typeLabel, onMove, onRemove, onDates, onKind, dragging, onDragging }: PlacementRowProps) {
  const title = titleOf(row);
  const pill = PILLS[state];
  const drop = (event: DragEvent<HTMLLIElement>) => {
    event.preventDefault();
    if (dragging !== null && dragging !== index) onMove(index);
    onDragging(null);
  };
  return (
    <li
      className={`mf-featured-row${dragging === index ? " mf-featured-row--dragged" : ""}`}
      draggable
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", title);
        onDragging(index);
      }}
      onDragEnd={() => {
        onDragging(null);
      }}
      onDragOver={(event) => {
        if (dragging !== null) event.preventDefault();
      }}
      onDrop={drop}
    >
      <span className="mf-featured-grip" aria-hidden="true" title="Drag to reorder">
        <Icon name="grip" />
      </span>
      <span className="mf-featured-order">
        <Button size="small" icon="chevron-down" className="mf-featured-up" aria-label={`Move ${title} up`} disabled={index === 0} onClick={() => {
            onMove(index - 1);
          }} />
        <Button size="small" icon="chevron-down" aria-label={`Move ${title} down`} disabled={index === count - 1} onClick={() => {
            onMove(index + 1);
          }} />
      </span>
      {row.link ? (
        <span className="mf-featured-mark" role="img" aria-label="YouTube">
          <Icon name="play" />
        </span>
      ) : row.ref?.image ? (
        <img className="mf-featured-cover" src={row.ref.image} alt="" width={44} height={44} loading="lazy" />
      ) : (
        <span className="mf-featured-cover mf-featured-cover--none" aria-hidden="true">
          <Icon name="music" />
        </span>
      )}
      <span className="mf-featured-words">
        <span className="mf-featured-title">{title}</span>
        <span className="mf-featured-line">{lineOf(row, typeLabel)}</span>
      </span>
      {row.link ? (
        <Select
          className="mf-featured-kind"
          aria-label={`Kind of ${title}`}
          value={row.link.kind ?? ""}
          onChange={(event) => {
            onKind(event.target.value || null);
          }}
        >
          <option value="">No kind</option>
          {kinds.map((each) => (
            <option key={each.key} value={each.key}>
              {each.label}
            </option>
          ))}
        </Select>
      ) : null}
      <Button size="small" icon="calendar" className="mf-featured-dates" aria-label={`Dates of ${title}: ${datesWords(row.starts_at, row.ends_at)}`} onClick={onDates} disabled={row.removed}>
        {datesWords(row.starts_at, row.ends_at)}
      </Button>
      <Pill tone={pill.tone}>{pill.label}</Pill>
      <Button size="small" icon="close" aria-label={`Remove ${title}`} onClick={onRemove} />
    </li>
  );
}
