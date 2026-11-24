// A live page at its address (`dev plans/contracts/pages.md` §2): its title, the
// day it last changed and its body, made HTML and cleaned on the server, drawn
// with the kit's Prose. The words are the server copy's own (an h1, the Updated
// line, then the body), so a crawler reads what a person sees. An address a live page left moves on to it; any
// other is the 404 page. It reads through `usePage`, the read a site's own page
// replacing this one imports from `@/modules/pages/public`.
import { Navigate, useLocation, useParams } from "react-router";

import { ApiProblem, LoadError, NotFound, Prose, Seo } from "@/kernel";

import { day } from "../api";
import { isMoved, usePage } from "../reads";
import "../pages.css";

export default function PublicPage() {
  const { address = "" } = useParams();
  const { search, hash } = useLocation();
  const found = usePage(address);
  if (found.isPending) return null;
  if (found.error) {
    if (found.error instanceof ApiProblem && found.error.status === 404) return <NotFound />;
    return <LoadError what="This page" error={found.error} onRetry={() => void found.refetch()} />;
  }
  const page = found.data;
  if (isMoved(page)) return <Navigate to={`${page.moved}${search}${hash}`} replace />;
  return (
    <article className="mf-page">
      <Seo title={page.search_title} description={page.search_description} path={page.address} modified={page.updated_at} />
      <h1>{page.title}</h1>
      <p className="mf-page-updated">
        Updated <time dateTime={page.updated_at}>{day(page.updated_at)}</time>
      </p>
      <Prose html={page.html} />
    </article>
  );
}
