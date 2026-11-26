// The Newsletter page, /admin/campaigns (`dev plans/contracts/campaigns.md` §2; the
// canvas's AdminNewsletter board): the intro and New email, the attention card for
// addresses that bounced, the cards Subscribed, Scheduled and Set aside, and the tabs
// Emails, Subscribers and Set aside with the board's columns and pills. The tabs of
// people show to those who hold `campaigns.subscriber.manage`.
import { useInfiniteQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import {
  AdminPage,
  Attention,
  Button,
  Dialog,
  EmptyState,
  Field,
  Input,
  LinkButton,
  LoadError,
  Pill,
  Select,
  StatCard,
  Table,
  Tabs,
  useSession,
  useToast,
  type Column,
} from "@/kernel";

import {
  EMAILS,
  KIND_WORDS,
  SET_ASIDE,
  STATUS_TONE,
  STATUS_WORDS,
  SUBSCRIBERS,
  SUBSCRIBER_PERMISSION,
  SUBSCRIBER_TONE,
  SUBSCRIBER_WORDS,
  api,
  day,
  dayAndTime,
  people,
  sourceWords,
  whyWords,
  type CampaignEmailItem,
  type EmailsPage,
  type SetAsideAddress,
  type Subscriber,
} from "../api";
import "../campaigns.css";

type Tab = "emails" | "subscribers" | "set-aside";
type Page<Item> = { items: Item[]; next_cursor: string | null };

const LISTS = ["campaigns", "lists"] as const;

function tabOf(value: string | null, mayPeople: boolean): Tab {
  if (mayPeople && (value === "subscribers" || value === "set-aside")) return value;
  return "emails";
}

/** One of the three lists, page after page as Show more asks. */
function useList<P extends { next_cursor: string | null }>(name: Tab, read: (cursor: string | null) => Promise<P>) {
  return useInfiniteQuery<P, Error, InfiniteData<P>, readonly unknown[], string | null>({
    queryKey: [...LISTS, name],
    queryFn: ({ pageParam }) => read(pageParam),
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor,
  });
}

async function emailsPage(cursor: string | null): Promise<EmailsPage> {
  const { data } = await api.GET(EMAILS, { params: { query: cursor === null ? {} : { cursor } } });
  if (!data) throw new Error("The emails didn't answer.");
  return data;
}

async function subscribersPage(cursor: string | null): Promise<Page<Subscriber>> {
  const { data } = await api.GET(SUBSCRIBERS, { params: { query: cursor === null ? {} : { cursor } } });
  if (!data) throw new Error("The subscribers didn't answer.");
  return data;
}

async function setAsidePage(cursor: string | null): Promise<Page<SetAsideAddress> & { reads_bounces: boolean }> {
  const { data } = await api.GET(SET_ASIDE, { params: { query: cursor === null ? {} : { cursor } } });
  if (!data) throw new Error("The addresses set aside didn't answer.");
  return data;
}

function More({ list }: { list: { hasNextPage: boolean; isFetchingNextPage: boolean; fetchNextPage: () => Promise<unknown> } }) {
  if (!list.hasNextPage) return null;
  return (
    <Button size="small" onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>
      {list.isFetchingNextPage ? "Loading…" : "Show more"}
    </Button>
  );
}

const EMAIL_COLUMNS: readonly Column<CampaignEmailItem>[] = [
  {
    key: "email",
    header: "Email",
    cell: (row) => (
      <span className="mf-newsletter-cell">
        <span className="mf-newsletter-subject">{row.subject}</span>
        <span className="mf-newsletter-quiet">{KIND_WORDS[row.kind]}</span>
      </span>
    ),
  },
  { key: "status", header: "Status", cell: (row) => <Pill tone={STATUS_TONE[row.status]}>{STATUS_WORDS[row.status]}</Pill> },
  {
    key: "sent",
    header: "Sent to",
    cell: (row) => (row.status === "draft" ? <span className="mf-newsletter-quiet">Not sent</span> : people(row.sent_to)),
  },
  {
    key: "when",
    header: "When",
    cell: (row) =>
      row.when === null ? <span className="mf-newsletter-quiet">Not sent</span> : row.status === "scheduled" ? dayAndTime(row.when) : day(row.when),
  },
  {
    key: "open",
    header: <span className="mf-visually-hidden">Open</span>,
    align: "end",
    cell: (row) => (
      <Link to={`/admin/campaigns/${row.id}`} aria-label={`Open ${row.subject}`}>
        Open
      </Link>
    ),
  },
];

function Emails() {
  const list = useList("emails", emailsPage);
  if (list.error) return <LoadError what="The emails" error={list.error} onRetry={() => void list.refetch()} />;
  if (!list.data) return null;
  const rows = list.data.pages.flatMap((page) => page.items);
  return (
    <div className="mf-newsletter-list">
      <Table
        caption="Emails"
        captionHidden
        columns={EMAIL_COLUMNS}
        rows={rows}
        rowKey={(row) => row.id}
        empty={<EmptyState title="No emails yet">Write the first with New email.</EmptyState>}
      />
      <More list={list} />
    </div>
  );
}

type Asking = { kind: "remove" | "set-aside"; row: Subscriber } | null;

function Subscribers() {
  const list = useList("subscribers", subscribersPage);
  const queryClient = useQueryClient();
  const toast = useToast();
  const [asking, setAsking] = useState<Asking>(null);
  const [why, setWhy] = useState<"bounced" | "unsubscribed">("bounced");
  const [detail, setDetail] = useState("");
  const [busy, setBusy] = useState(false);

  const done = async (said: string) => {
    setAsking(null);
    setDetail("");
    await queryClient.invalidateQueries({ queryKey: LISTS });
    toast({ tone: "success", text: said });
  };

  const act = async () => {
    if (!asking) return;
    setBusy(true);
    try {
      const path = { params: { path: { subscriber_id: asking.row.id } } };
      if (asking.kind === "remove") {
        await api.DELETE("/api/campaigns/admin/subscribers/{subscriber_id}", path);
        await done(`${asking.row.email} is removed and won't be emailed again.`);
      } else {
        await api.POST("/api/campaigns/admin/subscribers/{subscriber_id}/set-aside", {
          ...path,
          body: { why, detail: detail.trim() || null },
        });
        await done(`${asking.row.email} is set aside.`);
      }
    } catch {
      toast({ tone: "danger", text: "That didn't go through. Try again." });
    } finally {
      setBusy(false);
    }
  };

  if (list.error) return <LoadError what="The subscribers" error={list.error} onRetry={() => void list.refetch()} />;
  if (!list.data) return null;
  const rows = list.data.pages.flatMap((page) => page.items);
  const columns: readonly Column<Subscriber>[] = [
    {
      key: "person",
      header: "Person",
      cell: (row) => (
        <span className="mf-newsletter-cell">
          <span className="mf-newsletter-subject">{row.email}</span>
          {row.name ? <span className="mf-newsletter-quiet">{row.name}</span> : null}
        </span>
      ),
    },
    { key: "source", header: "Signed up from", cell: (row) => sourceWords(row.source) },
    { key: "status", header: "Status", cell: (row) => <Pill tone={SUBSCRIBER_TONE[row.status]}>{SUBSCRIBER_WORDS[row.status]}</Pill> },
    { key: "since", header: "Since", cell: (row) => day(row.since) },
    {
      key: "actions",
      header: <span className="mf-visually-hidden">Actions</span>,
      align: "end",
      cell: (row) => (
        <span className="mf-newsletter-actions">
          <Button size="small" onClick={() => { setAsking({ kind: "set-aside", row }); }} aria-label={`Set aside ${row.email}`}>
            Set aside
          </Button>
          <Button size="small" onClick={() => { setAsking({ kind: "remove", row }); }} aria-label={`Remove ${row.email}`}>
            Remove
          </Button>
        </span>
      ),
    },
  ];
  return (
    <div className="mf-newsletter-list">
      <Table
        caption="Subscribers"
        captionHidden
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        empty={<EmptyState title="Nobody has signed up yet">Sign-ups from the site&rsquo;s forms show here.</EmptyState>}
      />
      <More list={list} />
      {asking?.kind === "remove" ? (
        <Dialog title={`Remove ${asking.row.email}?`} onClose={() => { setAsking(null); }}>
          <p>For a person who asks to be forgotten. Their details go, and their address stays set aside so it&rsquo;s never emailed again.</p>
          <div className="mf-newsletter-actions">
            <Button variant="primary" disabled={busy} onClick={() => void act()}>
              Remove them
            </Button>
            <Button onClick={() => { setAsking(null); }}>Keep them</Button>
          </div>
        </Dialog>
      ) : null}
      {asking?.kind === "set-aside" ? (
        <Dialog title={`Set ${asking.row.email} aside?`} onClose={() => { setAsking(null); }}>
          <p>The address won&rsquo;t be emailed again. There&rsquo;s no undoing it.</p>
          <Field label="Why">
            <Select value={why} onChange={(event) => { setWhy(event.target.value === "unsubscribed" ? "unsubscribed" : "bounced"); }}>
              <option value="bounced">It bounced</option>
              <option value="unsubscribed">They asked to stop</option>
            </Select>
          </Field>
          <Field label="Note" hint="Optional: what happened, for whoever reads the list later.">
            <Input value={detail} maxLength={300} onChange={(event) => { setDetail(event.target.value); }} />
          </Field>
          <div className="mf-newsletter-actions">
            <Button variant="primary" disabled={busy} onClick={() => void act()}>
              Set it aside
            </Button>
            <Button onClick={() => { setAsking(null); }}>Cancel</Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

const ASIDE_COLUMNS: readonly Column<SetAsideAddress>[] = [
  { key: "address", header: "Address", cell: (row) => row.email },
  { key: "why", header: "Why", cell: (row) => whyWords(row.why, row.detail) },
  { key: "since", header: "Since", cell: (row) => day(row.since) },
];

function SetAside() {
  const list = useList("set-aside", setAsidePage);
  if (list.error) return <LoadError what="The addresses set aside" error={list.error} onRetry={() => void list.refetch()} />;
  if (!list.data) return null;
  const rows = list.data.pages.flatMap((page) => page.items);
  const reads = list.data.pages[0]?.reads_bounces ?? true;
  return (
    <div className="mf-newsletter-list">
      <Table
        caption="Addresses set aside"
        captionHidden
        columns={ASIDE_COLUMNS}
        rows={rows}
        rowKey={(row) => row.email}
        empty={<EmptyState title="Nothing set aside">Addresses that bounce, complain or unsubscribe show here.</EmptyState>}
      />
      <More list={list} />
      <p className="mf-newsletter-quiet">These addresses are never emailed again, so the site&rsquo;s mail keeps reaching inboxes.</p>
      {reads ? null : (
        <p className="mf-newsletter-quiet">
          Bounces aren&rsquo;t being read: the bounce mailbox&rsquo;s login isn&rsquo;t in the host&rsquo;s variables yet. Unsubscribes and
          addresses set aside by hand still show here.
        </p>
      )}
    </div>
  );
}

export default function AdminNewsletter() {
  const session = useSession();
  const mayPeople = session.status === "signed-in" && session.can(SUBSCRIBER_PERMISSION);
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const tab = tabOf(search.get("tab"), mayPeople);
  const first = useList("emails", emailsPage);
  const head = first.data?.pages[0];
  const tabs = [
    { id: "emails" as const, label: "Emails", panel: tab === "emails" ? <Emails /> : null },
    ...(mayPeople
      ? [
          { id: "subscribers" as const, label: "Subscribers", panel: tab === "subscribers" ? <Subscribers /> : null },
          { id: "set-aside" as const, label: "Set aside", panel: tab === "set-aside" ? <SetAside /> : null },
        ]
      : []),
  ];
  return (
    <AdminPage
      page="Newsletter"
      title="Newsletter"
      lead="Release announcements and news, sent to the people who asked for them."
      actions={
        <LinkButton to="/admin/campaigns/new" variant="primary" icon="plus">
          New email
        </LinkButton>
      }
    >
      <div className="mf-newsletter-admin">
        {head && !head.setup.has_address ? (
          <Attention
            tone="warning"
            what="The newsletter has no postal address"
            why="US law puts a postal address in every newsletter, so nothing sends until it's set. A P.O. box will do."
            action={{ label: "Add it", to: "/admin/settings" }}
          />
        ) : null}
        {head?.waiting ? (
          <Attention
            tone={head.waiting.tone}
            what={head.waiting.what}
            why={head.waiting.why}
            action={{ label: head.waiting.label, to: head.waiting.to }}
          />
        ) : null}
        {head ? (
          <div className="mf-newsletter-cards">
            <StatCard
              level={2}
              label="Subscribed"
              value={head.counts.subscribed.toLocaleString()}
              state={head.setup.signups_open ? { tone: "success", label: "Sign-ups open" } : { tone: "neutral", label: "Sign-ups closed" }}
              line="From the site's sign-up and contact forms"
            />
            <StatCard
              level={2}
              label="Scheduled"
              value={head.counts.scheduled.toLocaleString()}
              {...(head.scheduled ? { state: { tone: "info" as const, label: "Up next" } } : {})}
              line={head.scheduled ? `${head.scheduled.subject}, ${dayAndTime(head.scheduled.when)}` : "Nothing scheduled"}
            />
            <StatCard
              level={2}
              label="Set aside"
              value={head.counts.set_aside.toLocaleString()}
              state={{ tone: "neutral", label: "Handled" }}
              line="Bounced, complained or unsubscribed"
            />
          </div>
        ) : null}
        {first.error ? <LoadError what="The newsletter" error={first.error} onRetry={() => void first.refetch()} /> : null}
        <Tabs
          label="Newsletter"
          selected={tab}
          onSelect={(next) => {
            void navigate(next === "emails" ? "/admin/campaigns" : `/admin/campaigns?tab=${next}`);
          }}
          tabs={tabs}
        />
      </div>
    </AdminPage>
  );
}
