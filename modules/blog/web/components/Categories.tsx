// The board's Categories card (`dev plans/contracts/blog.md` §2): each
// category with its posts, and for staff holding kernel.taxonomy.manage, Edit,
// which adds, renames and deletes them through the kernel's term routes
// (hook 2). A deleted category leaves its posts with none.
import { useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import {
  ApiProblem,
  Button,
  Dialog,
  Field,
  Input,
  LoadError,
  api as kernel,
  failureWords,
  useSession,
  useToast,
} from "@/kernel";

import { CATEGORIES, LIST, PUBLIC_LIST, useApiQuery, type AdminCategory } from "../api";
import { slugFor } from "../editing";

const MANAGE = "kernel.taxonomy.manage";

function posts(count: number): string {
  return count === 1 ? "1 post" : `${String(count)} posts`;
}

export function Categories() {
  const session = useSession();
  const mayManage = session.status === "signed-in" && session.can(MANAGE);
  const listed = useApiQuery("get", CATEGORIES);
  const [editing, setEditing] = useState(false);
  if (listed.error) return <LoadError what="The categories" error={listed.error} onRetry={() => void listed.refetch()} />;
  if (!listed.data) return null;
  const items = listed.data.items;
  return (
    <div className="mf-blog-categories">
      {items.length ? (
        <ul className="mf-blog-category-list">
          {items.map((each) => (
            <li key={each.id}>
              <span>{each.label}</span>
              <span className="mf-blog-count">{posts(each.posts)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mf-field-hint">No categories yet.{mayManage ? " Edit adds the first." : ""}</p>
      )}
      {mayManage ? (
        <Button
          size="small"
          onClick={() => {
            setEditing(true);
          }}
        >
          Edit categories
        </Button>
      ) : null}
      {editing ? (
        <EditCategories
          items={items}
          onClose={() => {
            setEditing(false);
          }}
        />
      ) : null}
    </div>
  );
}

function EditCategories({ items, onClose }: { items: readonly AdminCategory[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [labels, setLabels] = useState<Record<string, string>>(() => Object.fromEntries(items.map((each) => [each.id, each.label])));
  const [added, setAdded] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function act(what: () => Promise<unknown>, done: string) {
    setBusy(true);
    setProblem(null);
    try {
      await what();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["get", CATEGORIES] }),
        queryClient.invalidateQueries({ queryKey: ["get", LIST] }),
        queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_LIST] }),
      ]);
      toast({ tone: "success", text: done });
    } catch (error) {
      setProblem(error instanceof ApiProblem && error.code === "kernel.term_exists" ? "There's a category with that address already." : error instanceof Error ? failureWords(error) : "That didn't go through. Try again.");
    } finally {
      setBusy(false);
    }
  }

  function add(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const label = added.trim();
    const slug = slugFor(label);
    if (!slug) {
      setProblem("A category's name needs letters or digits.");
      return;
    }
    const position = Math.max(-1, ...items.map((each) => each.position)) + 1;
    void act(async () => {
      await kernel.POST("/api/kernel/admin/terms", { body: { vocabulary: "blog_category", slug, label, position } });
      setAdded("");
    }, `${label} is added.`);
  }

  return (
    <Dialog title="Edit categories" onClose={onClose} wide>
      <p className="mf-dialog-lead">A post sits in one category. Deleting one leaves its posts with none.</p>
      <ul className="mf-blog-edit-list">
        {items.map((each) => {
          const label = labels[each.id] ?? each.label;
          return (
            <li key={each.id}>
              <Field label={`Name of ${each.label}`} hint={posts(each.posts)}>
                <Input
                  value={label}
                  maxLength={80}
                  onChange={(event) => {
                    setLabels((now) => ({ ...now, [each.id]: event.target.value }));
                  }}
                />
              </Field>
              <div className="mf-blog-edit-actions">
                <Button
                  size="small"
                  disabled={busy || !label.trim() || label.trim() === each.label}
                  onClick={() =>
                    void act(
                      () => kernel.PATCH("/api/kernel/admin/terms/{term_id}", { params: { path: { term_id: each.id } }, body: { label: label.trim() } }),
                      `${label.trim()} is saved.`,
                    )
                  }
                >
                  Rename
                </Button>
                <Button
                  size="small"
                  disabled={busy}
                  onClick={() => void act(() => kernel.DELETE("/api/kernel/admin/terms/{term_id}", { params: { path: { term_id: each.id } } }), `${each.label} is deleted.`)}
                >
                  Delete
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      <form className="mf-blog-add" onSubmit={add}>
        <Field label="New category" error={problem ?? undefined}>
          <Input
            value={added}
            maxLength={80}
            onChange={(event) => {
              setAdded(event.target.value);
            }}
          />
        </Field>
        <Button type="submit" disabled={busy || !added.trim()}>
          Add
        </Button>
      </form>
      <div className="mf-dialog-actions">
        <Button variant="primary" onClick={onClose}>
          Done
        </Button>
      </div>
    </Dialog>
  );
}
