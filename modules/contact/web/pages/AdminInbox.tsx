// The Inbox, /admin/contact and /admin/contact/:id (`dev plans/contracts/contact.md`
// §2; the canvas's AdminInbox board): the waiting card, the five tabs with their
// counts, the list, and the open message beside it (alone on a phone, with Back).
// Replies go from the reader's own email; the site only marks the message.
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { AdminPage, Attention, Button, Card, Dialog, EmptyState, LoadError, Pill, Tabs, buttonClass, useToast, when } from "@/kernel";

import {
  LIST,
  ONE,
  STATUS_WORDS,
  TABS,
  api,
  exportAll,
  reasonWords,
  toCsv,
  useApiMutation,
  useApiQuery,
  morePages,
  type InboxItem,
  type InboxMessage,
  type More,
  type Status,
  type Tab,
} from "../api";
import "../contact.css";

const TONE = { new: "warning", replied: "success", archived: "neutral", spam: "danger" } as const;

function tabOf(value: string | null): Tab {
  return TABS.some((tab) => tab.id === value) ? (value as Tab) : "all";
}

function Row({ item, tab, open }: { item: InboxItem; tab: Tab; open: boolean }) {
  return (
    <li>
      <Link
        className="mf-contact-row"
        to={`/admin/contact/${item.id}${tab === "all" ? "" : `?tab=${tab}`}`}
        aria-current={open ? "true" : undefined}
      >
        <span className="mf-contact-row-head">
          <span className="mf-contact-row-name">{item.name}</span>
          <span className="mf-contact-row-time">{when(item.received_at)}</span>
        </span>
        <span className="mf-contact-row-topic">
          {item.topic_label}
          {tab === "all" && item.status !== "new" ? <Pill tone={TONE[item.status]}>{STATUS_WORDS[item.status]}</Pill> : null}
        </span>
        <span className="mf-contact-row-line">{item.first_line}</span>
      </Link>
    </li>
  );
}

function List({ tab, open }: { tab: Tab; open: string | undefined }) {
  const listed = useApiQuery("get", LIST, { params: { query: { status: tab } } });
  // The pages after the first, for the first page they follow: a new read of
  // the first (a status changed, another tab) starts over from it.
  const [extra, setExtra] = useState<More | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreFailed, setMoreFailed] = useState(false);
  if (listed.error) return <LoadError what="The messages" error={listed.error} onRetry={() => void listed.refetch()} />;
  if (!listed.data) return null;
  const more = extra?.after === listed.dataUpdatedAt ? extra : null;
  const items = [...listed.data.items, ...(more?.items ?? [])];
  const next = more ? more.next : listed.data.next_cursor;
  if (!items.length) {
    return (
      <EmptyState title={tab === "spam" ? "No spam" : "No messages here"}>
        {tab === "spam" ? "Messages the bot check or the filters hold show here." : "New messages from the contact form show here."}
      </EmptyState>
    );
  }
  const showMore = async () => {
    if (!next) return;
    const after = listed.dataUpdatedAt;
    setLoadingMore(true);
    setMoreFailed(false);
    try {
      const { data } = await api.GET(LIST, { params: { query: { status: tab, cursor: next } } });
      if (!data) throw new Error("The next page didn't answer.");
      setExtra((before) => morePages(before, after, data));
    } catch {
      // The rows already shown stay, and Show more tries the same page again.
      setMoreFailed(true);
    } finally {
      setLoadingMore(false);
    }
  };
  return (
    <div className="mf-contact-list">
      <ul aria-label="Messages">
        {items.map((item) => (
          <Row key={item.id} item={item} tab={tab} open={item.id === open} />
        ))}
      </ul>
      {moreFailed ? (
        <p className="mf-contact-error" role="alert">
          The next messages couldn&rsquo;t be loaded.
        </p>
      ) : null}
      {next ? (
        <Button size="small" onClick={() => void showMore()} disabled={loadingMore}>
          {loadingMore ? "Loading…" : "Show more"}
        </Button>
      ) : null}
    </div>
  );
}

