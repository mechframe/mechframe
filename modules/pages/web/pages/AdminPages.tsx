// The pages' list, /admin/pages (`dev plans/contracts/pages.md`; the canvas's
// AdminPages board): every page, newest edit first, with its address, its
// state, the menus it's in and when it was last changed, and New page. While
// no page at /privacy is live, the board's note asks for one.
import { AdminPage, Attention, LinkButton, LoadError, Pill, Table, when, type Column } from "@/kernel";

import { LIST, PRIVACY, STATUS_WORDS, menuWords, useApiQuery, type Listed } from "../api";
import "../pages.css";

const TONE = { draft: "neutral", scheduled: "info", published: "success" } as const;

const COLUMNS: readonly Column<Listed>[] = [
  {
    key: "page",
    header: "Page",
    cell: (page) => (
      <span className="mf-pages-name">
        <span className="mf-pages-title">{page.title}</span>
        <span className="mf-pages-address">{page.address}</span>
      </span>
    ),
  },
  { key: "status", header: "Status", cell: (page) => <Pill tone={TONE[page.status]}>{STATUS_WORDS[page.status]}</Pill> },
  { key: "menu", header: "Menu", cell: (page) => menuWords(page) },
  {
    key: "edited",
    header: "Last edited",
    cell: (page) => (
      <span className="mf-pages-edited">
        {when(page.updated_at)}
        {page.updated_by ? <span className="mf-pages-by">by {page.updated_by}</span> : null}
      </span>
    ),
  },
  {
    key: "edit",
    header: <span className="mf-visually-hidden">Actions</span>,
    align: "end",
    cell: (page) => (
      <LinkButton size="small" to={`/admin/pages/${page.id}`} aria-label={`Edit ${page.title}`}>
        Edit
      </LinkButton>
    ),
  },
];

/** The board's note while no privacy page is live: Write it opens the draft there, or a new page at that address. */
function PrivacyNote({ pages }: { pages: readonly Listed[] }) {
  const found = pages.find((page) => page.address === PRIVACY);
  if (found?.status === "published") return null;
  return (
    <Attention
      tone="warning"
      what="There's no privacy page yet"
      why="The site takes people's email addresses when they sign up, so it should say how they're used."
      action={{ label: "Write it", to: found ? `/admin/pages/${found.id}` : "/admin/pages/new?address=privacy" }}
    />
  );
}

export default function AdminPages() {
  const listed = useApiQuery("get", LIST);
  return (
    <AdminPage
      page="Pages"
      title="Pages"
      lead="Fixed pages like About and Credits. Blog posts, music and products have their own sections."
      actions={
        <LinkButton variant="primary" icon="plus" to="/admin/pages/new">
          New page
        </LinkButton>
      }
    >
      {listed.error ? (
        <LoadError what="The pages" error={listed.error} onRetry={() => void listed.refetch()} />
      ) : listed.data ? (
        <div className="mf-pages-list">
          <PrivacyNote pages={listed.data} />
          <Table
            caption="Pages"
            captionHidden
            columns={COLUMNS}
            rows={listed.data}
            rowKey={(page) => page.id}
            empty="No pages yet. New page writes the first."
          />
        </div>
      ) : null}
    </AdminPage>
  );
}
