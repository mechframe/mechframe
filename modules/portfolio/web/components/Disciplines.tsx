// Edit disciplines (`dev plans/contracts/portfolio.md` §2): for staff holding
// kernel.taxonomy.manage, add, rename and delete the disciplines through the
// kernel's term routes (hook 2), as blog's categories are. A deleted discipline
// leaves its pieces with none, shown under All only.
import { useQueryClient } from "@tanstack/react-query";
import { useState, type SubmitEvent } from "react";

import { ApiProblem, Button, Dialog, Field, Input, api as kernel, failureWords, useToast } from "@/kernel";

import { DISCIPLINES, LIST, PUBLIC_DISCIPLINES, PUBLIC_LIST, type AdminDiscipline } from "../api";
import { slugFor } from "../editing";

export const TAXONOMY = "kernel.taxonomy.manage";
/** Where an error about adding a discipline is said. */
const ADD_ROW = "add";

function pieces(count: number): string {
  return count === 1 ? "1 piece" : `${String(count)} pieces`;
}

export function EditDisciplines({ items, onClose }: { items: readonly AdminDiscipline[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [labels, setLabels] = useState<Record<string, string>>(() => Object.fromEntries(items.map((each) => [each.id, each.label])));
  const [added, setAdded] = useState("");
  const [busy, setBusy] = useState(false);
  // Said where it went wrong: beside the row renamed or deleted, or under New discipline (cubic on #171).
  const [problem, setProblem] = useState<{ where: string; text: string } | null>(null);

  async function act(what: () => Promise<unknown>, done: string, where: string = ADD_ROW) {
    setBusy(true);
    setProblem(null);
    try {
      await what();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["get", DISCIPLINES] }),
        queryClient.invalidateQueries({ queryKey: ["get", LIST] }),
        queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_LIST] }),
        queryClient.invalidateQueries({ queryKey: ["get", PUBLIC_DISCIPLINES] }),
      ]);
      toast({ tone: "success", text: done });
    } catch (error) {
      setProblem({
        where,
        text:
          error instanceof ApiProblem && error.code === "kernel.term_exists"
            ? "There's a discipline with that address already."
            : error instanceof Error
              ? failureWords(error)
              : "That didn't go through. Try again.",
      });
    } finally {
      setBusy(false);
    }
  }

  function add(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const label = added.trim();
    const slug = slugFor(label);
    if (!slug) {
      setProblem({ where: ADD_ROW, text: "A discipline's name needs letters or digits." });
      return;
    }
    if (slug === "piece") {
      setProblem({ where: ADD_ROW, text: "That name is taken by a piece's own address. Choose another." });
      return;
    }
    const position = Math.max(-1, ...items.map((each) => each.position)) + 1;
    void act(async () => {
      await kernel.POST("/api/kernel/admin/terms", { body: { vocabulary: "portfolio_discipline", slug, label, position } });
      setAdded("");
    }, `${label} is added.`);
  }

  return (
    <Dialog title="Edit disciplines" onClose={onClose} wide>
      <p className="mf-dialog-lead">A piece sits in one discipline. Deleting one leaves its pieces with none: they show under All only.</p>
      <ul className="mf-portfolio-edit-list">
        {items.map((each) => {
          const label = labels[each.id] ?? each.label;
          return (
            <li key={each.id}>
              <Field label={`Name of ${each.label}`} hint={pieces(each.pieces)} error={problem?.where === each.id ? problem.text : undefined}>
                <Input
                  value={label}
                  maxLength={80}
                  onChange={(event) => {
                    setLabels((now) => ({ ...now, [each.id]: event.target.value }));
                  }}
                />
              </Field>
              <div className="mf-portfolio-edit-actions">
                <Button
                  size="small"
                  disabled={busy || !label.trim() || label.trim() === each.label}
                  onClick={() =>
                    void act(
                      () => kernel.PATCH("/api/kernel/admin/terms/{term_id}", { params: { path: { term_id: each.id } }, body: { label: label.trim() } }),
                      `${label.trim()} is saved.`,
                      each.id,
                    )
                  }
                >
                  Rename
                </Button>
                <Button
                  size="small"
                  disabled={busy}
                  onClick={() => void act(() => kernel.DELETE("/api/kernel/admin/terms/{term_id}", { params: { path: { term_id: each.id } } }), `${each.label} is deleted.`, each.id)}
                >
                  Delete
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      <form className="mf-portfolio-add" onSubmit={add}>
        <Field label="New discipline" error={problem?.where === ADD_ROW ? problem.text : undefined}>
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
