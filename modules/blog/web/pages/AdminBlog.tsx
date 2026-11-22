// The blog's list, /admin/blog (`dev plans/contracts/blog.md`; the canvas's
// AdminBlog board): the note for a scheduled post with no cover, Search posts,
// the four filters, the table newest edit first, and the Categories card,
// whose terms staff holding kernel.taxonomy.manage add, rename and delete.
import { useInfiniteQuery } from "@tanstack/react-query";
import { useDeferredValue, useState } from "react";

import {
  AdminPage,
  Attention,
  Button,
  Card,
  Chip,
  LinkButton,
  LoadError,
  Pill,
  SearchBox,
  Table,
  when,
  type Column,
} from "@/kernel";

import { LIST, STATUS_TONE, STATUS_WORDS, api, day, type Listed, type Status } from "../api";
import "../blog.css";
import { Categories } from "../components/Categories";

const FILTERS: readonly { value: Status | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "published", label: "Live" },
  { value: "scheduled", label: "Scheduled" },
  { value: "draft", label: "Drafts" },
];

/** When a post goes or went live, as the board's When column says it. */
function whenOf(post: Listed): string {
  if (post.status === "scheduled") return when(post.publish_at);
  if (post.status === "published" && post.published_at) return day(post.published_at);
  return "Not published";
}

const COLUMNS: readonly Column<Listed>[] = [
  {
    key: "post",
    header: "Post",
    cell: (post) => (
      <span className="mf-blog-name">
        <span className="mf-blog-title">{post.title}</span>
        {post.category ? <span className="mf-blog-category">{post.category.label}</span> : null}
      </span>
    ),
  },
  { key: "author", header: "Author", cell: (post) => post.author?.name ?? "No one named" },
  { key: "status", header: "Status", cell: (post) => <Pill tone={STATUS_TONE[post.status]}>{STATUS_WORDS[post.status]}</Pill> },
  { key: "when", header: "When", cell: whenOf },
  {
    key: "edit",
    header: <span className="mf-visually-hidden">Actions</span>,
    align: "end",
    cell: (post) => (
      <LinkButton size="small" to={`/admin/blog/${post.id}`} aria-label={`Edit ${post.title}`}>
        Edit
      </LinkButton>
    ),
  },
];

export default function AdminBlog() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Status | "all">("all");
  const words = useDeferredValue(q.trim());
  const query = { ...(words ? { q: words } : {}), ...(filter === "all" ? {} : { status: filter }) };
  const listed = useInfiniteQuery({
    queryKey: ["get", LIST, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET(LIST, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The site answered without the posts.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
  const first = listed.data?.pages[0];
  const posts = listed.data?.pages.flatMap((page) => page.items) ?? [];
  const waiting = first?.needs_cover;

  return (
    <AdminPage
      page="Blog"
      title="Blog"
      lead="Posts for the site's blog. Drafts stay private until you publish or schedule them."
      actions={
        <LinkButton variant="primary" icon="plus" to="/admin/blog/new">
          New post
        </LinkButton>
      }
    >
      <div className="mf-blog-board">
        <div className="mf-blog-main">
          {waiting ? (
            <Attention
              tone="warning"
              what="A scheduled post has no cover image"
              why={`${waiting.title} goes up on ${when(waiting.publish_at)}. Without a cover, it shows a plain card on the blog and when it's shared.`}
              action={{ label: "Add a cover", to: `/admin/blog/${waiting.id}` }}
            />
          ) : null}
          <div className="mf-blog-filters">
            <SearchBox
              label="Search posts"
              value={q}
              onChange={(event) => {
                setQ(event.target.value);
              }}
            />
            <div className="mf-blog-chips" role="group" aria-label="Show">
              {FILTERS.map((each) => (
                <Chip
                  key={each.value}
                  pressed={filter === each.value}
                  onPressedChange={() => {
                    setFilter(each.value);
                  }}
                >
                  {each.label}
                </Chip>
              ))}
            </div>
          </div>
          {listed.error ? (
            <LoadError what="The posts" error={listed.error} onRetry={() => void listed.refetch()} />
          ) : listed.data ? (
            <>
              <Table
                caption="Posts"
                captionHidden
                columns={COLUMNS}
                rows={posts}
                rowKey={(post) => post.id}
                empty={words || filter !== "all" ? "No posts match. Try other words, or show all." : "No posts yet. New post writes the first."}
              />
              {listed.hasNextPage ? (
                <Button disabled={listed.isFetchingNextPage} onClick={() => void listed.fetchNextPage()}>
                  Older posts
                </Button>
              ) : null}
            </>
          ) : null}
        </div>
        <div className="mf-blog-side">
          <Card title="Categories" level={2}>
            <Categories />
          </Card>
        </div>
      </div>
    </AdminPage>
  );
}
