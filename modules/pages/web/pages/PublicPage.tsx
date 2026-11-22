// A live page at its address (`dev plans/contracts/pages.md` §2): its title and
// its body, made HTML and cleaned on the server, drawn with the kit's Prose.
// The words are the server copy's own (an h1, then the body), so a crawler
// reads what a person sees. An address a live page left moves on to it; any
// other is the 404 page.
import { Navigate, useLocation, useParams } from "react-router";

import { ApiProblem, LoadError, NotFound, Prose, Seo } from "@/kernel";

import { useApiQuery } from "../api";
import "../pages.css";

export default function PublicPage() {
  const { address = "" } = useParams();
  const { search, hash } = useLocation();
  const found = useApiQuery("get", "/api/pages/page", { params: { query: { address: `/${address}` } } });
  if (found.isPending) return null;
  if (found.error) {
    if (found.error instanceof ApiProblem && found.error.status === 404) return <NotFound />;
    return <LoadError what="This page" error={found.error} onRetry={() => void found.refetch()} />;
  }
  const page = found.data;
  if ("moved" in page) return <Navigate to={`${page.moved}${search}${hash}`} replace />;
  return (
    <article className="mf-page">
      <Seo title={page.search_title} description={page.search_description} path={page.address} modified={page.updated_at} />
      <h1>{page.title}</h1>
      <Prose html={page.html} />
    </article>
  );
}