function OpenMessage({ id, tab }: { id: string; tab: Tab }) {
  const path = { params: { path: { message_id: id } } };
  const read = useApiQuery("get", ONE, path);
  const change = useApiMutation("post", "/api/contact/admin/messages/{message_id}/status");
  const remove = useApiMutation("delete", ONE);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const back = `/admin/contact${tab === "all" ? "" : `?tab=${tab}`}`;

  if (read.error) return <LoadError what="This message" error={read.error} onRetry={() => void read.refetch()} />;
  if (!read.data) return null;
  const message: InboxMessage = read.data;
  const held = reasonWords(message.held_reason);

  const move = (status: Status, said: string) => {
    change.mutate(
      { ...path, body: { status } },
      {
        onSuccess: (moved) => {
          queryClient.setQueryData(["get", ONE, path], moved);
          void queryClient.invalidateQueries({ queryKey: ["get", LIST] });
          toast({ tone: "success", text: said });
        },
        onError: () => {
          toast({ tone: "danger", text: "That didn't save. Try again." });
        },
      },
    );
  };

  const reply = `mailto:${encodeURIComponent(message.email)}?subject=${encodeURIComponent(`Re: ${message.topic_label}`)}`;
  return (
    <Card className="mf-contact-open">
      <Link className="mf-contact-back" to={back}>
        Back to the messages
      </Link>
      <div className="mf-contact-open-head">
        <h2>{message.name}</h2>
        <p className="mf-contact-meta">
          <a href={`mailto:${encodeURIComponent(message.email)}`}>{message.email}</a>, received {when(message.received_at)}
        </p>
        <p className="mf-contact-meta">
          <Pill tone={TONE[message.status]}>{STATUS_WORDS[message.status]}</Pill> {message.topic_label}
          {message.wants_news ? <span className="mf-contact-news-pill">Wants the newsletter</span> : null}
        </p>
        {held ? <p className="mf-contact-held">Set apart: {held}.</p> : null}
      </div>
      <p className="mf-contact-body">{message.message}</p>
      <div className="mf-contact-actions">
        <a className={buttonClass({ variant: "primary" })} href={reply}>
          Reply by email
        </a>
        {message.status === "spam" ? (
          <Button onClick={() => { move("new", "Back in New."); }} disabled={change.isPending}>
            Not spam
          </Button>
        ) : (
          <>
            {message.status !== "replied" ? (
              <Button onClick={() => { move("replied", "Marked as replied."); }} disabled={change.isPending}>
                Mark as replied
              </Button>
            ) : null}
            {message.status !== "archived" ? (
              <Button onClick={() => { move("archived", "Archived."); }} disabled={change.isPending}>
                Archive
              </Button>
            ) : null}
            <Button onClick={() => { move("spam", "Moved to Spam."); }} disabled={change.isPending}>
              Spam
            </Button>
          </>
        )}
        <Button onClick={() => { setAsking(true); }}>Delete</Button>
      </div>
      <p className="mf-contact-note">Replies go from your own email, so the conversation carries on there.</p>
      {asking ? (
        <Dialog title="Delete this message?" onClose={() => { setAsking(false); }}>
          <p>It goes for good, for a sender who asks to be forgotten. Archive it to keep it out of the way.</p>
          <div className="mf-contact-actions">
            <Button
              variant="primary"
              disabled={remove.isPending}
              onClick={() => { remove.mutate(path, {
                  onSuccess: () => {
                    setAsking(false);
                    queryClient.removeQueries({ queryKey: ["get", ONE, path] });
                    void queryClient.invalidateQueries({ queryKey: ["get", LIST] });
                    toast({ tone: "success", text: "Deleted." });
                    void navigate(back);
                  },
                  onError: () => {
                    toast({ tone: "danger", text: "It wasn't deleted. Try again." });
                  },
                }); }
              }
            >
              Delete it
            </Button>
            <Button onClick={() => { setAsking(false); }}>Keep it</Button>
          </div>
        </Dialog>
      ) : null}
    </Card>
  );
}

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export default function AdminInbox() {
  const { id } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const tab = tabOf(search.get("tab"));
  const toast = useToast();
  const listed = useApiQuery("get", LIST, { params: { query: { status: tab } } });
  const [exporting, setExporting] = useState(false);
  const counts = listed.data?.counts;
  const waiting = listed.data?.waiting;

  const exportTab = async () => {
    setExporting(true);
    try {
      const messages = await exportAll(tab);
      download(`messages-${tab}-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(messages));
    } catch {
      toast({ tone: "danger", text: "The export didn't download. Try again." });
    } finally {
      setExporting(false);
    }
  };

  const label = (each: (typeof TABS)[number]) => {
    if (!counts) return each.label;
    const count = each.id === "all" ? counts.new + counts.replied + counts.archived : counts[each.id];
    return `${each.label} (${String(count)})`;
  };

  return (
    <AdminPage
      page="Inbox"
      title="Inbox"
      lead="Messages from the contact form. New messages on a first topic come first."
      actions={
        <Button icon="upload" onClick={() => void exportTab()} disabled={exporting}>
          {exporting ? "Exporting…" : "Export"}
        </Button>
      }
    >
      <div className={id ? "mf-contact-inbox mf-contact-inbox--open" : "mf-contact-inbox"}>
        {waiting ? <Attention tone={waiting.tone} what={waiting.what} why={waiting.why} action={{ label: waiting.label, to: waiting.to }} /> : null}
        <Tabs
          label="Messages"
          selected={tab}
          onSelect={(next) => {
            // Back to the list: an open message belongs to the tab it was opened from (CodeRabbit on #125).
            void navigate(next === "all" ? "/admin/contact" : `/admin/contact?tab=${next}`);
          }}
          tabs={TABS.map((each) => ({
            id: each.id,
            label: label(each),
            panel:
              each.id === tab ? (
                <div className="mf-contact-layout">
                  <List tab={tab} open={id} />
                  {id ? <OpenMessage key={id} id={id} tab={tab} /> : null}
                </div>
              ) : null,
          }))}
        />
      </div>
    </AdminPage>
  );
}
