// The two pages a newsletter's links open (`dev plans/contracts/campaigns.md` §2):
// /newsletter/confirm and /newsletter/unsubscribe. Each says what its link is for,
// with one button, then the done state. Opening one changes nothing, since link
// scanners open links; only the button does. Both are noindex.
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { ApiProblem, Button, Seo, useSite } from "@/kernel";

import { api, type SubscriptionLink } from "../api";
import "../campaigns.css";

type Kind = "confirm" | "unsubscribe";

const WORDS: Record<Kind, { title: string; lead: string; button: string; done: string; path: string }> = {
  confirm: {
    title: "Confirm your subscription",
    lead: "Press Confirm to start getting the site's news and releases by email.",
    button: "Confirm",
    done: "You're subscribed",
    path: "/newsletter/confirm",
  },
  unsubscribe: {
    title: "Unsubscribe from the newsletter",
    lead: "Press Unsubscribe and the site won't email you its news again. Messages about your own account aren't affected.",
    button: "Unsubscribe",
    done: "You're unsubscribed",
    path: "/newsletter/unsubscribe",
  },
};

async function act(kind: Kind, token: string): Promise<SubscriptionLink> {
  const { data } =
    kind === "confirm"
      ? await api.POST("/api/campaigns/confirm", { body: { token } })
      : await api.POST("/api/campaigns/unsubscribe", { params: { query: { token } } });
  if (!data) throw new Error("The site answered without the subscription.");
  return data;
}

function doneLine(kind: Kind, link: SubscriptionLink): string {
  if (kind === "unsubscribe") return `${link.email_hint} won't get the newsletter again.`;
  if (link.subscribed) return `The news goes to ${link.email_hint} from now on.`;
  return `${link.email_hint} isn't on the list: it unsubscribed or was set aside, so nothing is sent to it.`;
}

export function LinkPage({ kind }: { kind: Kind }) {
  const words = WORDS[kind];
  const site = useSite();
  const [search] = useSearchParams();
  const token = search.get("token") ?? "";
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<SubscriptionLink | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const answer = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (done || failed) answer.current?.focus();
  }, [done, failed]);

  const press = async () => {
    setBusy(true);
    setFailed(null);
    try {
      setDone(await act(kind, token));
    } catch (error) {
      setFailed(
        error instanceof ApiProblem && error.status === 404
          ? "This link isn't one the site knows. Use the newest email's link."
          : "That didn't go through. Try again in a moment.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="mf-newsletter-page">
      <Seo title={site ? `${words.title} · ${site.name}` : words.title} description={words.lead} path={words.path} noindex />
      {done ? (
        <div role="status" tabIndex={-1} ref={answer} className="mf-newsletter-done">
          <h1>{words.done}</h1>
          <p>{doneLine(kind, done)}</p>
        </div>
      ) : (
        <>
          <h1>{words.title}</h1>
          {token ? (
            <>
              <p>{words.lead}</p>
              <Button variant="primary" onClick={() => void press()} disabled={busy}>
                {busy ? "Just a moment…" : words.button}
              </Button>
            </>
          ) : (
            <p>This page needs the link from the email. Open the link in the newest email to {kind === "confirm" ? "confirm" : "unsubscribe"}.</p>
          )}
          {failed ? (
            <div role="alert" tabIndex={-1} ref={answer} className="mf-newsletter-error">
              {failed}
            </div>
          ) : null}
        </>
      )}
    </article>
  );
}
