// The picker (`dev plans/contracts/featured.md` §8, 7): what "Add track" opens. A
// search, a type's filter where the player takes two, a page of the site's things
// at a time with Load more, drafts too (they go live with their own page), and Add.
import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Dialog, Field, Input, LoadError, Select } from "@/kernel";

import { SLOT, api, singular, type AdminRef, type TypeLabel } from "../api";

export type PickerProps = {
  slotKey: string;
  /** The types this player takes whose modules are on, by label. */
  types: readonly TypeLabel[];
  /** The type its button named. */
  first: string;
  /** What's in the list already, by `type:id`. */
  taken: ReadonlySet<string>;
  onAdd: (type: string, ref: AdminRef) => void;
  onClose: () => void;
};

export function Picker({ slotKey, types, first, taken, onAdd, onClose }: PickerProps) {
  const [type, setType] = useState(first);
  const [typed, setTyped] = useState("");
  const [words, setWords] = useState("");
  const label = types.find((each) => each.type === type)?.label ?? type;
  const pages = useInfiniteQuery({
    queryKey: ["get", `${SLOT}/pick`, slotKey, type, words],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET("/api/featured/admin/slots/{key}/pick", {
        params: { path: { key: slotKey }, query: { type, ...(words ? { q: words } : {}), ...(pageParam ? { cursor: pageParam } : {}) } },
      });
      if (!data) throw new Error("The site answered without the list.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
    retry: false,
  });
  const found = pages.data?.pages.flatMap((page) => page.items) ?? [];
  return (
    <Dialog title={`Add ${singular(label)}`} onClose={onClose} wide>
      <div className="mf-featured-stack">
        <form
          role="search"
          className="mf-featured-search"
          onSubmit={(event) => {
            event.preventDefault();
            setWords(typed.trim());
          }}
        >
          {types.length > 1 ? (
            <Field label="Show">
              <Select
                value={type}
                onChange={(event) => {
                  setType(event.target.value);
                }}
              >
                {types.map((each) => (
                  <option key={each.type} value={each.type}>
                    {each.label}
                  </option>
                ))}
              </Select>
            </Field>
          ) : null}
          <Field label={`Search ${label.toLowerCase()}`}>
            <Input
              type="search"
              value={typed}
              maxLength={200}
              onChange={(event) => {
                setTyped(event.target.value);
              }}
            />
          </Field>
          <Button type="submit" icon="search">
            Search
          </Button>
        </form>
        {pages.error ? (
          <LoadError what={label} error={pages.error} onRetry={() => void pages.refetch()} inline />
        ) : pages.isPending ? (
          <p className="mf-featured-hint" role="status">
            Looking…
          </p>
        ) : found.length === 0 ? (
          <p className="mf-featured-hint" role="status">
            {words ? `Nothing in ${label.toLowerCase()} matches “${words}”.` : `There are no ${label.toLowerCase()} yet.`}
          </p>
        ) : (
          <ul className="mf-featured-choices" aria-label={label}>
            {found.map((ref) => {
              const added = taken.has(`${type}:${ref.id}`);
              return (
                <li key={ref.id} className="mf-featured-choice">
                  {ref.image ? <img className="mf-featured-cover" src={ref.image} alt="" width={44} height={44} loading="lazy" /> : <span className="mf-featured-cover mf-featured-cover--none" aria-hidden="true" />}
                  <span className="mf-featured-words">
                    <span className="mf-featured-title">{ref.title}</span>
                    <span className="mf-featured-line">{ref.live ? ref.line : `${ref.line}. Not on the site yet: it shows once it's live.`}</span>
                  </span>
                  <Button
                    size="small"
                    icon={added ? "check" : "plus"}
                    aria-label={added ? `${ref.title} is in the list` : `Add ${ref.title}`}
                    disabled={added}
                    onClick={() => {
                      onAdd(type, ref);
                    }}
                  >
                    {added ? "Added" : "Add"}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        <div className="mf-dialog-actions">
          {pages.hasNextPage ? (
            <Button disabled={pages.isFetchingNextPage} onClick={() => void pages.fetchNextPage()}>
              {pages.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          ) : null}
          <Button variant="primary" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
