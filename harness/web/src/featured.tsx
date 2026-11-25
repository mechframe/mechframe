// A player as a site's page reads it (harness/web/featured.html, at
// /featured.html?slot=<key>; dev plans/contracts/featured.md §4): what's live in
// the slot now, in order, through featured's `useFeatured`, drawn as a plain list
// of titles and lines. How a site draws a player is its own; this only shows the
// read. Sample words only.
import "../../../themes/machined-light/tokens.css";
import "../../../themes/vibrant-mindz/tokens.css";
import "./frame.css";

import { defineSite, mountApp } from "@/kernel";
import { useFeatured } from "@/modules/featured/public";

function Featured() {
  const key = new URLSearchParams(window.location.search).get("slot") ?? "spotlight";
  const found = useFeatured(key);
  if (found.error) return <p role="alert">There's no player “{key}”.</p>;
  if (!found.data) return <p role="status">Reading the player…</p>;
  return (
    <section className="frame-long">
      <h1>{found.data.label}</h1>
      {found.data.items.length === 0 ? (
        <p>Nothing is live in it now.</p>
      ) : (
        <ol aria-label={`Live in the ${found.data.label}`}>
          {found.data.items.map((each) => (
            <li key={each.id}>
              {each.ref ? `${each.ref.title}: ${each.ref.line}` : each.link ? `${each.link.title} (youtu.be/${each.link.video_id})` : ""}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

const site = defineSite({
  routes: {
    public: [{ path: "/featured.html", lazy: () => Promise.resolve({ default: Featured }) }],
    member: [],
  },
});

void mountApp({ modules: [], site });
