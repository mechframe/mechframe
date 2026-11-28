// portfolio in a browser (`dev plans/contracts/portfolio.md` §7): an editor adds a
// discipline on Collective › Portfolio and opens a piece in the editor; a visitor
// finds it on the Art page, opens its panel at its address and closes it again.
// Each page has nothing serious for axe, in both themes, at 1440 and at a phone's
// 390, and nothing loads from YouTube until a visitor plays the video. The editor adds a
// piece, its picture picked from the library, and publishes it. The e2e
// server runs with storage off (harness.e2e), so media can't give a picture an
// address: the pieces' reads are stood in at the browser, as blog's spec stands in
// its cover, while the disciplines and the Art page's settings are the server's.
// The contract suite and the backend's tests keep real pieces.
import { randomBytes } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

import { THEMES, axe, makeUser, signInTo, theme } from "../../../../kernel/tests/e2e/support";

const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
] as const;

/** A 1 × 1 PNG: a piece's picture, stood in while the e2e server's storage is off. */
const PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg==";
const PICTURE = { id: "51111111-1111-4111-8111-111111111111", url: PNG, srcset: `${PNG} 1200w`, width: 1200, height: 900, alt: "Boats in a harbour at dusk", decorative: false };
const ID = "11111111-1111-4111-8111-111111111111";

/** axe at each width, the page as it is. */
async function cleanAtEachWidth(page: Page): Promise<void> {
  for (const size of WIDTHS) {
    await page.setViewportSize(size);
    expect(await axe(page)).toEqual([]);
  }
  await page.setViewportSize(WIDTHS[0]);
}

