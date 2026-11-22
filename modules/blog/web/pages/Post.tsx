// A live post at /blog/:slug (`dev plans/contracts/blog.md` §2; the site's Post
// board): its category, title, byline, cover and body, made HTML and cleaned on
// the server and drawn with the kit's Prose, then its related posts. The words
// are the server copy's own (an h1, the byline, then the body). A slug a live
// post left moves on to it; any other is the 404 page.
import { Link, Navigate, useLocation, useParams } from "react-router";

import { ApiProblem, LoadError, NotFound, Prose, Seo } from "@/kernel";
import { Picture } from "@/modules/media/public";

import { day, pathOf } from "../api";
import { isMoved, usePost } from "../reads";
import "../blog.css";

export default function Post() {
  const { slug = "" } = useParams();
  const { search, hash } = useLocation();
  const found = usePost(slug);
  if (found.isPending) return null;
  if (found.error) {
    if (found.error instanceof ApiProblem && found.error.status === 404) return <NotFound />;
    return <LoadError what="This post" error={found.error} onRetry={() => void found.refetch()} />;
  }
  const post = found.data;
  if (isMoved(post)) return <Navigate to={`${post.moved}${search}${hash}`} replace />;
  return (
    <article className="mf-blog-post">
      <Seo
        title={post.search_title}
        description={post.search_description}
        path={pathOf(post.slug)}
        type="article"
        published={post.published_at}
        modified={post.updated_at}
        {...(post.cover ? { image: post.cover.url } : {})}
      />
      <nav className="mf-blog-crumbs" aria-label="Breadcrumb">
        <Link to="/blog">Blog</Link>
        {post.category ? (
          <>
            {" / "}
            <Link to={`/blog?category=${post.category.slug}`}>{post.category.label}</Link>
          </>
        ) : null}
      </nav>
      <h1>{post.title}</h1>
      <p className="mf-blog-byline">
        {post.author ? <span>{post.author}</span> : null}
        <time dateTime={post.published_at}>{day(post.published_at)}</time>
        <span>{post.reading_minutes} min read</span>
      </p>
      {post.cover ? <Picture image={post.cover} sizes="(min-width: 48rem) 44rem, 100vw" loading="eager" className="mf-blog-post-cover" /> : null}
      <Prose html={post.html} />
      {post.related.length ? (
        <section className="mf-blog-related-posts" aria-labelledby="mf-blog-related">
          <h2 id="mf-blog-related">Related posts</h2>
          <ul>
            {post.related.map((each) => (
              <li key={each.slug}>
                <Link to={pathOf(each.slug)}>{each.title}</Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
