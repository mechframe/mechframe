// Collective › Portfolio, /admin/portfolio (`dev plans/contracts/portfolio.md` §2;
// VM Website's AdminPortfolio board): the note while pieces have no artist,
// the chips by discipline (and Disciplines for staff holding
// kernel.taxonomy.manage), the grid of pieces with their pills, and the editor
// beside it for the piece chosen, at its own address (`/admin/portfolio/<id>`,
// `/new` for a new one), so the kit's guard asks before another replaces unsaved
// edits (Codex on #171). Add a piece picks its picture first. Someone holding `portfolio.piece.add` alone sees and edits
// their own pieces; `portfolio.piece.manage` every piece (decision 0074).
import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router";

import { AdminPage, Attention, Button, Card, Chip, LoadError, Pill, useSession, type Tone } from "@/kernel";
import { ImagePicker, Picture } from "@/modules/media/public";

import { DISCIPLINES, LIST, MANAGE, ONE, STATUS_WORDS, api, joined, useApiQuery, type AdminPiece, type Picture as PiecePicture } from "../api";
import { EditDisciplines, TAXONOMY } from "../components/Disciplines";
import { PieceEditor, pictureOf } from "../components/PieceEditor";
import "../portfolio.css";

const NEW = "new";

function pillOf(piece: AdminPiece): { tone: Tone; words: string } | null {
  if (!piece.artist) return { tone: "warning", words: "No artist" };
  if (piece.status !== "published") return { tone: piece.status === "scheduled" ? "info" : "neutral", words: STATUS_WORDS[piece.status] };
  return null;
}

function Tile({ piece, chosen, onChoose }: { piece: AdminPiece; chosen: boolean; onChoose: () => void }) {
  const pill = pillOf(piece);
  return (
    <li>
      {/* Its name is its words with "Edit" first, so what's seen is part of what's said (WCAG 2.5.3). */}
      <button type="button" className="mf-portfolio-tile" aria-pressed={chosen} onClick={onChoose}>
        <span className="mf-visually-hidden">Edit </span>
        {piece.picture ? (
          <Picture image={{ ...piece.picture, decorative: true }} sizes="170px" className="mf-portfolio-tile-picture" />
        ) : (
          <span className="mf-portfolio-no-photo">No photo yet</span>
        )}
        <span className="mf-portfolio-tile-title">{piece.title}</span>
        <span className="mf-portfolio-tile-meta">{piece.discipline?.label ?? "No discipline"}</span>
        {pill ? (
          <span className="mf-portfolio-tile-pill">
            <Pill tone={pill.tone}>{pill.words}</Pill>
          </span>
        ) : null}
      </button>
    </li>
  );
}

