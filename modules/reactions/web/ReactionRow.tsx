// The row of reactions under a thing (`content.reactions`; `dev plans/contracts/reactions.md`
// §2): one button per reaction the site offers, its icon, its count and its name,
// pressed when it's the reader's own. Pressing changes the count at once and puts it
// back if the server refuses. Signed out, the counts show and pressing goes to sign-in;
// an unverified member is told to verify their address first. A thing the site
// doesn't show now, or a read that fails, draws nothing: the page goes on without it.
import { useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { ApiProblem, failureWords, signInFor, useSession, useToast, type ReactionPartProps } from "@/kernel";

import { PRESS, READ, api, readOf, useApiQuery, type Counted, type Reactions } from "./api";
import { ReactionIcon } from "./icons";
import "./reactions.css";

const UNVERIFIED = "reactions.email_unverified";

/** The thing's row with `key` pressed or let go, in the palette's order. */
function toggled(item: Counted, key: string, on: boolean, order: string[]): Counted {
  const mine = on ? item.mine.filter((each) => each !== key) : [...item.mine, key];
  return {
    ...item,
    counts: { ...item.counts, [key]: Math.max(0, (item.counts[key] ?? 0) + (on ? -1 : 1)) },
    mine: order.filter((each) => mine.includes(each)),
  };
}

export default function ReactionRow({ type, id }: ReactionPartProps) {
  const session = useSession();
  const init = readOf(type, id);
  const found = useApiQuery("get", READ, init);
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const { pathname, search, hash } = useLocation();
  const [unverified, setUnverified] = useState(false);
  // The keys whose press is on its way: another press of one waits for its answer.
  const sending = useRef(new Set<string>());

  const item = found.data?.items[0];
  if (!found.data || !item) return null;
  const palette = found.data.palette;
  const order = palette.map((choice) => choice.key);
  const queryKey = ["get", READ, init];

  const set = (next: (row: Counted) => Counted) => {
    queryClient.setQueryData<Reactions>(queryKey, (current) =>
      current ? { ...current, items: current.items.map((each) => (each.id === id ? next(each) : each)) } : current,
    );
  };

  const press = async (key: string) => {
    if (session.status !== "signed-in") {
      void navigate(signInFor(`${pathname}${search}${hash}`));
      return;
    }
    if (!session.user.verified) {
      setUnverified(true);
      return;
    }
    if (sending.current.has(key)) return;
    const shown = queryClient.getQueryData<Reactions>(queryKey)?.items.find((each) => each.id === id) ?? item;
    const on = shown.mine.includes(key);
    sending.current.add(key);
    set((row) => toggled(row, key, on, order));
    try {
      const at = { params: { path: { type, id, key } } };
      const { data } = on ? await api.DELETE(PRESS, at) : await api.PUT(PRESS, at);
      if (data) set(() => data);
    } catch (error) {
      set((row) => toggled(row, key, !on, order));
      if (error instanceof ApiProblem && error.code === UNVERIFIED) setUnverified(true);
      else toast({ tone: "danger", text: failureWords(error) || "That reaction wasn't saved. Try again." });
      void queryClient.invalidateQueries({ queryKey });
    } finally {
      sending.current.delete(key);
    }
  };

  return (
    <div className="mf-reactions">
      <div role="group" aria-label="Reactions" className="mf-reactions-row">
        {palette.map((choice) => {
          const on = item.mine.includes(choice.key);
          const count = item.counts[choice.key] ?? 0;
          return (
            <button
              key={choice.key}
              type="button"
              className="mf-reaction"
              // Its name and its count, "Fire, 3": the count is the words it shows.
              aria-label={`${choice.label}, ${String(count)}`}
              aria-pressed={on}
              onClick={() => void press(choice.key)}
            >
              <ReactionIcon name={choice.key} />
              <span className="mf-reaction-count">{count}</span>
            </button>
          );
        })}
      </div>
      {unverified ? (
        <p className="mf-reactions-note" role="status">
          Verify your email address first. <Link to="/account">Go to your account</Link>
        </p>
      ) : null}
    </div>
  );
}