function standIn(tag: string, discipline: { slug: string; label: string }) {
  const slug = `harbour-${tag}`;
  const piece = {
    id: ID,
    title: `Harbour at dusk ${tag}`,
    slug,
    discipline,
    artist: { id: "61111111-1111-4111-8111-111111111111", name: "petro" },
    year: 2025,
    about: "Oil on canvas, painted from the sea wall over three evenings.",
    image_id: PICTURE.id,
    picture: PICTURE,
    video: { url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", video_id: "dQw4w9WgXcQ" },
    status: "published" as const,
    publish_at: null,
    published_at: "2026-11-28T12:00:00+00:00",
    version: 1,
    updated_at: "2026-11-28T12:00:00+00:00",
    path: `/art/piece/${slug}`,
  };
  const card = {
    id: ID,
    title: piece.title,
    slug,
    discipline,
    artist: "petro",
    year: 2025,
    picture: PICTURE,
    has_video: true,
    path: piece.path,
  };
  const draft = { ...piece, id: "21111111-1111-4111-8111-111111111111", title: `A draft ${tag}`, slug: `draft-${tag}`, artist: null, status: "draft" as const, published_at: null, path: null, video: null };
  return { slug, piece, card, draft };
}

for (const [name, canvas] of Object.entries(THEMES)) {
  test(`an editor works on Portfolio and a visitor opens a piece on the Art page (${name})`, async ({ page, browser }) => {
    const editor = await makeUser(page.request, "portfolio", { totp: true, roles: ["member", "editor"] });
    const tag = randomBytes(4).toString("hex");
    const label = `Paintings ${tag}`;

    await signInTo(page, editor, "/admin/portfolio");
    await theme(page, name, canvas);
    await expect(page.getByRole("heading", { level: 1, name: "Portfolio" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Admin" }).getByRole("link", { name: "Portfolio" })).toBeVisible();

    // A discipline, the server's own, through the kernel's term routes.
    await page.getByRole("button", { name: "Disciplines" }).click();
    const editing = page.getByRole("dialog", { name: "Edit disciplines" });
    await editing.getByRole("textbox", { name: "New discipline" }).fill(label);
    await editing.getByRole("button", { name: "Add", exact: true }).click();
    await expect(editing.getByRole("textbox", { name: `Name of ${label}` })).toBeVisible();
    expect(await axe(page)).toEqual([]);
    await editing.getByRole("button", { name: "Done" }).click();
    const discipline = { slug: `paintings-${tag}`, label };
    const { slug, piece, card, draft } = standIn(tag, discipline);

    // The pieces, stood in: storage is off, so media can't give a picture an address. The
    // library's list, the new piece's save and its publish are stood in too, so the editor
    // adds and publishes it as a person would (cubic on #171).
    const image = { ...PICTURE, bytes: 1000, content_type: "image/png", filename: "harbour.png", uploaded_by: null, created_at: "2026-11-28T12:00:00+00:00", version: 1 };
    const fresh = { ...piece, status: "draft" as const, published_at: null, path: null, video: null };
    let live = false;
    const sent: string[] = [];
    await page.route("**/api/media/admin/images*", (route) => route.fulfill({ json: { items: [image], next_cursor: null, missing_alt: 0 } }));
    await page.route(/\/api\/portfolio\/admin\/pieces(\?.*)?$/, async (route) => {
      if (route.request().method() === "POST") {
        sent.push(JSON.stringify(route.request().postDataJSON()));
        await route.fulfill({ status: 201, json: fresh });
        return;
      }
      await route.fulfill({ json: { items: live ? [piece, draft] : [draft], next_cursor: null, no_artist: 1 } });
    });
    await page.route(`**/api/portfolio/admin/pieces/${ID}/publish`, async (route) => {
      live = true;
      await route.fulfill({ json: piece });
    });
    await page.route(`**/api/portfolio/admin/pieces/${ID}`, (route) => route.fulfill({ json: live ? piece : fresh }));
    await page.reload();
    await theme(page, name, canvas);
    // Only the uncredited draft is there yet: none has an artist.
    await expect(page.getByText("No piece has an artist yet")).toBeVisible();
    const grid = page.getByRole("list", { name: "Pieces" });
    await expect(grid.getByRole("button", { name: new RegExp(`^Edit A draft ${tag}`) })).toContainText("No artist");

    await page.getByRole("button", { name: "Add a piece" }).click();
    const picker = page.getByRole("dialog", { name: "Choose the new piece's picture" });
    await picker.getByRole("button", { name: `${PICTURE.alt}, 1200 × 900` }).click();
    await expect(page).toHaveURL(/\/admin\/portfolio\/new$/);
    await page.getByRole("textbox", { name: "Title" }).fill(piece.title);
    await expect(page.getByRole("textbox", { name: "Address" })).toHaveValue(`harbour-at-dusk-${tag}`);
    await page.getByLabel("Discipline").selectOption({ label });
    await cleanAtEachWidth(page);
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/admin/portfolio/${ID}$`));
    await expect(page.getByRole("link", { name: "View on the site" })).toHaveAttribute("href", `/art/piece/${slug}`);
    await expect(page.getByLabel("Discipline")).toHaveValue(discipline.slug);
    expect(sent).toHaveLength(1);
    expect(JSON.parse(sent[0] ?? "{}")).toMatchObject({ title: piece.title, discipline: discipline.slug, image_id: PICTURE.id });
    await expect(grid.getByRole("button", { name: new RegExp(`^Edit ${piece.title}`) })).toBeVisible();
    await cleanAtEachWidth(page);

    // A visitor, with no session: the Art page lists it, and its address opens the panel.
    const visitor = await browser.newContext();
    const reader = await visitor.newPage();
    const youtube: string[] = [];
    reader.on("request", (request) => {
      if (/youtube|ytimg|googlevideo/.test(new URL(request.url()).hostname)) youtube.push(request.url());
    });
    await reader.route("**/api/portfolio/pieces?*", (route) => route.fulfill({ json: { items: [card], next_cursor: null } }));
    await reader.route("**/api/portfolio/pieces", (route) => route.fulfill({ json: { items: [card], next_cursor: null } }));
    await reader.route(`**/api/portfolio/pieces/${slug}`, (route) => route.fulfill({ json: { ...card, about: piece.about, video: piece.video } }));
    await reader.route("**/api/portfolio/disciplines", (route) => route.fulfill({ json: { items: [discipline] } }));
    await reader.goto("/art");
    await theme(reader, name, canvas);
    await expect(reader.getByRole("heading", { level: 1, name: "Art" })).toBeVisible();
    await expect(reader.getByRole("navigation", { name: "Show" }).getByRole("link", { name: label })).toHaveAttribute("href", `/art/${discipline.slug}`);
    await cleanAtEachWidth(reader);

    await reader.getByRole("list", { name: "Artwork" }).getByRole("link", { name: piece.title }).click();
    await expect(reader).toHaveURL(new RegExp(`/art/piece/${slug}$`));
    const heading = reader.getByRole("heading", { level: 2, name: piece.title });
    await expect(heading).toBeFocused();
    await expect(reader.getByText("By petro, 2025")).toBeVisible();
    await expect(reader.getByRole("button", { name: /^Play/ })).toBeVisible();
    await cleanAtEachWidth(reader);
    expect(youtube).toEqual([]);

    await reader.getByRole("button", { name: "Close" }).click();
    await expect(reader).toHaveURL(/\/art$/);
    await expect(reader.getByRole("list", { name: "Artwork" }).getByRole("link", { name: piece.title })).toBeFocused();
    expect(youtube).toEqual([]);
    await visitor.close();
  });
}
