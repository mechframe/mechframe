// The Share card (`content.share`; `dev plans/contracts/social.md` §2): a published
// thing shared to the site's channels through Buffer, from its own admin page. It
// opens from the database alone; Check the channels and Refresh ask Buffer. Each
// refusal comes back in words before anything leaves, and a share that may have
// gone says so.
import { useState } from "react";

import {
  ApiProblem,
  Attention,
  Button,
  Card,
  Chip,
  Field,
  Input,
  LinkButton,
  LoadError,
  Pill,
  Select,
  TextArea,
  failureWords,
  useToast,
  type SharePartProps,
} from "@/kernel";

import { MODE_WORDS, SHARES, STATE_TONE, STATE_WORDS, api, dayAndTime, lengthFor, useApiQuery, type Channel, type Mode, type Share } from "./api";
import "./social.css";

const MODES: Mode[] = ["queue", "now", "at", "draft"];

function History({ shares, onTakeBack, busy }: { shares: Share[]; onTakeBack: (share: Share) => void; busy: boolean }) {
  return (
    <ul className="mf-social-history" aria-label="Shared so far">
      {shares.map((share) => (
        <li key={share.id} className="mf-social-share">
          <div className="mf-social-share-head">
            <span className="mf-social-share-channel">
              {share.channel_name} <span className="mf-social-quiet">({share.network})</span>
            </span>
            <Pill tone={STATE_TONE[share.state]}>{STATE_WORDS[share.state]}</Pill>
          </div>
          <p className="mf-social-quiet">
            {dayAndTime(share.created_at)}
            {share.sent_by_name ? `, by ${share.sent_by_name}` : ""}
            {share.due_at && (share.state === "queued" || share.state === "draft") ? `. Goes out ${dayAndTime(share.due_at)}` : ""}
          </p>
          {share.error ? <p className="mf-social-error">{share.error}</p> : null}
          <div className="mf-social-share-actions">
            {share.external_link ? (
              <a href={share.external_link} target="_blank" rel="noreferrer noopener">
                See it on {share.network}
              </a>
            ) : null}
            {share.state === "queued" || share.state === "draft" ? (
              <Button
                size="small"
                disabled={busy}
                onClick={() => {
                  onTakeBack(share);
                }}
              >
                Take it back
              </Button>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function SharePanel({ type, id, live, adminPath }: SharePartProps) {
  const toast = useToast();
  const view = useApiQuery("get", SHARES, { params: { query: { type, id } } });
  const [typed, setTyped] = useState<string | null>(null);
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const [when, setWhen] = useState<Mode>("queue");
  const [at, setAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState("");
  const [sharedBefore, setSharedBefore] = useState("");

  const title = <>Share</>;
  const description = "To the site's channels, through Buffer.";
  if (view.isError) {
    return (
      <Card title={title} description={description} className="mf-social-card">
        <LoadError what="The sharing card" error={view.error} onRetry={() => void view.refetch()} inline />
      </Card>
    );
  }
  if (!view.data) {
    return (
      <Card title={title} description={description} className="mf-social-card">
        <p className="mf-social-quiet">Loading…</p>
      </Card>
    );
  }
  const state = view.data;
  const text = typed ?? state.text;
  const usable = state.channels.filter((channel) => channel.usable);
  const unusable = state.channels.filter((channel) => !channel.usable);
  const chosen = usable.filter((channel) => picked.has(channel.id));
  const link = state.card?.url ?? "";

  const run = async (work: () => Promise<void>) => {
    setBusy(true);
    setRefused("");
    try {
      await work();
    } catch (error) {
      if (error instanceof ApiProblem && error.code === "social.shared_before") setSharedBefore(error.detail);
      else setRefused(failureWords(error));
    } finally {
      setBusy(false);
      void view.refetch();
    }
  };

  const check = () =>
    run(async () => {
      await api.POST("/api/social/admin/channels");
      toast({ tone: "success", text: "The channels are checked." });
    });

  const share = (again: boolean) =>
    run(async () => {
      setSharedBefore("");
      const { data } = await api.POST("/api/social/admin/shares", {
        body: {
          type,
          id,
          admin_path: adminPath,
          channel_ids: chosen.map((channel) => channel.id),
          text,
          when,
          due_at: when === "at" && at ? new Date(at).toISOString() : null,
          again,
        },
      });
      const results = data?.results ?? [];
      const taken = results.filter((one) => one.state !== "refused" && one.state !== "unknown").length;
      toast({
        tone: taken === results.length ? "success" : "danger",
        text: taken === results.length ? `Shared to ${results.length === 1 ? "1 channel" : `${results.length.toString()} channels`}.` : "Some of it didn't go. Each channel says why below.",
      });
      setPicked(new Set());
    });

  const refresh = () =>
    run(async () => {
      await api.POST("/api/social/admin/shares/refresh", { body: { type, id } });
    });

  const takeBack = (one: Share) =>
    run(async () => {
      await api.DELETE("/api/social/admin/shares/{share_id}", { params: { path: { share_id: one.id } } });
      toast({ tone: "success", text: `Taken back from ${one.channel_name}.` });
    });

  const tightest = chosen
    .filter((channel): channel is Channel & { limit: number } => channel.limit !== null)
    .map((channel) => ({ channel, length: lengthFor(channel, text, link) }))
    .sort((one, other) => other.length / other.channel.limit - one.length / one.channel.limit)[0];
  const tooLong = tightest !== undefined && tightest.length > tightest.channel.limit;

  return (
    <Card title={title} description={description} className="mf-social-card">
      {state.unreadable ? (
        <Attention tone="danger" what="The saved Buffer token can't be read" why="This happens when the server's ENCRYPTION_KEYS change. An admin can save it again in Settings, under Social." />
      ) : null}
      {!state.unreadable && state.source === "none" ? (
        <div className="mf-social-stack">
          <p className="mf-social-quiet">Sharing goes through Buffer. An admin can save its token in Settings, under Social.</p>
          <div>
            <LinkButton size="small" to="/admin/settings">
              Open Settings
            </LinkButton>
          </div>
        </div>
      ) : null}
      {!state.unreadable && state.source !== "none" && state.channels.length === 0 ? (
        <div className="mf-social-stack">
          <p className="mf-social-quiet">Buffer's channels aren't listed yet.</p>
          <div>
            <Button size="small" disabled={busy} onClick={() => void check()}>
              {busy ? "Checking…" : "Check the channels"}
            </Button>
          </div>
        </div>
      ) : null}
      {state.ready && !(live && state.live) ? <p className="mf-social-quiet">Share it once it's published.</p> : null}
      {state.ready && live && state.live ? (
        <form
          className="mf-social-form"
          onSubmit={(event) => {
            event.preventDefault();
            void share(false);
          }}
        >
          <fieldset className="mf-social-channels">
            <legend>Channels</legend>
            <div className="mf-social-chips">
              {usable.map((channel) => (
                <Chip
                  key={channel.id}
                  pressed={picked.has(channel.id)}
                  onPressedChange={(pressed) => {
                    const next = new Set(picked);
                    if (pressed) next.add(channel.id);
                    else next.delete(channel.id);
                    setPicked(next);
                  }}
                >
                  {channel.name} ({channel.network})
                </Chip>
              ))}
            </div>
            {unusable.length > 0 ? (
              <ul className="mf-social-unusable">
                {unusable.map((channel) => (
                  <li key={channel.id}>{channel.problem}</li>
                ))}
              </ul>
            ) : null}
            {usable.some((channel) => channel.queue_paused) ? (
              <p className="mf-social-quiet">A paused queue in Buffer holds what's queued until it's resumed there.</p>
            ) : null}
          </fieldset>
          <Field
            label="Text"
            hint={tightest ? `${tightest.length.toLocaleString()} of ${tightest.channel.limit.toLocaleString()} characters for ${tightest.channel.network}, the link included.` : "The link goes at its end, or as LinkedIn's card."}
            error={tooLong ? `Too long for ${tightest.channel.network}. Shorten the text.` : undefined}
          >
            <TextArea
              rows={4}
              maxLength={5000}
              value={text}
              onChange={(event) => {
                setTyped(event.target.value);
              }}
            />
          </Field>
          <Field label="When">
            <Select
              value={when}
              onChange={(event) => {
                setWhen(event.target.value as Mode);
              }}
            >
              {MODES.map((mode) => (
                <option key={mode} value={mode}>
                  {MODE_WORDS[mode]}
                </option>
              ))}
            </Select>
          </Field>
          {when === "at" ? (
            <Field label="Goes out at" hint="In your own time zone, at least a minute ahead.">
              <Input
                type="datetime-local"
                value={at}
                onChange={(event) => {
                  setAt(event.target.value);
                }}
              />
            </Field>
          ) : null}
          {sharedBefore ? (
            <div className="mf-social-stack">
              <Attention tone="warning" what="It's been shared there before" why={sharedBefore} />
              <div>
                <Button disabled={busy} onClick={() => void share(true)}>
                  Share again
                </Button>
              </div>
            </div>
          ) : null}
          {refused ? (
            <p className="mf-social-error" role="alert">
              {refused}
            </p>
          ) : null}
          <div className="mf-social-actions">
            <Button size="small" disabled={busy} onClick={() => void check()}>
              Check the channels
            </Button>
            <Button type="submit" variant="primary" disabled={busy || chosen.length === 0 || !text.trim() || tooLong || (when === "at" && !at)}>
              {busy ? "Sharing…" : "Share"}
            </Button>
          </div>
        </form>
      ) : null}
      {refused && !(state.ready && live && state.live) ? (
        <p className="mf-social-error" role="alert">
          {refused}
        </p>
      ) : null}
      {state.history.length > 0 ? (
        <div className="mf-social-stack">
          <div className="mf-social-history-head">
            <h3>Shared so far</h3>
            <Button size="small" disabled={busy} onClick={() => void refresh()}>
              Refresh
            </Button>
          </div>
          <History shares={state.history} onTakeBack={(one) => void takeBack(one)} busy={busy} />
        </div>
      ) : null}
    </Card>
  );
}
