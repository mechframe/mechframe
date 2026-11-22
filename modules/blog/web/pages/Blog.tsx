// The blog, /blog (`dev plans/contracts/blog.md` §2; the site's Blog board): the
// latest post first and larger, then the rest as cards, filtered by category
// (`?category=`), with Older posts for the next 12. The words are the server
// copy's own, so a crawler reads what a person sees.
import { Link, useSearchParams } from "react-router";

import { Button, Chip, LoadError, Seo, useSite } from "@/kernel";
import { Picture } from "@/modules/media/public";

import { day, pathOf, type Card } from "../api";
import { useCategories, usePosts } from "../reads";
import "../blog.css";

function Byline({ card }: { card: Card }) {
  return (
    <p className="mf-blog-byline">
      {card.author ? <span>{card.author}</span> : null}
      <time dateTime={card.published_at}>{day(card.published_at)}</time>
      <span>{card.reading_minutes} min read</span>
    </p>
  );
}

function PostCard({ card, latest = false }: { card: Card; latest?: boolean }) {
  const Heading = latest ? "h2" : "h3";
  return (
    <article className={latest ? "mf-blog-card mf-blog-card--latest" : "mf-blog-card"}>
      {card.cover ? (
        <Picture image={card.cover} sizes={latest ? "(min-width: 60rem) 60vw, 100vw" : "(min-width: 60rem) 30vw, 100vw"} className="mf-blog-card-picture" />
      ) : (
        <div className="mf-blog-card-plain" aria-hidden="true" />
      )}
      <div className="mf-blog-card-words">
        {card.category ? <span className="mf-blog-card-category">{card.category.label}</span> : null}
        <Heading className="mf-blog-card-title">
          <Link to={pathOf(card.slug)}>{card.title}</Link>
        </Heading>
        {card.summary ? <p className="mf-blog-card-summary">{card.summary}</p> : null}
        <Byline card={card} />
      </div>
    </article>
  );
}

export default function Blog() {
  const site = useSite();
  const [search, setSearch] = useSearchParams();
  const category = search.get("category") ?? "";
  const categories = useCategories();
  const posts = usePosts({ category });
  const cards = posts.data?.pages.flatMap((page) => page.items) ?? [];
  const [latest, ...rest] = cards;
  const shown = (categories.data?.items ?? []).filter((each) => each.posts > 0);
  const named = shown.find((each) => each.slug === category);

  function choose(slug: string) {
    setSearch(slug ? { category: slug } : {}, { replace: true });
  }

  return (
    <div className="mf-blog">
      <Seo
        title={site ? `Blog · ${site.name}` : "Blog"}
        description={site ? `The newest posts from ${site.name}.` : "The newest posts."}
        path={category ? `/blog?category=${category}` : "/blog"}
      />
      <h1>{named ? `Blog: ${named.label}` : "Blog"}</h1>
      {/* All posts stays while a filter is on, however few categories have posts (CodeRabbit on #123). */}
      {shown.length > 1 || category ? (
        <div className="mf-blog-chips" role="group" aria-label="Show posts from">
          <Chip
            pressed={!category}
            onPressedChange={() => {
              choose("");
            }}
          >
            All posts
          </Chip>
          {shown.map((each) => (
            <Chip
              key={each.slug}
              pressed={category === each.slug}
              onPressedChange={() => {
                choose(each.slug);
              }}
            >
              {each.label}
            </Chip>
          ))}
        </div>
      ) : null}
      {posts.error ? (
        <LoadError what="The posts" error={posts.error} onRetry={() => void posts.refetch()} />
      ) : posts.data ? (
        latest ? (
          <>
            <PostCard card={latest} latest />
            {rest.length ? (
              <div className="mf-blog-grid">
                {rest.map((card) => (
                  <PostCard key={card.slug} card={card} />
                ))}
              </div>
            ) : null}
            {posts.hasNextPage ? (
              <Button disabled={posts.isFetchingNextPage} onClick={() => void posts.fetchNextPage()}>
                Older posts
              </Button>
            ) : null}
          </>
        ) : (
          <p className="mf-blog-empty">Nothing's posted {named ? `in ${named.label} ` : ""}yet.</p>
        )
      ) : null}
    </div>
  );
}