export default function PortfolioAdmin() {
  const session = useSession();
  const signedIn = session.status === "signed-in" ? session : null;
  const manages = signedIn?.can(MANAGE) ?? false;
  const mayTaxonomy = signedIn?.can(TAXONOMY) ?? false;
  const me = { id: signedIn?.user.id ?? "", name: signedIn?.user.name || signedIn?.user.email || "You" };
  const navigate = useNavigate();
  const location = useLocation();
  const chosen = useParams().id ?? "";
  // The filter is in the address, so it stays as a piece is chosen.
  const [search, setSearch] = useSearchParams();
  const discipline = search.get("discipline") ?? "";
  const [picking, setPicking] = useState(false);
  const picked = chosen === NEW ? ((location.state as { picked?: PiecePicture } | null)?.picked ?? null) : null;
  const [editingDisciplines, setEditingDisciplines] = useState(false);

  const disciplines = useApiQuery("get", DISCIPLINES);
  const query = discipline ? { discipline } : {};
  const listed = useInfiniteQuery({
    queryKey: ["get", LIST, { params: { query } }, "pages"],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => {
      const { data } = await api.GET(LIST, { params: { query: { ...query, ...(pageParam ? { cursor: pageParam } : {}) } } });
      if (!data) throw new Error("The site answered without the pieces.");
      return data;
    },
    getNextPageParam: (last) => last.next_cursor,
  });
  const one = useApiQuery("get", ONE, { params: { path: { piece_id: chosen } } }, { enabled: chosen !== "" && chosen !== NEW });
  const pieces = listed.data?.pages.flatMap((page) => page.items) ?? [];
  const noArtist = listed.data?.pages[0]?.no_artist ?? null;
  const everyLoaded = listed.data !== undefined && !listed.hasNextPage;
  const firstUncredited = pieces.find((each) => each.artist === null);
  const items = disciplines.data?.items ?? [];
  const labels = items.map((each) => each.label);

  function choose(piece: string, state?: { picked: PiecePicture }) {
    void navigate({ pathname: piece ? `/admin/portfolio/${piece}` : "/admin/portfolio", search: location.search }, state ? { state } : undefined);
  }

  function filter(slug: string) {
    setSearch(slug ? { discipline: slug } : {}, { replace: true });
  }

  const lead = labels.length ? `${joined(labels)}. Everything live here shows on the Art page.` : "Everything live here shows on the Art page.";
  const uncreditedWhat =
    noArtist === null || noArtist === 0
      ? null
      : // Only the whole list can say none has one: a discipline's is a part (cubic on #171).
        !discipline && everyLoaded && noArtist === pieces.length
        ? "No piece has an artist yet"
        : noArtist === 1
          ? "1 piece has no artist"
          : `${String(noArtist)} pieces have no artist`;

  return (
    <AdminPage
      page="Portfolio"
      title="Portfolio"
      lead={lead}
      actions={
        <Button
          variant="primary"
          icon="upload"
          onClick={() => {
            setPicking(true);
          }}
        >
          Add a piece
        </Button>
      }
    >
      {manages && uncreditedWhat ? (
        <Attention
          tone="warning"
          what={uncreditedWhat}
          why="The Art page names no artist on them until each is credited."
          {...(firstUncredited ? { action: { label: "Credit the first", to: `/admin/portfolio/${firstUncredited.id}` } } : {})}
        />
      ) : null}
      <div className="mf-portfolio-board">
        <div className="mf-portfolio-main">
          <div className="mf-portfolio-chips" role="group" aria-label="Show">
            <Chip
              pressed={discipline === ""}
              onPressedChange={() => {
                filter("");
              }}
            >
              All
            </Chip>
            {items.map((each) => (
              <Chip
                key={each.id}
                pressed={discipline === each.slug}
                onPressedChange={() => {
                  filter(each.slug);
                }}
              >
                {each.label}
              </Chip>
            ))}
            {mayTaxonomy ? (
              <Button
                size="small"
                onClick={() => {
                  setEditingDisciplines(true);
                }}
              >
                Disciplines
              </Button>
            ) : null}
          </div>
          {listed.error ? (
            <LoadError what="The pieces" error={listed.error} onRetry={() => void listed.refetch()} />
          ) : listed.data ? (
            pieces.length ? (
              <>
                <ul className="mf-portfolio-grid" aria-label="Pieces">
                  {pieces.map((piece) => (
                    <Tile
                      key={piece.id}
                      piece={piece}
                      chosen={piece.id === chosen}
                      onChoose={() => {
                        choose(piece.id);
                      }}
                    />
                  ))}
                </ul>
                {listed.hasNextPage ? (
                  <Button disabled={listed.isFetchingNextPage} onClick={() => void listed.fetchNextPage()}>
                    Load more
                  </Button>
                ) : null}
              </>
            ) : (
              <p className="mf-portfolio-hint">{discipline ? "No pieces in this discipline yet." : "No pieces yet. Add a piece puts up the first."}</p>
            )
          ) : null}
        </div>
        <div className="mf-portfolio-side">
          {chosen === NEW && picked ? (
            <Card level={2}>
              <PieceEditor
                key={`new-${picked.id}`}
                piece={null}
                picked={picked}
                disciplines={items}
                me={me}
                manages={manages}
                onSaved={(piece) => {
                  choose(piece.id);
                }}
                onDeleted={() => {
                  choose("");
                }}
              />
            </Card>
          ) : chosen && one.data ? (
            <Card level={2}>
              <PieceEditor
                key={one.data.id}
                piece={one.data}
                picked={null}
                disciplines={items}
                me={me}
                manages={manages}
                onSaved={() => undefined}
                onDeleted={() => {
                  choose("");
                }}
              />
            </Card>
          ) : chosen && one.error ? (
            <LoadError what="The piece" error={one.error} onRetry={() => void one.refetch()} />
          ) : (
            <p className="mf-portfolio-hint">Pick a piece to edit it, or add a piece.</p>
          )}
        </div>
      </div>
      {picking ? (
        <ImagePicker
          title="Choose the new piece's picture"
          onPick={(image) => {
            setPicking(false);
            choose(NEW, { picked: pictureOf(image) });
          }}
          onClose={() => {
            setPicking(false);
          }}
        />
      ) : null}
      {editingDisciplines ? (
        <EditDisciplines
          items={items}
          onClose={() => {
            setEditingDisciplines(false);
          }}
        />
      ) : null}
    </AdminPage>
  );
}
