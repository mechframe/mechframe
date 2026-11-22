// The editor's Related posts (`dev plans/contracts/blog.md` §2; VybeSite's
// related_posts.py): up to three live posts, in the order shown under the post.
// Find one by its title among the live posts; move it up, or remove it.
import { useDeferredValue, useState } from "react";

import { Button, SearchBox } from "@/kernel";

import { LIST, useApiQuery } from "../api";
import { MAX_RELATED, type RelatedPick } from "../editing";

export type RelatedPickerProps = {
  /** The post being edited, never a pick of its own; null for a new one. */
  self: string | null;
  value: readonly RelatedPick[];
  onChange: (next: RelatedPick[]) => void;
};

export function RelatedPicker({ self, value, onChange }: RelatedPickerProps) {
  const [q, setQ] = useState("");
  const words = useDeferredValue(q.trim());
  const full = value.length >= MAX_RELATED;
  const found = useApiQuery(
    "get",
    LIST,
    { params: { query: { status: "published", ...(words ? { q: words } : {}) } } },
    { enabled: words.length > 0 && !full },
  );
  const taken = new Set([...value.map((each) => each.id), ...(self ? [self] : [])]);
  const offered = (found.data?.items ?? []).filter((post) => !taken.has(post.id)).slice(0, 5);

  return (
    <div className="mf-blog-related">
      {value.length ? (
        <ol className="mf-blog-related-list">
          {value.map((each, index) => (
            <li key={each.id}>
              <span className="mf-blog-related-title">{each.title}</span>
              <span className="mf-blog-related-actions">
                {index > 0 ? (
                  <Button
                    size="small"
                    aria-label={`Move ${each.title} up`}
                    onClick={() => {
                      const next = [...value];
                      next.splice(index - 1, 2, each, value[index - 1] as RelatedPick);
                      onChange(next);
                    }}
                  >
                    Up
                  </Button>
                ) : null}
                <Button
                  size="small"
                  aria-label={`Remove ${each.title}`}
                  onClick={() => {
                    onChange(value.filter((other) => other.id !== each.id));
                  }}
                >
                  Remove
                </Button>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mf-field-hint">None yet. They show under the post, up to {MAX_RELATED}.</p>
      )}
      {full ? (
        <p className="mf-field-hint">That's {MAX_RELATED}, the most a post lists.</p>
      ) : (
        <>
          <SearchBox
            label="Find a live post"
            value={q}
            onChange={(event) => {
              setQ(event.target.value);
            }}
          />
          {words && found.data ? (
            offered.length ? (
              <ul className="mf-blog-related-found" aria-label="Live posts found">
                {offered.map((post) => (
                  <li key={post.id}>
                    <span>{post.title}</span>
                    <Button
                      size="small"
                      aria-label={`Add ${post.title}`}
                      onClick={() => {
                        onChange([...value, { id: post.id, title: post.title, slug: post.slug }]);
                        setQ("");
                      }}
                    >
                      Add
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mf-field-hint">No live post by that name.</p>
            )
          ) : null}
        </>
      )}
    </div>
  );
}
